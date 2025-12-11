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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: could init DB connections, load models, etc.
    print(f"Starting up {settings.APP_NAME}")
    print("✅ Using NEW LangGraph architecture")
    yield
    # Shutdown: close connections
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

@app.get("/", tags=["Root"])
async def root():
    return {"message": f"{settings.APP_NAME} v{settings.APP_VERSION} is running", "docs": "/docs"}
