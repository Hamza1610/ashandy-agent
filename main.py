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

try:
    from app.routers import payment_webhook, sms_test_router
    PAYMENT_WEBHOOK_AVAILABLE = True
except ImportError:
    PAYMENT_WEBHOOK_AVAILABLE = False

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

if IMAGE_TEST_AVAILABLE:
    app.include_router(image_test_router.router, prefix="/api", tags=["Image Testing"])
    print("✅ Image test endpoints available at /api/test/image/")

if PAYMENT_WEBHOOK_AVAILABLE:
    app.include_router(payment_webhook.router, prefix="/webhook", tags=["Payment Webhook"])
    app.include_router(sms_test_router.router, prefix="/api", tags=["SMS Testing"])
    print("✅ Paystack webhook available at /webhook/paystack/webhook")
    print("✅ SMS test endpoint available at /api/test/sms")

@app.get("/", tags=["Root"])
async def root():
    return {"message": f"{settings.APP_NAME} v{settings.APP_VERSION} is running", "docs": "/docs"}
