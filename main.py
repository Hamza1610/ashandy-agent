from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.utils.config import settings
from app.routers import health, webhooks
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

# Scheduler import
try:
    from app.scheduler.cron_tasks import configure_scheduler, start_scheduler, shutdown_scheduler
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False

# Auto-migration import
try:
    from app.services.auto_migration import run_auto_migration
    AUTO_MIGRATION_AVAILABLE = True
except ImportError:
    AUTO_MIGRATION_AVAILABLE = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: could init DB connections, load models, etc.
    print(f"Starting up {settings.APP_NAME}")
    print("✅ Using NEW LangGraph architecture (System 3.0)")
    
    # Run auto-migration (creates tables if they don't exist)
    if AUTO_MIGRATION_AVAILABLE:
        try:
            await run_auto_migration()
            print("✅ Database tables verified/created")
        except Exception as e:
            print(f"⚠️ Auto-migration warning: {e}")
    
    # Start scheduler if available
    if SCHEDULER_AVAILABLE:
        try:
            configure_scheduler()
            start_scheduler()
            print("✅ Scheduler started (daily summary, weekly sync, weekly report)")
        except Exception as e:
            print(f"⚠️ Scheduler failed to start: {e}")
    
    yield
    
    # Shutdown: close connections
    if SCHEDULER_AVAILABLE:
        try:
            shutdown_scheduler()
            print("✅ Scheduler shutdown complete")
        except:
            pass
    print(f"Shutting down {settings.APP_NAME}")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(health.router, tags=["Health"])
app.include_router(webhooks.router, prefix="/webhook", tags=["Webhooks"])

# Optional test router for development
if TEST_ROUTER_AVAILABLE:
    app.include_router(test_graph_router.router, prefix="/api", tags=["Graph Testing"])
    print("✅ Test endpoints available at /api/test/")

if IMAGE_TEST_AVAILABLE:
    app.include_router(image_test_router.router, prefix="/api", tags=["Image Testing"])
    print("✅ Image test endpoints available at /api/test/image/")

@app.get("/", tags=["Root"])
async def root():
    return {"message": f"{settings.APP_NAME} v{settings.APP_VERSION} is running", "docs": "/docs"}
