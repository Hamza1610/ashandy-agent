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
    # Redis: either set REDIS_URL or host/port/db with username/password
    REDIS_URL: str | None = None
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_USERNAME: str | None = None
    REDIS_PASSWORD: str | None = None
    REDIS_CACHE_TTL: int = 3600

    # PINECONE
    PINECONE_API_KEY: Optional[str] = None
    PINECONE_ENVIRONMENT: Optional[str] = None
    PINECONE_INDEX_USER_MEMORY: str = None
    PINECONE_INDEX_PRODUCTS: str = None
    PINECONE_INDEX_PRODUCTS_TEXT: str = None

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
    
    # PINECONE
    PINECONE_API_KEY: Optional[str] = None
    PINECONE_ENV: str = "us-west-1-aws"
    PINECONE_INDEX_PRODUCTS_TEXT: str = "products-text-index"
    PINECONE_INDEX_PRODUCTS_IMAGE: str = "products-image-index"
    PINECONE_INDEX_USERS: str = "users-index"
    
    # ADMIN
    ADMIN_PHONE_NUMBERS: List[str] = []
    
    # GOOGLE MAPS & DELIVERY
    TOMTOM_API_KEY: Optional[str] = None
    SHOP_ADDRESS: str = "Ashandy Home of Cosmetics, Shop 9 &10, Divine Favor plaza, Railway Shed, Iyaganku, Dugbe Rd, Ibadan South West 200263, Oyo"
    PHPPOS_BASE_URL: Optional[str] = "https://ashandy.storeapp.com.ng/phppos/index.php/api/v1"

    # AI
    LLAMA_API_KEY: Optional[str] = None
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: str = "ashandy-agent"
    LANGCHAIN_TRACING_V2: str = "true"

    # SECURITY
    SECRET_KEY: str = "super-secret"
    CORS_ORIGINS: List[str] = ["*"]
    
    # BUSINESS
    TRANSPORT_FEE: float = 1500.0  # Delivery fee in Naira
    
    # Testing phone numbers (comment out when deploying)
    TEST_RIDER_PHONE: Optional[str] = "+2349026880099"  # Your test number
    TEST_MANAGER_PHONE: Optional[str] = "+2349026880099"  # Your test number
    # Production numbers (uncomment when deploying)
    # RIDER_PHONE: Optional[str] = None
    # MANAGER_PHONE: Optional[str] = None
    
    # ADMIN
    ADMIN_PHONE_NUMBERS: List[str] = []

    # Allow extra fields for flexibility
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore" 
    }

settings = Settings()



