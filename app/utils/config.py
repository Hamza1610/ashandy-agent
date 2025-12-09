from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    APP_NAME: str = "ashandy-agent"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # POSTGRES
    DATABASE_URL: str = "postgresql+asyncpg://postgres:hamza@localhost:5432/Ashandy-agent"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # REDIS
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 3600

    # PINECONE
    PINECONE_API_KEY: str = ""
    PINECONE_ENVIRONMENT: str = "us-west1-gcp"
    PINECONE_INDEX_USER_MEMORY: str = "user-semantic-memory"
    PINECONE_INDEX_PRODUCTS: str = "product-embeddings"

    # META API
    META_WHATSAPP_TOKEN: str = ""
    META_WHATSAPP_PHONE_ID: str = ""
    META_WHATSAPP_BUSINESS_ID: str = ""
    META_VERIFY_TOKEN: str = "sabi_verify_token"
    META_INSTAGRAM_TOKEN: str = ""
    META_INSTAGRAM_ACCOUNT_ID: str = ""

    # PAYSTACK
    PAYSTACK_SECRET_KEY: str = ""
    PAYSTACK_PUBLIC_KEY: str = ""
    PAYSTACK_WEBHOOK_SECRET: str = ""

    # POS
    POS_CONNECTOR_API_KEY: str = ""

    # AI
    LLAMA_API_KEY: str = "" # THIS SHOULD BE groq api key instead
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "ashandy-agent"
    LANGCHAIN_TRACING_V2: str = "true"

    # SECURITY
    SECRET_KEY: str = "super-secret"
    CORS_ORIGINS: List[str] = ["*"]
    
    # ADMIN
    ADMIN_PHONE_NUMBERS: List[str] = []

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore" 
    }

settings = Settings()
