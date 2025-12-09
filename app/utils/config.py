from pydantic_settings import BaseSettings
from typing import List, Optional
from dotenv import load_dotenv
import os

# Explicitly load .env file into os.environ so Pydantic picks it up
load_dotenv()

class Settings(BaseSettings):
    APP_NAME: str = "ashandy-agent"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # POSTGRES
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ashandy_agent" # Default or override
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # REDIS
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 3600

    # PINECONE
    PINECONE_API_KEY: Optional[str] = None
    PINECONE_ENVIRONMENT: Optional[str] = None
    PINECONE_INDEX_USER_MEMORY: str = "user_memory"
    PINECONE_INDEX_PRODUCTS: str = "products"

    # META API
    META_WHATSAPP_TOKEN: Optional[str] = None
    META_WHATSAPP_PHONE_ID: Optional[str] = None
    META_WHATSAPP_BUSINESS_ID: Optional[str] = None
    META_VERIFY_TOKEN: str = "token"
    META_INSTAGRAM_TOKEN: Optional[str] = None
    META_INSTAGRAM_ACCOUNT_ID: Optional[str] = None

    # TWILIO (Fallback)
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None

    # HUGGINGFACE (Visual API)
    HUGGINGFACE_API_KEY: Optional[str] = None

    # PAYSTACK
    PAYSTACK_SECRET_KEY: Optional[str] = None
    PAYSTACK_PUBLIC_KEY: Optional[str] = None
    PAYSTACK_WEBHOOK_SECRET: Optional[str] = None

    # POS
    POS_CONNECTOR_API_KEY: Optional[str] = None

    # AI
    LLAMA_API_KEY: Optional[str] = None
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: str = "ashandy-agent"
    LANGCHAIN_TRACING_V2: str = "true"

    # SECURITY
    SECRET_KEY: str = "super-secret"
    CORS_ORIGINS: List[str] = ["*"]

    # Allow extra fields for flexibility
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore" 
    }

settings = Settings()



