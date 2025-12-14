"""
Summary Service: Pre-computes daily aggregations for efficient weekly reports.
"""
from sqlalchemy import text
from app.services.db_service import AsyncSessionLocal
from app.services.mcp_service import mcp_service
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SummaryService:
    """Service for computing and storing daily summaries."""
    
    async def compute_daily_summary(self, date: datetime.date = None):
        """
        Compute and store summary for a specific date.
        
        Args:
            date: The date to summarize (defaults to yesterday)
        """
        if date is None:
            date = (datetime.now() - timedelta(days=1)).date()
        
        start_of_day = datetime.combine(date, datetime.min.time())
        end_of_day = datetime.combine(date, datetime.max.time())
        
        try:
            async with AsyncSessionLocal() as session:
                # 1. Count messages and calculate avg sentiment
                msg_query = text("""
                    SELECT 
                        COUNT(*) as total_messages,
                        COUNT(DISTINCT user_id) as unique_users,
                        AVG(sentiment_score) as avg_sentiment
                    FROM message_logs
                    WHERE created_at BETWEEN :start AND :end
                """)
                msg_result = await session.execute(msg_query, {
                    "start": start_of_day,
                    "end": end_of_day
                })
                msg_row = msg_result.fetchone()
                
                total_messages = msg_row[0] or 0
                unique_users = msg_row[1] or 0
                avg_sentiment = msg_row[2] or 0.0
                
                # 2. Get order data from PHPPOS via MCP (if available)
                total_orders = 0
                total_revenue = 0.0
                top_products = []
                
                try:
                    # This would query PHPPOS for orders on that date
                    # For now, we'll use a placeholder that can be enhanced
                    orders_data = await mcp_service.call_tool(
                        "pos", 
                        "get_orders_by_date",
                        {"date": date.isoformat()}
                    )
                    if orders_data and isinstance(orders_data, dict):
                        total_orders = orders_data.get("count", 0)
                        total_revenue = orders_data.get("total", 0.0)
                        top_products = orders_data.get("top_items", [])
                except Exception as e:
                    logger.warning(f"Could not fetch POS orders for summary: {e}")
                
                # 3. Get stockout requests (products requested but not in stock)
                stockout_query = text("""
                    SELECT content
                    FROM message_logs
                    WHERE created_at BETWEEN :start AND :end
                    AND role = 'user'
                    AND (intent = 'purchase' OR intent = 'inquiry')
                """)
                stockout_result = await session.execute(stockout_query, {
                    "start": start_of_day,
                    "end": end_of_day
                })
                # This is a placeholder - in production, we'd cross-reference with stock
                stockout_requests = []
                
                # 4. Upsert the summary
                upsert_query = text("""
                    INSERT INTO daily_summaries 
                        (date, total_orders, total_revenue, unique_users, total_messages, avg_sentiment, top_products, stockout_requests)
                    VALUES 
                        (:date, :orders, :revenue, :users, :messages, :sentiment, :products, :stockouts)
                    ON CONFLICT (date) DO UPDATE SET
                        total_orders = :orders,
                        total_revenue = :revenue,
                        unique_users = :users,
                        total_messages = :messages,
                        avg_sentiment = :sentiment,
                        top_products = :products,
                        stockout_requests = :stockouts
                """)
                
                import json
                await session.execute(upsert_query, {
                    "date": date,
                    "orders": total_orders,
                    "revenue": total_revenue,
                    "users": unique_users,
                    "messages": total_messages,
                    "sentiment": avg_sentiment,
                    "products": json.dumps(top_products),
                    "stockouts": json.dumps(stockout_requests)
                })
                await session.commit()
                
                logger.info(f"Daily summary computed for {date}: {unique_users} users, {total_messages} msgs, {total_orders} orders")
                return True
                
        except Exception as e:
            logger.error(f"Failed to compute daily summary: {e}")
            return False
    
    async def get_summaries_for_period(
        self,
        start_date: datetime.date,
        end_date: datetime.date
    ) -> list:
        """Get pre-computed summaries for a date range."""
        try:
            async with AsyncSessionLocal() as session:
                query = text("""
                    SELECT * FROM daily_summaries
                    WHERE date BETWEEN :start AND :end
                    ORDER BY date ASC
                """)
                result = await session.execute(query, {
                    "start": start_date,
                    "end": end_date
                })
                return [dict(row._mapping) for row in result.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get summaries: {e}")
            return []
    
    async def get_aggregated_summary(
        self,
        start_date: datetime.date,
        end_date: datetime.date
    ) -> dict:
        """Get aggregated metrics for a period."""
        summaries = await self.get_summaries_for_period(start_date, end_date)
        
        if not summaries:
            return {
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "total_orders": 0,
                "total_revenue": 0.0,
                "unique_users": 0,
                "total_messages": 0,
                "avg_sentiment": 0.0
            }
        
        total_orders = sum(s.get("total_orders", 0) for s in summaries)
        total_revenue = sum(s.get("total_revenue", 0.0) for s in summaries)
        unique_users = sum(s.get("unique_users", 0) for s in summaries)  # Note: not distinct across days
        total_messages = sum(s.get("total_messages", 0) for s in summaries)
        avg_sentiment = sum(s.get("avg_sentiment", 0.0) for s in summaries) / len(summaries)
        
        return {
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "unique_users": unique_users,
            "total_messages": total_messages,
            "avg_sentiment": round(avg_sentiment, 2)
        }


# Singleton instance
summary_service = SummaryService()
