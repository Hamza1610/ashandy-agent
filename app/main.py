# """
# Ashandy Agent: FastAPI application entry point.
# """
# from fastapi import FastAPI, Request
# from fastapi.middleware.cors import CORSMiddleware
# from contextlib import asynccontextmanager
# from slowapi import Limiter, _rate_limit_exceeded_handler
# from slowapi.util import get_remote_address
# from slowapi.errors import RateLimitExceeded
# from app.utils.config import settings
# from app.routers import health, webhooks
# import logging

# logger = logging.getLogger(__name__)

# # Rate limiter with custom key function (IP + user_id if available)
# def get_rate_limit_key(request: Request) -> str:
#     """Get rate limit key from user_id in body or IP address."""
#     # For webhooks, try to extract user_id from body
#     # For API calls, use IP address
#     return get_remote_address(request)

# limiter = Limiter(key_func=get_rate_limit_key)

# # Optional imports with graceful fallback
# try:
#     from app.routers import test_graph_router
#     TEST_ROUTER_AVAILABLE = True
# except ImportError:
#     TEST_ROUTER_AVAILABLE = False

# try:
#     from app.routers import image_test_router
#     IMAGE_TEST_AVAILABLE = True
# except ImportError:
#     IMAGE_TEST_AVAILABLE = False

# try:
#     from app.scheduler.cron_tasks import configure_scheduler, start_scheduler, shutdown_scheduler
#     SCHEDULER_AVAILABLE = True
# except ImportError:
#     SCHEDULER_AVAILABLE = False

# try:
#     from app.services.auto_migration import run_auto_migration
#     AUTO_MIGRATION_AVAILABLE = True
# except ImportError:
#     AUTO_MIGRATION_AVAILABLE = False

# try:
#     from app.services.response_cache_service import response_cache_service, COMMON_FAQS
#     CACHE_SERVICE_AVAILABLE = True
# except ImportError:
#     CACHE_SERVICE_AVAILABLE = False

# try:
#     from app.services.mcp_service import mcp_service
#     MCP_SERVICE_AVAILABLE = True
# except ImportError:
#     MCP_SERVICE_AVAILABLE = False


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     """Application lifecycle: startup and shutdown events."""
#     # Configure structured logging first
#     try:
#         from app.utils.structured_logging import configure_logging
#         configure_logging()
#     except ImportError:
#         pass  # Fall back to default logging
    
#     logger.info(f"Starting {settings.APP_NAME}")
    
#     if AUTO_MIGRATION_AVAILABLE:
#         try:
#             await run_auto_migration()
#             logger.info("✅ Database tables verified")
#         except Exception as e:
#             logger.warning(f"Auto-migration warning: {e}")
    
#     if SCHEDULER_AVAILABLE:
#         try:
#             configure_scheduler()
#             start_scheduler()
#             logger.info("✅ Scheduler started")
#         except Exception as e:
#             logger.warning(f"Scheduler failed: {e}")

#     # Initialize MCP connections (fixes shutdown errors)
#     if MCP_SERVICE_AVAILABLE:
#         try:
#             await mcp_service.initialize_all()
#         except Exception as e:
#             logger.error(f"MCP initialization failed: {e}")
    
#     # Warm response cache with common FAQs
#     if CACHE_SERVICE_AVAILABLE:
#         try:
#             await response_cache_service.warm_cache(COMMON_FAQS)
#             logger.info(f"✅ Response cache warmed with {len(COMMON_FAQS)} FAQs")
#         except Exception as e:
#             logger.warning(f"Cache warming failed: {e}")
    
#     # Initialize LangGraph checkpointer for state persistence
#     checkpointer_context = None
#     try:
#         from app.graphs.main_graph import app as graph_app
#         from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        
#         # Create checkpointer and setup tables
#         # Convert asyncpg URL to standard postgres URL (AsyncPostgresSaver uses psycopg internally)
#         postgres_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        
#         # Enter the async context manager and keep it alive for app lifetime
#         checkpointer_context = AsyncPostgresSaver.from_conn_string(postgres_url)
#         checkpointer = await checkpointer_context.__aenter__()
#         await checkpointer.setup()  # Create checkpoint tables
        
#         # Assign the actual saver instance to graph
#         graph_app.checkpointer = checkpointer
#         # Store context for cleanup on shutdown
#         app.state.checkpointer_context = checkpointer_context
#         logger.info("✅ Graph checkpointer initialized (state persistence enabled)")
#     except Exception as e:
#         logger.warning(f"Checkpointer initialization failed: {e}. State will not persist across sessions.")
#         checkpointer_context = None
    
#     yield
    
#     if SCHEDULER_AVAILABLE:
#         try:
#             shutdown_scheduler()
#         except:
#             pass
            
#     if MCP_SERVICE_AVAILABLE:
#         await mcp_service.cleanup()
    
#     # Cleanup checkpointer context
#     if hasattr(app.state, 'checkpointer_context') and app.state.checkpointer_context:
#         try:
#             await app.state.checkpointer_context.__aexit__(None, None, None)
#             logger.info("Checkpointer context cleaned up")
#         except Exception as e:
#             logger.warning(f"Checkpointer cleanup error: {e}")
        
#     logger.info(f"Shutting down {settings.APP_NAME}")


# app = FastAPI(
#     title=settings.APP_NAME,
#     version=settings.APP_VERSION,
#     lifespan=lifespan,
#     docs_url="/docs",
#     redoc_url="/redoc",
# )

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=settings.CORS_ORIGINS,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Rate limiting setup
# app.state.limiter = limiter
# app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# # Routers
# app.include_router(health.router, tags=["Health"])
# app.include_router(webhooks.router, prefix="/webhook", tags=["Webhooks"])

# if TEST_ROUTER_AVAILABLE:
#     app.include_router(test_graph_router.router, prefix="/api", tags=["Graph Testing"])

# if IMAGE_TEST_AVAILABLE:
#     app.include_router(image_test_router.router, prefix="/api", tags=["Image Testing"])


# @app.get("/", tags=["Root"])
# async def root():
#     return {"message": f"{settings.APP_NAME} v{settings.APP_VERSION} is running", "docs": "/docs"}









"""
Ashandy Agent: FastAPI application entry point.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.utils.config import settings
from app.routers import health, webhooks

logger = logging.getLogger(__name__)

# -------------------------------------------------
# Rate Limiting
# -------------------------------------------------

def get_rate_limit_key(request: Request) -> str:
    """Rate limit key based on client IP."""
    return get_remote_address(request)

limiter = Limiter(key_func=get_rate_limit_key)

# -------------------------------------------------
# Optional imports (graceful fallbacks)
# -------------------------------------------------

try:
    from app.routers import test_graph_router
    TEST_ROUTER_AVAILABLE = True
except ImportError:
    TEST_ROUTER_AVAILABLE = False

try:
    from app.routers import image_test_router
    IMAGE_TEST_AVAILABLE = True
except ImportError:
    IMAGE_TEST_AVAILABLE = False

try:
    from app.scheduler.cron_tasks import (
        configure_scheduler,
        start_scheduler,
        shutdown_scheduler,
    )
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False

try:
    from app.services.auto_migration import run_auto_migration
    AUTO_MIGRATION_AVAILABLE = True
except ImportError:
    AUTO_MIGRATION_AVAILABLE = False

try:
    from app.services.response_cache_service import (
        response_cache_service,
        COMMON_FAQS,
    )
    CACHE_SERVICE_AVAILABLE = True
except ImportError:
    CACHE_SERVICE_AVAILABLE = False

try:
    from app.services.mcp_service import mcp_service
    MCP_SERVICE_AVAILABLE = True
except ImportError:
    MCP_SERVICE_AVAILABLE = False


# -------------------------------------------------
# Lifespan (Render-safe)
# -------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle.
    IMPORTANT:
    - Do NOT block startup
    - Yield immediately so Render sees the open port
    """

    # Structured logging (optional)
    try:
        from app.utils.structured_logging import configure_logging
        configure_logging()
    except ImportError:
        pass

    logger.info("🚀 Lifespan entered")
    logger.info(f"Starting {settings.APP_NAME}")

    async def background_startup():
        # -------------------------
        # Auto migration
        # -------------------------
        if AUTO_MIGRATION_AVAILABLE:
            try:
                await run_auto_migration()
                logger.info("✅ Database tables verified")
            except Exception as e:
                logger.warning(f"Auto-migration failed: {e}")

        # -------------------------
        # Scheduler
        # -------------------------
        if SCHEDULER_AVAILABLE:
            try:
                configure_scheduler()
                start_scheduler()
                logger.info("✅ Scheduler started")
            except Exception as e:
                logger.warning(f"Scheduler failed: {e}")

        # -------------------------
        # MCP initialization
        # -------------------------
        if MCP_SERVICE_AVAILABLE:
            try:
                await mcp_service.initialize_all()
                logger.info("✅ MCP services initialized")
            except Exception as e:
                logger.warning(f"MCP initialization failed: {e}")

        # -------------------------
        # Cache warming
        # -------------------------
        if CACHE_SERVICE_AVAILABLE:
            try:
                await response_cache_service.warm_cache(COMMON_FAQS)
                logger.info(f"✅ Cache warmed with {len(COMMON_FAQS)} FAQs")
            except Exception as e:
                logger.warning(f"Cache warming failed: {e}")

        # -------------------------
        # LangGraph Checkpointer (optional, safe)
        # -------------------------
        try:
            from app.graphs.main_graph import app as graph_app
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

            postgres_url = settings.DATABASE_URL.replace(
                "postgresql+asyncpg://", "postgresql://"
            )

            checkpointer_context = AsyncPostgresSaver.from_conn_string(postgres_url)
            checkpointer = await checkpointer_context.__aenter__()
            await checkpointer.setup()

            graph_app.checkpointer = checkpointer
            app.state.checkpointer_context = checkpointer_context

            logger.info("✅ Graph checkpointer initialized")
        except Exception as e:
            logger.warning(
                f"Checkpointer initialization skipped: {e}. "
                "State will not persist across restarts."
            )

    # 🚀 Run startup work in background
    asyncio.create_task(background_startup())

    # ✅ IMPORTANT: yield immediately (this allows port binding)
    yield

    # -------------------------------------------------
    # Shutdown
    # -------------------------------------------------
    logger.info("Shutting down application")

    if SCHEDULER_AVAILABLE:
        try:
            shutdown_scheduler()
        except Exception:
            pass

    if MCP_SERVICE_AVAILABLE:
        try:
            await mcp_service.cleanup()
        except Exception:
            pass

    if hasattr(app.state, "checkpointer_context"):
        try:
            await app.state.checkpointer_context.__aexit__(None, None, None)
            logger.info("Checkpointer context cleaned up")
        except Exception as e:
            logger.warning(f"Checkpointer cleanup error: {e}")

    logger.info(f"Shut down {settings.APP_NAME}")


# -------------------------------------------------
# FastAPI App
# -------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# -------------------------------------------------
# Middleware
# -------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# -------------------------------------------------
# Routers
# -------------------------------------------------

app.include_router(health.router, tags=["Health"])
app.include_router(webhooks.router, prefix="/webhook", tags=["Webhooks"])

if TEST_ROUTER_AVAILABLE:
    app.include_router(
        test_graph_router.router,
        prefix="/api",
        tags=["Graph Testing"],
    )

if IMAGE_TEST_AVAILABLE:
    app.include_router(
        image_test_router.router,
        prefix="/api",
        tags=["Image Testing"],
    )


# -------------------------------------------------
# Root
# -------------------------------------------------

@app.get("/", tags=["Root"])
async def root():
    return {
        "message": f"{settings.APP_NAME} v{settings.APP_VERSION} is running",
        "docs": "/docs",
    }
