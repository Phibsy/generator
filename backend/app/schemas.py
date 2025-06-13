# backend/app/schemas.py
"""
📋 REELS GENERATOR - Pydantic Schemas
Request/Response models for API validation and serialization
"""

from pydantic import BaseModel, EmailStr, validator, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from .models import UserRole, ProjectStatus, Platform, VideoFormat

# ============================================================================
# BASE SCHEMAS
# ============================================================================

class TimestampMixin(BaseModel):
    """Mixin for timestamp fields"""
    created_at: datetime
    updated_at: Optional[datetime] = None

# ============================================================================
# USER SCHEMAS
# ============================================================================

class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    
    @validator('username')
    def username_alphanumeric(cls, v):
        """Validate username is alphanumeric with underscores"""
        import re
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Username must contain only letters, numbers, and underscores')
        return v

class UserCreate(UserBase):
    """Schema for user creation"""
    password: str = Field(..., min_length=8)

class UserLogin(BaseModel):
    """Schema for user login"""
    username: str  # Can be username or email
    password: str

class UserResponse(UserBase, TimestampMixin):
    """Schema for user response"""
    id: int
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    is_active: bool
    is_verified: bool
    role: UserRole
    subscription_plan: str
    videos_generated: int
    monthly_limit: int
    last_login: Optional[datetime] = None
    full_name: str
    can_generate_video: bool
    
    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    """Schema for user updates"""
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = None

# ============================================================================
# AUTHENTICATION SCHEMAS
# ============================================================================

class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserResponse

class TokenData(BaseModel):
    """Token payload data"""
    username: Optional[str] = None

# ============================================================================
# SOCIAL ACCOUNT SCHEMAS
# ============================================================================

class SocialAccountBase(BaseModel):
    """Base social account schema"""
    platform: Platform
    username: str
    
class SocialAccountCreate(SocialAccountBase):
    """Schema for social account creation"""
    platform_user_id: str
    access_token: str
    refresh_token: Optional[str] = None

class SocialAccountResponse(SocialAccountBase, TimestampMixin):
    """Schema for social account response"""
    id: int
    platform_user_id: str
    is_active: bool
    followers_count: int
    token_expires_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# ============================================================================
# PROJECT SCHEMAS
# ============================================================================

class ProjectBase(BaseModel):
    """Base project schema"""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    topic: Optional[str] = Field(None, max_length=200)
    target_audience: Optional[str] = Field(None, max_length=100)
    video_style: Optional[str] = Field(None, max_length=50)
    duration: int = Field(default=60, ge=15, le=180)  # 15 seconds to 3 minutes

class ProjectCreate(ProjectBase):
    """Schema for project creation"""
    voice_id: Optional[str] = None
    background_music: Optional[str] = None
    subtitle_style: Optional[Dict[str, Any]] = None

class ProjectUpdate(BaseModel):
    """Schema for project updates"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    topic: Optional[str] = Field(None, max_length=200)
    target_audience: Optional[str] = Field(None, max_length=100)
    video_style: Optional[str] = Field(None, max_length=50)
    duration: Optional[int] = Field(None, ge=15, le=180)
    voice_id: Optional[str] = None
    background_music: Optional[str] = None
    subtitle_style: Optional[Dict[str, Any]] = None

class ProjectResponse(ProjectBase, TimestampMixin):
    """Schema for project response"""
    id: int
    user_id: int
    status: ProjectStatus
    script: Optional[str] = None
    hashtags: Optional[List[str]] = None
    audio_file_path: Optional[str] = None
    video_file_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    processing_duration: Optional[float] = None
    error_message: Optional[str] = None
    voice_id: Optional[str] = None
    background_music: Optional[str] = None
    subtitle_style: Optional[Dict[str, Any]] = None
    is_processing: bool
    is_completed: bool
    
    class Config:
        from_attributes = True

# ============================================================================
# CONTENT GENERATION SCHEMAS
# ============================================================================

class ContentGenerationRequest(BaseModel):
    """Schema for content generation request"""
    topic: str = Field(..., min_length=3, max_length=200)
    target_audience: str = Field(..., min_length=3, max_length=100)
    video_style: str = Field(default="educational")
    duration: int = Field(default=60, ge=15, le=180)
    tone: str = Field(default="engaging")
    include_call_to_action: bool = Field(default=True)
    
class ContentGenerationResponse(BaseModel):
    """Schema for content generation response"""
    script: str
    hashtags: List[str]
    suggested_title: str
    estimated_duration: int
    content_score: float  # 0-1 quality score

# ============================================================================
# PUBLICATION SCHEMAS
# ============================================================================

class PublicationBase(BaseModel):
    """Base publication schema"""
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    scheduled_for: Optional[datetime] = None

class PublicationCreate(PublicationBase):
    """Schema for publication creation"""
    social_account_id: int

class PublicationResponse(PublicationBase, TimestampMixin):
    """Schema for publication response"""
    id: int
    project_id: int
    social_account_id: int
    platform_post_id: Optional[str] = None
    url: Optional[str] = None
    is_published: bool
    published_at: Optional[datetime] = None
    views: int
    likes: int
    comments: int
    shares: int
    engagement_rate: float
    
    class Config:
        from_attributes = True

# ============================================================================
# ANALYTICS SCHEMAS
# ============================================================================

class VideoAnalyticsResponse(TimestampMixin):
    """Schema for video analytics response"""
    id: int
    project_id: int
    generation_time: Optional[float] = None
    content_score: Optional[float] = None
    total_views: int
    total_likes: int
    total_comments: int
    total_shares: int
    avg_engagement_rate: float
    best_performing_platform: Optional[Platform] = None
    script_length: Optional[int] = None
    hashtag_count: Optional[int] = None
    sentiment_score: Optional[float] = None
    
    class Config:
        from_attributes = True

class DashboardStats(BaseModel):
    """Schema for dashboard statistics"""
    total_projects: int
    completed_projects: int
    processing_projects: int
    total_views: int
    total_likes: int
    avg_engagement_rate: float
    videos_this_month: int
    remaining_videos: int

# ============================================================================
# FILE UPLOAD SCHEMAS
# ============================================================================

class FileUploadResponse(BaseModel):
    """Schema for file upload response"""
    filename: str
    file_path: str
    file_size: int
    upload_url: Optional[str] = None  # S3 URL if using cloud storage

# ============================================================================
# ERROR SCHEMAS
# ============================================================================

class ErrorResponse(BaseModel):
    """Schema for error responses"""
    error: bool = True
    message: str
    status_code: int
    timestamp: float
    details: Optional[Dict[str, Any]] = None

class ValidationError(BaseModel):
    """Schema for validation errors"""
    field: str
    message: str
    invalid_value: Any

# ============================================================================
# WEBHOOK SCHEMAS
# ============================================================================

class PlatformWebhook(BaseModel):
    """Schema for platform webhook data"""
    platform: Platform
    post_id: str
    event_type: str
    data: Dict[str, Any]
    timestamp: datetime

# ============================================================================
# PAGINATION SCHEMAS
# ============================================================================

class PaginationParams(BaseModel):
    """Schema for pagination parameters"""
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)

class PaginatedResponse(BaseModel):
    """Schema for paginated responses"""
    items: List[Any]
    total: int
    page: int
    limit: int
    pages: int
    has_next: bool
    has_prev: bool

# Add to backend/app/schemas.py

# ============================================================================
# TEXT-TO-SPEECH SCHEMAS
# ============================================================================

class TTSRequest(BaseModel):
    """Schema for TTS generation request"""
    text: str = Field(..., min_length=1, max_length=5000)
    voice_id: str = Field(default="rachel")
    speed: float = Field(default=1.0, ge=0.5, le=2.0)

class TTSResponse(BaseModel):
    """Schema for TTS generation response"""
    audio_url: str
    duration: float
    provider: str
    voice_id: str
    file_key: str

class VoiceInfo(BaseModel):
    """Schema for voice information"""
    voice_id: str
    name: str
    description: str
    provider: str  # elevenlabs, polly, or both
    preview_url: str
    
class VoiceCloneRequest(BaseModel):
    """Schema for voice cloning request"""
    voice_name: str = Field(..., min_length=3, max_length=50)
    description: str = Field(..., max_length=200)
