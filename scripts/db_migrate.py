import asyncio
import sys
import os

# Add the project root directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.ext.asyncio import create_async_engine
from app.models.db_models import Base
from app.utils.config import settings
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_db():
    database_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(database_url, echo=True)
    
    async with engine.begin() as conn:
        logger.info("Creating tables...")
        await conn.run_sync(Base.metadata.drop_all) # Optional: reset DB for dev
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Tables created successfully!")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_db())
