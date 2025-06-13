# backend/app/models.py
"""
🏗️ REELS GENERATOR - Database Models
SQLAlchemy models for all application entities
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey, Enum as SQLEnum, Float
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum
import uuid

from .database import Base

# ============================================================================
# ENUMS
# ============================================================================

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    PREMIUM = "premium"

class ProjectStatus(str, Enum):
    DRAFT = "draft"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PUBLISHED = "published"

class VideoFormat(str, Enum):
    MP4 = "mp4"
    MOV = "mov"
    AVI = "avi"

class Platform(str, Enum):
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"

# ============================================================================
# USER MODEL
# ============================================================================

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    # Profile Information
    first_name = Column(String(100))
    last_name = Column(String(100))
    avatar_url = Column(String(500))
    bio = Column(Text)
    
    # Account Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    role = Column(SQLEnum(UserRole), default=UserRole.USER)
    
    # Subscription & Limits
    subscription_plan = Column(String(50), default="free")
    videos_generated = Column(Integer, default=0)
    monthly_limit = Column(Integer, default=10)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))
    
    # Relationships
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    social_accounts = relationship("SocialAccount", back_populates="user", cascade="all, delete-orphan")
    
    @hybrid_property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    @hybrid_property
    def can_generate_video(self):
        """Check if user can generate more videos this month"""
        return self.videos_generated < self.monthly_limit
    
    def __repr__(self):
        return f"<User(username='{self.username}', email='{self.email}')>"

# ============================================================================
# SOCIAL ACCOUNT MODEL
# ============================================================================

class SocialAccount(Base):
    __tablename__ = "social_accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    platform = Column(SQLEnum(Platform), nullable=False)
    platform_user_id = Column(String(100), nullable=False)
    username = Column(String(100), nullable=False)
    
    # OAuth Tokens
    access_token = Column(Text)
    refresh_token = Column(Text)
    token_expires_at = Column(DateTime)
    
    # Account Info
    is_active = Column(Boolean, default=True)
    followers_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="social_accounts")
    publications = relationship("Publication", back_populates="social_account")
    
    def __repr__(self):
        return f"<SocialAccount(platform='{self.platform}', username='{self.username}')>"

# ============================================================================
# PROJECT MODEL
# ============================================================================

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Basic Info
    title = Column(String(200), nullable=False)
    description = Column(Text)
    status = Column(SQLEnum(ProjectStatus), default=ProjectStatus.DRAFT)
    
    # Content Configuration
    topic = Column(String(200))
    target_audience = Column(String(100))
    video_style = Column(String(50))  # gaming, educational, entertainment
    duration = Column(Integer, default=60)  # seconds
    
    # Generated Content
    script = Column(Text)
    hashtags = Column(JSON)  # List of hashtags
    
    # File Paths
    audio_file_path = Column(String(500))
    video_file_path = Column(String(500))
    thumbnail_path = Column(String(500))
    
    # Processing Info
    processing_started_at = Column(DateTime)
    processing_completed_at = Column(DateTime)
    error_message = Column(Text)
    
    # Settings
    voice_id = Column(String(100))  # ElevenLabs voice ID
    background_music = Column(String(200))
    subtitle_style = Column(JSON)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="projects")
    publications = relationship("Publication", back_populates="project")
    analytics = relationship("VideoAnalytics", back_populates="project", uselist=False)
    
    @hybrid_property
    def is_processing(self):
        return self.status == ProjectStatus.PROCESSING
    
    @hybrid_property
    def is_completed(self):
        return self.status == ProjectStatus.COMPLETED
    
    @hybrid_property
    def processing_duration(self):
        if self.processing_started_at and self.processing_completed_at:
            return (self.processing_completed_at - self.processing_started_at).total_seconds()
        return None
    
    def __repr__(self):
        return f"<Project(title='{self.title}', status='{self.status}')>"

# ============================================================================
# PUBLICATION MODEL
# ============================================================================

class Publication(Base):
    __tablename__ = "publications"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    social_account_id = Column(Integer, ForeignKey("social_accounts.id"), nullable=False)
    
    # Publication Info
    platform_post_id = Column(String(100))  # ID from the platform
    url = Column(String(500))
    title = Column(String(200))
    description = Column(Text)
    
    # Status
    is_published = Column(Boolean, default=False)
    published_at = Column(DateTime)
    scheduled_for = Column(DateTime)
    
    # Performance (updated via webhooks)
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    project = relationship("Project", back_populates="publications")
    social_account = relationship("SocialAccount", back_populates="publications")
    
    @hybrid_property
    def engagement_rate(self):
        if self.views > 0:
            return ((self.likes + self.comments + self.shares) / self.views) * 100
        return 0
    
    def __repr__(self):
        return f"<Publication(platform_post_id='{self.platform_post_id}', views={self.views})>"

# ============================================================================
# VIDEO ANALYTICS MODEL
# ============================================================================

class VideoAnalytics(Base):
    __tablename__ = "video_analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    
    # Generation Metrics
    generation_time = Column(Float)  # seconds
    content_score = Column(Float)    # AI-generated quality score
    
    # Performance Metrics (aggregated from publications)
    total_views = Column(Integer, default=0)
    total_likes = Column(Integer, default=0)
    total_comments = Column(Integer, default=0)
    total_shares = Column(Integer, default=0)
    
    # Engagement Analysis
    avg_engagement_rate = Column(Float, default=0.0)
    best_performing_platform = Column(SQLEnum(Platform))
    
    # Content Analysis
    script_length = Column(Integer)  # characters
    hashtag_count = Column(Integer)
    sentiment_score = Column(Float)  # -1 to 1
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    project = relationship("Project", back_populates="analytics")
    
    def __repr__(self):
        return f"<VideoAnalytics(project_id={self.project_id}, total_views={self.total_views})>"

# ============================================================================
# backend/app/api/auth.py
"""
🔐 REELS GENERATOR - Authentication API
JWT-based authentication with registration, login, and user management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import re

from ..database import get_db
from ..models import User, UserRole
from ..config import settings
from ..schemas import UserCreate, UserResponse, Token, UserLogin

# Initialize router
router = APIRouter()

# Security
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ============================================================================
# PASSWORD UTILITIES
# ============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

def validate_password(password: str) -> bool:
    """Validate password strength"""
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    return True

# ============================================================================
# JWT UTILITIES
# ============================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Get user from database
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user"""
    
    # Validate password strength
    if not validate_password(user_data.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters with uppercase, lowercase, and number"
        )
    
    # Check if user already exists
    result = await db.execute(
        select(User).where(
            (User.email == user_data.email) | (User.username == user_data.username)
        )
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        if existing_user.email == user_data.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        first_name=user_data.first_name,
        last_name=user_data.last_name
    )
    
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    return db_user

@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Login user and return JWT token"""
    
    # Find user by email or username
    result = await db.execute(
        select(User).where(
            (User.email == user_data.username) | (User.username == user_data.username)
        )
    )
    user = result.scalar_one_or_none()
    
    # Verify user and password
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account"
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user
    }

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """Get current user information"""
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: dict = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user information"""
    
    # Update allowed fields
    allowed_fields = ["first_name", "last_name", "bio", "avatar_url"]
    for field, value in user_update.items():
        if field in allowed_fields and hasattr(current_user, field):
            setattr(current_user, field, value)
    
    current_user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(current_user)
    
    return current_user

@router.post("/logout")
async def logout():
    """Logout user (client should discard token)"""
    return {"message": "Successfully logged out"}
