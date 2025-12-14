"""
Scheduler: Autonomous task scheduling using APScheduler.
Runs scheduled jobs for weekly reports and Instagram sync.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.services.summary_service import summary_service
from app.services.ingestion_service import ingestion_service
from app.tools.report_tool import generate_comprehensive_report
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler()


async def daily_summary_job():
    """
    Compute daily summary at midnight.
    Aggregates all messages and orders from the previous day.
    """
    try:
        yesterday = (datetime.now() - timedelta(days=1)).date()
        logger.info(f"Running daily summary job for {yesterday}")
        await summary_service.compute_daily_summary(date=yesterday)
        logger.info("Daily summary job completed successfully.")
    except Exception as e:
        logger.error(f"Daily summary job failed: {e}")


async def weekly_instagram_sync_job():
    """
    Sync products from Instagram every Sunday at 2 AM.
    """
    try:
        logger.info("Running weekly Instagram sync job...")
        result = await ingestion_service.sync_instagram_products(limit=50)
        logger.info(f"Instagram sync completed: {result}")
    except Exception as e:
        logger.error(f"Instagram sync job failed: {e}")


async def weekly_report_job():
    """
    Generate and store weekly report every Monday at 3 AM.
    This can also be sent to the Manager via WhatsApp if configured.
    """
    try:
        logger.info("Running weekly report generation job...")
        
        # Generate report for the past 7 days
        result = await generate_comprehensive_report.ainvoke({
            "start_date": "last week",
            "end_date": "today"
        })
        
        # Log the report (in production, this could be stored or sent)
        logger.info(f"Weekly report generated. Length: {len(result)} chars")
        
        # TODO: Optionally send to Manager via WhatsApp
        # from app.tools.admin_tools import relay_message_to_customer
        # await relay_message_to_customer.ainvoke({
        #     "customer_id": settings.MANAGER_WHATSAPP_ID,
        #     "message": result[:4000]  # WhatsApp message limit
        # })
        
    except Exception as e:
        logger.error(f"Weekly report job failed: {e}")


def configure_scheduler():
    """
    Configure all scheduled jobs.
    Call this during application startup.
    """
    # Daily summary at midnight
    scheduler.add_job(
        daily_summary_job,
        CronTrigger(hour=0, minute=0),
        id="daily_summary",
        name="Compute Daily Summary",
        replace_existing=True
    )
    
    # Weekly Instagram sync - Sunday 2 AM
    scheduler.add_job(
        weekly_instagram_sync_job,
        CronTrigger(day_of_week="sun", hour=2, minute=0),
        id="weekly_instagram_sync",
        name="Weekly Instagram Sync",
        replace_existing=True
    )
    
    # Weekly report - Monday 3 AM
    scheduler.add_job(
        weekly_report_job,
        CronTrigger(day_of_week="mon", hour=3, minute=0),
        id="weekly_report",
        name="Weekly Report Generation",
        replace_existing=True
    )
    
    logger.info("Scheduler configured with 3 jobs: daily_summary, weekly_instagram_sync, weekly_report")


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
