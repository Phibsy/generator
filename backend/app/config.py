# backend/app/config.py
"""
⚙️ REELS GENERATOR - Configuration Management
Pydantic-based settings with environment variable support
"""

from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import List, Optional
import os
from pathlib import Path

class Settings(BaseSettings):
    """Application settings with automatic environment variable loading"""
    
    # ========================================================================
    # BASIC APPLICATION SETTINGS
    # ========================================================================
    
    APP_NAME: str = "Reels Generator"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=True, env="DEBUG")
    
    # ========================================================================
    # SECURITY SETTINGS
    # ========================================================================
    
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    ALGORITHM: str = Field(default="HS256", env="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # ========================================================================
    # DATABASE SETTINGS
    # ========================================================================
    
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    POSTGRES_USER: str = Field(..., env="POSTGRES_USER")
    POSTGRES_PASSWORD: str = Field(..., env="POSTGRES_PASSWORD") 
    POSTGRES_DB: str = Field(..., env="POSTGRES_DB")
    
    # ========================================================================
    # REDIS SETTINGS
    # ========================================================================
    
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    
    # ========================================================================
    # API KEYS
    # ========================================================================
    
    OPENAI_API_KEY: str = Field(..., env="OPENAI_API_KEY")
    ELEVENLABS_API_KEY: str = Field(..., env="ELEVENLABS_API_KEY")
    
    # ========================================================================
    # AWS SETTINGS
    # ========================================================================
    
    AWS_ACCESS_KEY_ID: str = Field(..., env="AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: str = Field(..., env="AWS_SECRET_ACCESS_KEY")
    AWS_REGION: str = Field(default="eu-central-1", env="AWS_REGION")
    S3_BUCKET_NAME: str = Field(..., env="S3_BUCKET_NAME")
    
    # ========================================================================
    # SOCIAL MEDIA API SETTINGS
    # ========================================================================
    
    YOUTUBE_CLIENT_ID: Optional[str] = Field(default=None, env="YOUTUBE_CLIENT_ID")
    YOUTUBE_CLIENT_SECRET: Optional[str] = Field(default=None, env="YOUTUBE_CLIENT_SECRET")
    INSTAGRAM_CLIENT_ID: Optional[str] = Field(default=None, env="INSTAGRAM_CLIENT_ID")
    INSTAGRAM_CLIENT_SECRET: Optional[str] = Field(default=None, env="INSTAGRAM_CLIENT_SECRET")
    
    # ========================================================================
    # CORS & SECURITY
    # ========================================================================
    
    ALLOWED_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        env="ALLOWED_ORIGINS"
    )
    ALLOWED_HOSTS: List[str] = Field(
        default=["localhost", "127.0.0.1"],
        env="ALLOWED_HOSTS"
    )
    
    # ========================================================================
    # FILE PROCESSING
    # ========================================================================
    
    MAX_UPLOAD_SIZE: int = Field(default=100 * 1024 * 1024, env="MAX_UPLOAD_SIZE")  # 100MB
    ALLOWED_VIDEO_FORMATS: List[str] = Field(
        default=["mp4", "mov", "avi", "mkv"],
        env="ALLOWED_VIDEO_FORMATS"
    )
    ALLOWED_AUDIO_FORMATS: List[str] = Field(
        default=["mp3", "wav", "m4a"],
        env="ALLOWED_AUDIO_FORMATS"
    )
    
    # ========================================================================
    # CONTENT GENERATION
    # ========================================================================
    
    DEFAULT_VIDEO_DURATION: int = Field(default=60, env="DEFAULT_VIDEO_DURATION")  # seconds
    MAX_VIDEO_DURATION: int = Field(default=180, env="MAX_VIDEO_DURATION")  # 3 minutes
    DEFAULT_VOICE_ID: str = Field(default="21m00Tcm4TlvDq8ikWAM", env="DEFAULT_VOICE_ID")  # ElevenLabs Rachel
    
    # ========================================================================
    # MONITORING
    # ========================================================================
    
    SENTRY_DSN: Optional[str] = Field(default=None, env="SENTRY_DSN")
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    
    # ========================================================================
    # VALIDATORS
    # ========================================================================
    
    @validator("ALLOWED_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("ALLOWED_HOSTS", pre=True) 
    def parse_allowed_hosts(cls, v):
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v
    
    @validator("ALLOWED_VIDEO_FORMATS", pre=True)
    def parse_video_formats(cls, v):
        if isinstance(v, str):
            return [fmt.strip().lower() for fmt in v.split(",")]
        return v
    
    @validator("ALLOWED_AUDIO_FORMATS", pre=True)
    def parse_audio_formats(cls, v):
        if isinstance(v, str):
            return [fmt.strip().lower() for fmt in v.split(",")]
        return v
    
    # ========================================================================
    # COMPUTED PROPERTIES
    # ========================================================================
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"
    
    @property
    def media_directory(self) -> Path:
        return Path("media")
    
    @property
    def temp_directory(self) -> Path:
        return Path("temp")
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Initialize settings
settings = Settings()

# ============================================================================
# backend/app/database.py
"""
🗄️ REELS GENERATOR - Database Configuration
SQLAlchemy async setup with connection pooling
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import StaticPool
from typing import AsyncGenerator
import logging

from .config import settings

logger = logging.getLogger(__name__)

# ============================================================================
# ENGINE CONFIGURATION
# ============================================================================

# Convert sync database URL to async
if settings.DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
else:
    ASYNC_DATABASE_URL = settings.DATABASE_URL

# Create async engine with connection pooling
engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=settings.DEBUG,  # Log SQL queries in debug mode
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Validate connections before use
    pool_recycle=3600,   # Recycle connections after 1 hour
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base class for models
Base = declarative_base()

# ============================================================================
# DATABASE DEPENDENCY
# ============================================================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Database dependency for FastAPI routes
    Provides async database session with automatic cleanup
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# ============================================================================
# DATABASE UTILITIES
# ============================================================================

async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        # Import all models to ensure they're registered
        from . import models  # noqa
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database tables created")

async def drop_db():
    """Drop all database tables (use with caution!)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.warning("🗑️ All database tables dropped")

# ============================================================================
# HEALTH CHECK
# ============================================================================

async def check_db_connection() -> bool:
    """Check if database is accessible"""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute("SELECT 1")
            return True
    except Exception as e:
        logger.error(f"💥 Database connection failed: {e}")
        return False
