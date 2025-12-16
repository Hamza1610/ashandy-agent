"""
Configuration module with environment-based settings.
Supports: development, staging, production
"""
from pydantic_settings import BaseSettings
from typing import List, Optional
from functools import lru_cache
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()


class BaseConfig(BaseSettings):
    """Base configuration shared across all environments."""
    
    # Application
    APP_NAME: str = "ashandy-agent"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ashandy_agent"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: str | None = None
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_USERNAME: str | None = None
    REDIS_PASSWORD: str | None = None
    REDIS_CACHE_TTL: int = 3600

    # Pinecone
    PINECONE_API_KEY: Optional[str] = None
    PINECONE_ENVIRONMENT: Optional[str] = None
    PINECONE_INDEX_USER_MEMORY: str = None
    PINECONE_INDEX_PRODUCTS: str = None
    PINECONE_INDEX_PRODUCTS_TEXT: str = None

    # Meta API
    META_WHATSAPP_TOKEN: Optional[str] = None
    META_WHATSAPP_PHONE_ID: Optional[str] = None
    META_WHATSAPP_BUSINESS_ID: Optional[str] = None
    META_VERIFY_TOKEN: str = None
    META_INSTAGRAM_TOKEN: Optional[str] = None
    META_INSTAGRAM_ACCOUNT_ID: Optional[str] = None
    INSTAGRAM_INGESTION_ENABLED: bool = True

    # Twilio (Fallback SMS)
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None

    # HuggingFace
    HUGGINGFACE_API_KEY: Optional[str] = None

    # Paystack
    PAYSTACK_SECRET_KEY: Optional[str] = None
    PAYSTACK_PUBLIC_KEY: Optional[str] = None
    PAYSTACK_WEBHOOK_SECRET: Optional[str] = None

    # POS
    POS_CONNECTOR_API_KEY: Optional[str] = None
    
    # Admin
    ADMIN_PHONE_NUMBERS: List[str] = []
    
    # Email/SMTP
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    ADMIN_EMAIL: Optional[str] = None

    # TomTom & Delivery
    TOMTOM_API_KEY: Optional[str] = None
    SHOP_ADDRESS: str = "Ashandy Home of Cosmetics, Shop 9 &10, Divine Favor plaza, Railway Shed, Iyaganku, Dugbe Rd, Ibadan South West 200263, Oyo"
    PHPPOS_BASE_URL: Optional[str] = "https://ashandy.storeapp.com.ng/phppos/index.php/api/v1"

    # AI Providers
    LLAMA_API_KEY: Optional[str] = None  # Groq (Primary)
    TOGETHER_API_KEY: Optional[str] = None  # Together AI (Fallback 1)
    OPENROUTER_API_KEY: Optional[str] = None  # OpenRouter (Fallback 2)
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: str = "ashandy-agent"
    LANGCHAIN_TRACING_V2: str = "true"

    # Security
    SECRET_KEY: str = "super-secret"
    CORS_ORIGINS: List[str] = ["*"]
    
    # Business
    TRANSPORT_FEE: float = 1500.0

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_PERIOD: str = "minute"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore"
    }


class DevelopmentConfig(BaseConfig):
    """Development environment configuration."""
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    
    # Use mock data in development
    USE_MOCK_DATA: bool = True
    
    # Test phone numbers for development
    RIDER_PHONE: Optional[str] = "+2349026880099"
    MANAGER_PHONE: Optional[str] = "+2349026880099"
    
    # Relaxed rate limits for testing
    RATE_LIMIT_REQUESTS: int = 1000
    
    # Verbose tracing
    LANGCHAIN_TRACING_V2: str = "true"


class ProductionConfig(BaseConfig):
    """Production environment configuration."""
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    LOG_LEVEL: str = "WARNING"
    
    # Use real data in production
    USE_MOCK_DATA: bool = False
    
    # Real phone numbers (set via env vars)
    RIDER_PHONE: Optional[str] = None
    MANAGER_PHONE: Optional[str] = None
    
    # Strict rate limits
    RATE_LIMIT_REQUESTS: int = 60
    
    # Disable verbose tracing in production
    LANGCHAIN_TRACING_V2: str = "false"
    
    # Stricter CORS in production
    CORS_ORIGINS: List[str] = [
        "https://ashandy.com",
        "https://www.ashandy.com"
    ]


class StagingConfig(BaseConfig):
    """Staging environment configuration."""
    ENVIRONMENT: str = "staging"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    USE_MOCK_DATA: bool = False
    RATE_LIMIT_REQUESTS: int = 100


@lru_cache()
def get_settings() -> BaseConfig:
    """
    Factory function that returns the appropriate config based on ENVIRONMENT.
    Uses lru_cache for singleton pattern.
    """
    env = os.getenv("ENVIRONMENT", "development").lower()
    
    config_map = {
        "development": DevelopmentConfig,
        "dev": DevelopmentConfig,
        "staging": StagingConfig,
        "stage": StagingConfig,
        "production": ProductionConfig,
        "prod": ProductionConfig,
    }
    
    config_class = config_map.get(env, DevelopmentConfig)
    return config_class()


# Default settings instance (for backward compatibility)
settings = get_settings()
