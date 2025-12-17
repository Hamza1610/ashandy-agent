"""
Scheduler: Autonomous task scheduling for summaries, reports, sync, and learning.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.services.summary_service import summary_service
from app.services.ingestion_service import ingestion_service
from app.tools.report_tool import generate_comprehensive_report
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

# Optional imports with graceful fallback
try:
    from app.services.feedback_service import feedback_service
    FEEDBACK_SERVICE_AVAILABLE = True
except ImportError:
    FEEDBACK_SERVICE_AVAILABLE = False


async def daily_summary_job():
    """Compute daily summary at midnight."""
    try:
        yesterday = (datetime.now() - timedelta(days=1)).date()
        logger.info(f"Running daily summary for {yesterday}")
        await summary_service.compute_daily_summary(date=yesterday)
    except Exception as e:
        logger.error(f"Daily summary failed: {e}")


async def weekly_instagram_sync_job():
    """Sync products from Instagram every Sunday at 2 AM."""
    try:
        logger.info("Running weekly Instagram sync...")
        result = await ingestion_service.sync_instagram_products(limit=50)
        logger.info(f"Instagram sync completed: {result}")
    except Exception as e:
        logger.error(f"Instagram sync failed: {e}")


async def weekly_report_job():
    """Generate weekly report every Monday at 3 AM."""
    try:
        logger.info("Running weekly report generation...")
        result = await generate_comprehensive_report.ainvoke({
            "start_date": "last week",
            "end_date": "today"
        })
        logger.info(f"Weekly report generated. Length: {len(result)} chars")
    except Exception as e:
        logger.error(f"Weekly report failed: {e}")


async def weekly_feedback_learning_job():
    """Aggregate feedback and update preferences every Monday at 4 AM."""
    if not FEEDBACK_SERVICE_AVAILABLE:
        return
    try:
        logger.info("Running weekly feedback learning...")
        result = await feedback_service.run_weekly_learning()
        logger.info(f"Feedback learning completed: {result}")
    except Exception as e:
        logger.error(f"Feedback learning failed: {e}")


async def cart_abandonment_followup_job():
    """
    Follow up on abandoned carts (unpaid orders > 6 hours old).
    
    Runs every 6 hours to recover lost sales by sending reminder messages.
    """
    from app.services.db_service import AsyncSessionLocal
    from app.services.meta_service import meta_service
    from sqlalchemy import text
    
    try:
        logger.info("Running cart abandonment follow-up...")
        
        async with AsyncSessionLocal() as session:
            # Find unpaid orders older than 6 hours but less than 48 hours
            result = await session.execute(text("""
                SELECT order_id, user_id, total_amount, items, created_at
                FROM orders
                WHERE status = 'pending_payment'
                AND created_at > NOW() - INTERVAL '48 hours'
                AND created_at < NOW() - INTERVAL '6 hours'
                AND (metadata->>'abandonment_reminder_sent') IS NULL
                LIMIT 10
            """))
            
            abandoned_orders = result.fetchall()
            
            if not abandoned_orders:
                logger.info("No abandoned carts found.")
                return
            
            recovered = 0
            for order in abandoned_orders:
                order_id, user_id, amount, items, created_at = order
                
                # Send WhatsApp reminder
                message = (
                    f"Hi! 👋 I noticed you started an order but didn't complete payment.\n\n"
                    f"Your cart (₦{amount:,.0f}) is still here waiting for you! ✨\n\n"
                    f"Ready to complete your purchase? Just reply 'Yes' and I'll send you the payment link! 💄"
                )
                
                try:
                    await meta_service.send_whatsapp_text(user_id, message)
                    
                    # Mark as reminded
                    await session.execute(text("""
                        UPDATE orders 
                        SET metadata = COALESCE(metadata, '{}') || '{"abandonment_reminder_sent": true}'::jsonb
                        WHERE order_id = :oid
                    """), {"oid": order_id})
                    
                    recovered += 1
                    logger.info(f"Sent abandonment reminder to {user_id} for order {order_id}")
                except Exception as e:
                    logger.error(f"Failed to send abandonment reminder to {user_id}: {e}")
            
            await session.commit()
            logger.info(f"Cart abandonment follow-up complete: {recovered}/{len(abandoned_orders)} reminders sent")
            
    except Exception as e:
        logger.error(f"Cart abandonment job failed: {e}")


def configure_scheduler():
    """Configure all scheduled jobs. Call during startup."""
    scheduler.add_job(daily_summary_job, CronTrigger(hour=0, minute=0),
                      id="daily_summary", name="Daily Summary", replace_existing=True)
    scheduler.add_job(weekly_instagram_sync_job, CronTrigger(day_of_week="sun", hour=2, minute=0),
                      id="weekly_instagram_sync", name="IG Sync", replace_existing=True)
    scheduler.add_job(weekly_report_job, CronTrigger(day_of_week="mon", hour=3, minute=0),
                      id="weekly_report", name="Weekly Report", replace_existing=True)
    scheduler.add_job(weekly_feedback_learning_job, CronTrigger(day_of_week="mon", hour=4, minute=0),
                      id="weekly_feedback_learning", name="Feedback Learning", replace_existing=True)
    # P1: Cart abandonment follow-up every 6 hours
    scheduler.add_job(cart_abandonment_followup_job, CronTrigger(hour="*/6", minute=30),
                      id="cart_abandonment", name="Cart Abandonment", replace_existing=True)
    logger.info("Scheduler configured: daily_summary, weekly_instagram_sync, weekly_report, weekly_feedback_learning, cart_abandonment")


def start_scheduler():
    """Start the scheduler."""
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started.")


def shutdown_scheduler():
    """Shutdown the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler shutdown.")
