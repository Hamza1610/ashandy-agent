"""
Ashandy Agent: FastAPI application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.utils.config import settings
from app.routers import health, webhooks
import logging

logger = logging.getLogger(__name__)

# Optional imports with graceful fallback
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
    from app.scheduler.cron_tasks import configure_scheduler, start_scheduler, shutdown_scheduler
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False

try:
    from app.services.auto_migration import run_auto_migration
    AUTO_MIGRATION_AVAILABLE = True
except ImportError:
    AUTO_MIGRATION_AVAILABLE = False

try:
    from app.services.response_cache_service import response_cache_service, COMMON_FAQS
    CACHE_SERVICE_AVAILABLE = True
except ImportError:
    CACHE_SERVICE_AVAILABLE = False

try:
    from app.services.mcp_service import mcp_service
    MCP_SERVICE_AVAILABLE = True
except ImportError:
    MCP_SERVICE_AVAILABLE = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: startup and shutdown events."""
    logger.info(f"Starting {settings.APP_NAME}")
    
    if AUTO_MIGRATION_AVAILABLE:
        try:
            await run_auto_migration()
            logger.info("✅ Database tables verified")
        except Exception as e:
            logger.warning(f"Auto-migration warning: {e}")
    
    if SCHEDULER_AVAILABLE:
        try:
            configure_scheduler()
            start_scheduler()
            logger.info("✅ Scheduler started")
        except Exception as e:
            logger.warning(f"Scheduler failed: {e}")

    # Initialize MCP connections (fixes shutdown errors)
    if MCP_SERVICE_AVAILABLE:
        try:
            await mcp_service.initialize_all()
        except Exception as e:
            logger.error(f"MCP initialization failed: {e}")
    
    # Warm response cache with common FAQs
    if CACHE_SERVICE_AVAILABLE:
        try:
            await response_cache_service.warm_cache(COMMON_FAQS)
            logger.info(f"✅ Response cache warmed with {len(COMMON_FAQS)} FAQs")
        except Exception as e:
            logger.warning(f"Cache warming failed: {e}")
    
    yield
    
    if SCHEDULER_AVAILABLE:
        try:
            shutdown_scheduler()
        except:
            pass
            
    if MCP_SERVICE_AVAILABLE:
        await mcp_service.cleanup()
        
    logger.info(f"Shutting down {settings.APP_NAME}")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router, tags=["Health"])
app.include_router(webhooks.router, prefix="/webhook", tags=["Webhooks"])

if TEST_ROUTER_AVAILABLE:
    app.include_router(test_graph_router.router, prefix="/api", tags=["Graph Testing"])

if IMAGE_TEST_AVAILABLE:
    app.include_router(image_test_router.router, prefix="/api", tags=["Image Testing"])


@app.get("/", tags=["Root"])
async def root():
    return {"message": f"{settings.APP_NAME} v{settings.APP_VERSION} is running", "docs": "/docs"}
