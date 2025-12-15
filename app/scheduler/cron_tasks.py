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
    logger.info("Scheduler configured: daily_summary, weekly_instagram_sync, weekly_report, weekly_feedback_learning")


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
