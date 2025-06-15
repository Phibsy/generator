#### `backend/app/api/social_media.py`
```python
"""
📱 REELS GENERATOR - Social Media API
Endpoints for platform connections and publishing
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any, Optional
import logging
import uuid
from datetime import datetime

from ..database import get_db
from ..models import User, SocialAccount, Platform, Publication
from ..schemas.social_media import (
    SocialAccountResponse,
    PublishRequest,
    PublishResponse,
    PlatformAnalytics,
    SchedulePublishRequest
)
from ..services.social_media import (
    youtube_service,
    instagram_service,
    tiktok_service,
    publishing_service
)
from .auth import get_current_active_user

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()

# ============================================================================
# OAUTH ENDPOINTS
# ============================================================================

@router.get("/connect/{platform}")
async def get_oauth_url(
    platform: Platform,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, str]:
    """Get OAuth URL for platform connection"""
    
    # Generate state for CSRF protection
    state = f"{current_user.id}:{uuid.uuid4()}"
    
    # Store state in Redis for verification
    from ..services.cache import cache_service
    await cache_service.set(f"oauth_state:{state}", current_user.id, expire=600)
    
    # Get platform-specific OAuth URL
    if platform == Platform.YOUTUBE:
        auth_url = youtube_service.get_auth_url(state)
    elif platform == Platform.INSTAGRAM:
        auth_url = instagram_service.get_auth_url(state)
    elif platform == Platform.TIKTOK:
        auth_url = tiktok_service.get_auth_url(state)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported platform: {platform}"
        )
    
    return {
        "auth_url": auth_url,
        "platform": platform.value
    }

@router.post("/callback/{platform}")
async def handle_oauth_callback(
    platform: Platform,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> SocialAccountResponse:
    """Handle OAuth callback from platform"""
    
    # Verify state
    from ..services.cache import cache_service
    stored_user_id = await cache_service.get(f"oauth_state:{state}")
    
    if not stored_user_id or int(stored_user_id) != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state"
        )
    
    # Clear state
    await cache_service.delete(f"oauth_state:{state}")
    
    try:
        # Exchange code for tokens
        if platform == Platform.YOUTUBE:
            auth_data = await youtube_service.handle_callback(code)
            platform_user_id = auth_data['channel_id']
            username = auth_data['channel_title']
            
        elif platform == Platform.INSTAGRAM:
            auth_data = await instagram_service.handle_callback(code)
            platform_user_id = auth_data['instagram_business_account_id']
            username = auth_data['username']
            
        elif platform == Platform.TIKTOK:
            auth_data = await tiktok_service.handle_callback(code)
            platform_user_id = auth_data['open_id']
            username = auth_data['username']
        
        else:
            raise ValueError(f"Unsupported platform: {platform}")
        
        # Check if account already exists
        result = await db.execute(
            select(SocialAccount).where(
                SocialAccount.user_id == current_user.id,
                SocialAccount.platform == platform,
                SocialAccount.platform_user_id == platform_user_id
            )
        )
        social_account = result.scalar_one_or_none()
        
        if social_account:
            # Update existing account
            social_account.access_token = auth_data['access_token']
            social_account.refresh_token = auth_data.get('refresh_token')
            social_account.token_expires_at = auth_data.get('token_expires_at')
            social_account.is_active = True
            social_account.followers_count = auth_data.get('followers_count', 0)
        else:
            # Create new account
            social_account = SocialAccount(
                user_id=current_user.id,
                platform=platform,
                platform_user_id=platform_user_id,
                username=username,
                access_token=auth_data['access_token'],
                refresh_token=auth_data.get('refresh_token'),
                token_expires_at=auth_data.get('token_expires_at'),
                followers_count=auth_data.get('followers_count', 0)
            )
            db.add(social_account)
        
        await db.commit()
        await db.refresh(social_account)
        
        return social_account
        
    except Exception as e:
        logger.error(f"OAuth callback failed for {platform}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect {platform} account"
        )

# ============================================================================
# ACCOUNT MANAGEMENT
# ============================================================================

@router.get("/accounts", response_model=List[SocialAccountResponse])
async def get_connected_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> List[SocialAccountResponse]:
    """Get user's connected social accounts"""
    
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.user_id == current_user.id,
            SocialAccount.is_active == True
        )
    )
    accounts = result.scalars().all()
    
    return accounts

@router.delete("/accounts/{account_id}")
async def disconnect_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, str]:
    """Disconnect a social account"""
    
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.id == account_id,
            SocialAccount.user_id == current_user.id
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Social account not found"
        )
    
    # Soft delete - keep record but mark inactive
    account.is_active = False
    account.access_token = None
    account.refresh_token = None
    
    await db.commit()
    
    return {
        "message": f"{account.platform.value} account disconnected successfully"
    }

@router.post("/accounts/{account_id}/refresh")
async def refresh_account_data(
    account_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Refresh account data and analytics"""
    
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.id == account_id,
            SocialAccount.user_id == current_user.id
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Social account not found"
        )
    
    # Queue background task to refresh data
    background_tasks.add_task(
        refresh_account_analytics,
        account_id
    )
    
    return {
        "message": "Account refresh initiated",
        "account_id": account_id
    }

# ============================================================================
# PUBLISHING ENDPOINTS
# ============================================================================

@router.post("/publish/{project_id}", response_model=PublishResponse)
async def publish_video(
    project_id: int,
    request: PublishRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
) -> PublishResponse:
    """Publish video to selected platforms"""
    
    try:
        result = await publishing_service.publish_to_platforms(
            project_id=project_id,
            platforms=request.platforms,
            title=request.title,
            description=request.description,
            hashtags=request.hashtags,
            platform_settings=request.platform_settings
        )
        
        # Queue analytics update
        for success in result['successful']:
            background_tasks.add_task(
                update_publication_analytics_task,
                project_id,
                success['platform']
            )
        
        return PublishResponse(**result)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Publishing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Publishing failed"
        )

@router.post("/schedule/{project_id}")
async def schedule_publication(
    project_id: int,
    request: SchedulePublishRequest,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Schedule video publication"""
    
    # Validate scheduled time is in future
    if request.scheduled_for <= datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scheduled time must be in the future"
        )
    
    # Queue scheduled task
    from ..tasks.social_media_tasks import schedule_publication_task
    
    task = schedule_publication_task.apply_async(
        args=[
            project_id,
            request.platforms,
            request.scheduled_for.isoformat()
        ],
        kwargs={
            'title': request.title,
            'description': request.description,
            'hashtags': request.hashtags,
            'platform_settings': request.platform_settings
        },
        eta=request.scheduled_for
    )
    
    return {
        "message": "Publication scheduled",
        "task_id": task.id,
        "scheduled_for": request.scheduled_for.isoformat(),
        "platforms": request.platforms
    }

# ============================================================================
# ANALYTICS ENDPOINTS
# ============================================================================

@router.get("/analytics/project/{project_id}")
async def get_project_social_analytics(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Get social media analytics for a project"""
    
    # Get all publications for project
    result = await db.execute(
        select(Publication).where(
            Publication.project_id == project_id
        ).join(
            SocialAccount
        ).where(
            SocialAccount.user_id == current_user.id
        )
    )
    publications = result.scalars().all()
    
    # Aggregate analytics
    analytics = {
        'total_views': sum(p.views for p in publications),
        'total_likes': sum(p.likes for p in publications),
        'total_comments': sum(p.comments for p in publications),
        'total_shares': sum(p.shares for p in publications),
        'platforms': {}
    }
    
    # Group by platform
    for pub in publications:
        platform = pub.social_account.platform.value
        if platform not in analytics['platforms']:
            analytics['platforms'][platform] = {
                'publications': 0,
                'views': 0,
                'likes': 0,
                'comments': 0,
                'shares': 0,
                'engagement_rate': 0
            }
        
        platform_stats = analytics['platforms'][platform]
        platform_stats['publications'] += 1
        platform_stats['views'] += pub.views
        platform_stats['likes'] += pub.likes
        platform_stats['comments'] += pub.comments
        platform_stats['shares'] += pub.shares
    
    # Calculate engagement rates
    for platform_stats in analytics['platforms'].values():
        if platform_stats['views'] > 0:
            platform_stats['engagement_rate'] = (
                (platform_stats['likes'] + platform_stats['comments'] + platform_stats['shares']) 
                / platform_stats['views'] * 100
            )
    
    return analytics

@router.get("/analytics/account/{account_id}", response_model=PlatformAnalytics)
async def get_account_analytics(
    account_id: int,
    period: str = Query("30d", regex="^(7d|30d|90d)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> PlatformAnalytics:
    """Get analytics for a social account"""
    
    # Get account
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.id == account_id,
            SocialAccount.user_id == current_user.id
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Social account not found"
        )
    
    # Get platform-specific analytics
    try:
        if account.platform == Platform.YOUTUBE:
            analytics = await youtube_service.get_channel_analytics(account)
        elif account.platform == Platform.INSTAGRAM:
            analytics = await instagram_service.get_account_insights(account, period.rstrip('d'))
        elif account.platform == Platform.TIKTOK:
            analytics = await tiktok_service.get_user_insights(account)
        else:
            analytics = {}
        
        return PlatformAnalytics(
            platform=account.platform,
            account_id=account_id,
            period=period,
            metrics=analytics
        )
        
    except Exception as e:
        logger.error(f"Failed to get analytics for account {account_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analytics"
        )

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def refresh_account_analytics(account_id: int):
    """Background task to refresh account analytics"""
    
    from ..database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(Publication).where(
                Publication.project_id == project_id
            ).join(
                SocialAccount
            ).where(
                SocialAccount.user_id == current_user.id
            )
        )
        publications = result.scalars().all()
        
        return publications

# ============================================================================
# BACKGROUND TASKS
# ============================================================================

async def refresh_account_analytics(account_id: int):
    """Background task to refresh account analytics"""
    
    async with AsyncSessionLocal() as db:
        try:
            # Get social account
            result = await db.execute(
                select(SocialAccount).where(
                    SocialAccount.id == account_id,
                    SocialAccount.is_active == True
                )
            )
            account = result.scalar_one_or_none()
            
            if not account:
                return
            
            # Get service for platform
            service = None
            if account.platform == Platform.YOUTUBE:
                service = youtube_service
            elif account.platform == Platform.INSTAGRAM:
                service = instagram_service
            elif account.platform == Platform.TIKTOK:
                service = tiktok_service
            
            if not service:
                return
            
            # Refresh account data
            if account.platform == Platform.YOUTUBE:
                channel_data = await service.get_channel_analytics(account)
                account.followers_count = channel_data.get("totals", {}).get("subscribers_gained", 0)
            elif account.platform == Platform.INSTAGRAM:
                insights = await service.get_account_insights(account)
                account.followers_count = insights.get("metrics", {}).get("follower_count", 0)
            elif account.platform == Platform.TIKTOK:
                user_data = await service.get_user_insights(account)
                account.followers_count = user_data.get("followers", 0)
            
            # Update all publications for this account
            publications = await db.execute(
                select(Publication).where(
                    Publication.social_account_id == account_id,
                    Publication.is_published == True
                )
            )
            
            for pub in publications.scalars().all():
                await publishing_service.update_publication_analytics(pub.id)
            
            await db.commit()
            logger.info(f"✅ Refreshed analytics for account {account_id}")
            
        except Exception as e:
            logger.error(f"Failed to refresh account analytics: {e}")

async def update_publication_analytics_task(project_id: int, platform: str):
    """Background task to update analytics for a specific publication"""
    
    async with AsyncSessionLocal() as db:
        try:
            # Find publication
            result = await db.execute(
                select(Publication).where(
                    Publication.project_id == project_id
                ).join(
                    SocialAccount
                ).where(
                    SocialAccount.platform == Platform(platform)
                )
            )
            publication = result.scalar_one_or_none()
            
            if publication:
                await publishing_service.update_publication_analytics(publication.id)
                
        except Exception as e:
            logger.error(f"Failed to update publication analytics: {e}")


