"""
Summary Service: Pre-computes daily aggregations for weekly reports.
"""
from sqlalchemy import text
from app.services.db_service import AsyncSessionLocal
from app.services.mcp_service import mcp_service
from datetime import datetime, timedelta
import logging
import json

logger = logging.getLogger(__name__)


class SummaryService:
    async def compute_daily_summary(self, date: datetime.date = None):
        """Compute and store summary for a specific date."""
        if date is None:
            date = (datetime.now() - timedelta(days=1)).date()
        
        start_of_day = datetime.combine(date, datetime.min.time())
        end_of_day = datetime.combine(date, datetime.max.time())
        
        try:
            async with AsyncSessionLocal() as session:
                # Message stats
                msg_result = await session.execute(text("""
                    SELECT COUNT(*), COUNT(DISTINCT user_id), AVG(sentiment_score)
                    FROM message_logs WHERE created_at BETWEEN :start AND :end
                """), {"start": start_of_day, "end": end_of_day})
                msg_row = msg_result.fetchone()
                
                total_messages = msg_row[0] or 0
                unique_users = msg_row[1] or 0
                avg_sentiment = msg_row[2] or 0.0
                
                # POS orders
                total_orders, total_revenue, top_products = 0, 0.0, []
                try:
                    orders_data = await mcp_service.call_tool("pos", "get_orders_by_date", {"date": date.isoformat()})
                    if orders_data and isinstance(orders_data, dict):
                        total_orders = orders_data.get("count", 0)
                        total_revenue = orders_data.get("total", 0.0)
                        top_products = orders_data.get("top_items", [])
                except Exception as e:
                    logger.warning(f"Could not fetch POS orders: {e}")
                
                # Upsert summary
                await session.execute(text("""
                    INSERT INTO daily_summaries (date, total_orders, total_revenue, unique_users, total_messages, avg_sentiment, top_products, stockout_requests)
                    VALUES (:date, :orders, :revenue, :users, :messages, :sentiment, :products, :stockouts)
                    ON CONFLICT (date) DO UPDATE SET
                        total_orders = :orders, total_revenue = :revenue, unique_users = :users,
                        total_messages = :messages, avg_sentiment = :sentiment, top_products = :products, stockout_requests = :stockouts
                """), {
                    "date": date, "orders": total_orders, "revenue": total_revenue, "users": unique_users,
                    "messages": total_messages, "sentiment": avg_sentiment, "products": json.dumps(top_products), "stockouts": "[]"
                })
                await session.commit()
                
                logger.info(f"Summary for {date}: {unique_users} users, {total_messages} msgs, {total_orders} orders")
                return True
                
        except Exception as e:
            logger.error(f"Failed to compute summary: {e}")
            return False
    
    async def get_summaries_for_period(self, start_date, end_date) -> list:
        """Get pre-computed summaries for a date range."""
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(text(
                    "SELECT * FROM daily_summaries WHERE date BETWEEN :start AND :end ORDER BY date ASC"
                ), {"start": start_date, "end": end_date})
                return [dict(row._mapping) for row in result.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get summaries: {e}")
            return []
    
    async def get_aggregated_summary(self, start_date, end_date) -> dict:
        """Get aggregated metrics for a period."""
        summaries = await self.get_summaries_for_period(start_date, end_date)
        
        if not summaries:
            return {"period_start": str(start_date), "period_end": str(end_date), "total_orders": 0, "total_revenue": 0.0, "unique_users": 0, "total_messages": 0, "avg_sentiment": 0.0}
        
        return {
            "period_start": str(start_date),
            "period_end": str(end_date),
            "total_orders": sum(s.get("total_orders", 0) for s in summaries),
            "total_revenue": sum(s.get("total_revenue", 0.0) for s in summaries),
            "unique_users": sum(s.get("unique_users", 0) for s in summaries),
            "total_messages": sum(s.get("total_messages", 0) for s in summaries),
            "avg_sentiment": round(sum(s.get("avg_sentiment", 0.0) for s in summaries) / len(summaries), 2)
        }


summary_service = SummaryService()
