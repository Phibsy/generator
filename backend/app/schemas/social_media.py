# backend/app/schemas/social_media.py
"""
📋 REELS GENERATOR - Social Media Schemas
Request/Response models for social media integration
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from ..models import Platform

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
    token_expires_at: Optional[datetime] = None

class SocialAccountResponse(SocialAccountBase):
    """Schema for social account response"""
    id: int
    platform_user_id: str
    is_active: bool
    followers_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# ============================================================================
# PUBLISHING SCHEMAS
# ============================================================================

class PublishRequest(BaseModel):
    """Request to publish video to platforms"""
    platforms: List[str] = Field(..., min_items=1)
    title: Optional[str] = None
    description: Optional[str] = None
    hashtags: Optional[List[str]] = None
    platform_settings: Optional[Dict[str, Any]] = None
    
    @validator('platforms')
    def validate_platforms(cls, v):
        valid_platforms = ['youtube', 'instagram', 'tiktok']
        for platform in v:
            if platform not in valid_platforms:
                raise ValueError(f'Invalid platform: {platform}')
        return v

class SchedulePublishRequest(PublishRequest):
    """Request to schedule publication"""
    scheduled_for: datetime
    
    @validator('scheduled_for')
    def validate_future_date(cls, v):
        if v <= datetime.utcnow():
            raise ValueError('Scheduled time must be in the future')
        return v

class PublishResponse(BaseModel):
    """Response for publishing operation"""
    successful: List[Dict[str, Any]]
    failed: List[Dict[str, Any]]
    scheduled: List[Dict[str, Any]]

class PublicationResponse(BaseModel):
    """Schema for publication response"""
    id: int
    project_id: int
    social_account_id: int
    platform: Platform
    platform_post_id: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    is_published: bool
    published_at: Optional[datetime] = None
    scheduled_for: Optional[datetime] = None
    views: int
    likes: int
    comments: int
    shares: int
    engagement_rate: float
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# ============================================================================
# ANALYTICS SCHEMAS
# ============================================================================

class PlatformAnalytics(BaseModel):
    """Platform-specific analytics"""
    platform: Platform
    account_id: int
    period: str
    metrics: Dict[str, Any]

class VideoAnalyticsUpdate(BaseModel):
    """Analytics update from platform"""
    platform_post_id: str
    views: Optional[int] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None
    impressions: Optional[int] = None
    saves: Optional[int] = None

class AccountAnalytics(BaseModel):
    """Account-level analytics"""
    account_id: int
    platform: Platform
    followers_count: int
    total_views: int
    total_likes: int
    engagement_rate: float
    top_posts: List[Dict[str, Any]]
    growth_rate: float
    period: str

# ============================================================================
# WEBHOOK SCHEMAS
# ============================================================================

class YouTubeWebhook(BaseModel):
    """YouTube webhook payload"""
    channel_id: str
    video_id: str
    event_type: str
    data: Dict[str, Any]

class InstagramWebhook(BaseModel):
    """Instagram webhook payload"""
    object: str
    entry: List[Dict[str, Any]]

class TikTokWebhook(BaseModel):
    """TikTok webhook payload"""
    event_type: str
    object_id: str
    data: Dict[str, Any]

# ============================================================================
# CONNECTION SCHEMAS
# ============================================================================

class PlatformConnection(BaseModel):
    """Platform connection status"""
    platform: Platform
    connected: bool
    account: Optional[SocialAccountResponse] = None
    features: List[str]
    limits: Dict[str, Any]

class ConnectionStatus(BaseModel):
    """Overall connection status"""
    platforms: List[PlatformConnection]
    total_connected: int
    available_platforms: List[str]
