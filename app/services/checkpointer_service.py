"""
Checkpointer Service: Manages async checkpointer lifecycle for LangGraph.

Provides fallback chain: Redis → Postgres → MemorySaver
Handles proper async context manager lifecycle for startup/shutdown.
"""
import logging
from typing import Optional, Any, Union
from contextlib import AsyncExitStack

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver

logger = logging.getLogger(__name__)


class CheckpointerService:
    """
    Manages checkpointer lifecycle with Redis → Postgres → Memory fallback chain.
    
    Usage:
        # In lifespan startup:
        await checkpointer_service.initialize()
        
        # In lifespan shutdown:
        await checkpointer_service.cleanup()
        
        # In graph compilation:
        checkpointer = checkpointer_service.get_checkpointer()
    """
    
    def __init__(self):
        self._checkpointer: Optional[BaseCheckpointSaver] = None
        self._exit_stack: Optional[AsyncExitStack] = None
        self._backend: str = "none"
    
    async def initialize(self) -> bool:
        """
        Initialize checkpointer with fallback chain: Redis → Postgres → MemorySaver.
        
        Returns:
            bool: True if a persistent checkpointer was initialized, False if using MemorySaver.
        """
        self._exit_stack = AsyncExitStack()
        
        # Try Redis first (fastest for production)
        if await self._try_redis():
            return True
        
        # Try Postgres as fallback
        if await self._try_postgres():
            return True
        
        # Final fallback: MemorySaver (volatile)
        self._use_memory_saver()
        return False
    
    async def _try_redis(self) -> bool:
        """Attempt to initialize Redis checkpointer."""
        try:
            from langgraph.checkpoint.redis.aio import AsyncRedisSaver
            from app.utils.config import settings
            
            redis_url = getattr(settings, 'REDIS_URL', None)
            if not redis_url:
                redis_host = getattr(settings, 'REDIS_HOST', 'localhost')
                redis_port = getattr(settings, 'REDIS_PORT', 6379)
                redis_url = f"redis://{redis_host}:{redis_port}"
            
            logger.info(f"Attempting Redis checkpointer: {redis_url}")
            
            # Enter the async context manager
            context_manager = AsyncRedisSaver.from_conn_string(redis_url)
            self._checkpointer = await self._exit_stack.enter_async_context(context_manager)
            
            # Setup tables/indexes
            await self._checkpointer.asetup()
            
            self._backend = "redis"
            logger.info(f"✅ Redis checkpointer initialized: {redis_url}")
            return True
            
        except ImportError:
            logger.debug("langgraph-checkpoint-redis not installed")
        except Exception as e:
            logger.warning(f"Redis checkpointer failed: {e}")
        
        return False
    
    async def _try_postgres(self) -> bool:
        """Attempt to initialize Postgres checkpointer."""
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from app.utils.config import settings
            import sys
            
            db_url = getattr(settings, 'DATABASE_URL', None)
            if not db_url:
                logger.debug("DATABASE_URL not configured")
                return False
            
            # Convert asyncpg URL to psycopg format if needed
            postgres_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
            
            # Windows compatibility: psycopg requires SelectorEventLoop
            if sys.platform == 'win32':
                import asyncio
                import selectors
                # Check if we can use selector event loop
                try:
                    selector = selectors.SelectSelector()
                    loop = asyncio.get_event_loop()
                    if not isinstance(loop, asyncio.SelectorEventLoop):
                        logger.warning("Windows: Cannot use Postgres with ProactorEventLoop. Skipping.")
                        return False
                except Exception:
                    pass
            
            logger.info("Attempting Postgres checkpointer...")
            
            # Enter the async context manager
            context_manager = AsyncPostgresSaver.from_conn_string(postgres_url)
            self._checkpointer = await self._exit_stack.enter_async_context(context_manager)
            
            # Setup tables
            await self._checkpointer.setup()
            
            self._backend = "postgres"
            logger.info("✅ Postgres checkpointer initialized")
            return True
            
        except ImportError:
            logger.debug("langgraph-checkpoint-postgres not installed")
        except Exception as e:
            logger.warning(f"Postgres checkpointer failed: {e}")
        
        return False
    
    def _use_memory_saver(self) -> None:
        """Fall back to volatile MemorySaver."""
        self._checkpointer = MemorySaver()
        self._backend = "memory"
        logger.info("Using MemorySaver (volatile) - state will not persist across restarts")
    
    def get_checkpointer(self) -> BaseCheckpointSaver:
        """
        Get the active checkpointer.
        
        Returns:
            BaseCheckpointSaver: The initialized checkpointer.
        
        Raises:
            RuntimeError: If service not initialized.
        """
        if self._checkpointer is None:
            # Return MemorySaver as fallback if not initialized
            logger.warning("Checkpointer not initialized, using MemorySaver")
            self._checkpointer = MemorySaver()
            self._backend = "memory"
        return self._checkpointer
    
    @property
    def backend(self) -> str:
        """Get the current backend name: 'redis', 'postgres', or 'memory'."""
        return self._backend
    
    @property
    def is_persistent(self) -> bool:
        """Check if using a persistent backend (not MemorySaver)."""
        return self._backend in ("redis", "postgres")
    
    async def cleanup(self) -> None:
        """Clean up checkpointer resources. Call during shutdown."""
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
                logger.info(f"✅ Checkpointer ({self._backend}) cleaned up")
            except Exception as e:
                logger.warning(f"Checkpointer cleanup error: {e}")
            finally:
                self._exit_stack = None
                self._checkpointer = None
                self._backend = "none"


# Singleton instance
checkpointer_service = CheckpointerService()
