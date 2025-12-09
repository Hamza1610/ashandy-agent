from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.utils.config import settings
from app.routers import health, webhooks

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: could init DB connections, load models, etc.
    print(f"Starting up {settings.APP_NAME}")
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

@app.get("/", tags=["Root"])
async def root():
    return {"message": f"{settings.APP_NAME} v{settings.APP_VERSION} is running", "docs": "/docs"}
