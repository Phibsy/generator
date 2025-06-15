#### `backend/app/services/social_media/publishing_service.py`
```python
"""
📤 Publishing Service - Unified Social Media Publishing
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import asyncio

from ...models import Project, Publication, SocialAccount, Platform
from ...database import AsyncSessionLocal
from .youtube_service import youtube_service
from .instagram_service import instagram_service
from .tiktok_service import tiktok_service
from ..file_storage import storage_service

logger = logging.getLogger(__name__)

class PublishingService:
    """Unified service for publishing to all platforms"""
    
    def __init__(self):
        self.services = {
            Platform.YOUTUBE: youtube_service,
            Platform.INSTAGRAM: instagram_service,
            Platform.TIKTOK: tiktok_service
        }
    
    async def publish_to_platforms(
        self,
        project_id: int,
        platforms: List[str],
        title: Optional[str] = None,
        description: Optional[str] = None,
        hashtags: Optional[List[str]] = None,
        scheduled_for: Optional[datetime] = None,
        platform_settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Publish video to multiple platforms"""
        
        results = {
            'successful': [],
            'failed': [],
            'scheduled': []
        }
        
        async with AsyncSessionLocal() as db:
            # Get project
            project = await db.get(Project, project_id)
            if not project:
                raise ValueError(f"Project {project_id} not found")
            
            if not project.video_file_path:
                raise ValueError("Project has no video to publish")
            
            # Use project data if not provided
            title = title or project.title
            description = description or project.description or ""
            hashtags = hashtags or project.hashtags or []
            
            # Get user's social accounts
            social_accounts = await self._get_user_social_accounts(db, project.user_id)
            
            # Publish to each platform
            tasks = []
            for platform_str in platforms:
                platform = Platform(platform_str)
                
                if platform not in social_accounts:
                    results['failed'].append({
                        'platform': platform_str,
                        'error': 'No connected account'
                    })
                    continue
                
                # Create task for platform
                task = self._publish_to_platform(
                    project,
                    social_accounts[platform],
                    title,
                    description,
                    hashtags,
                    scheduled_for,
                    platform_settings.get(platform_str) if platform_settings else None
                )
                tasks.append((platform_str, task))
            
            # Execute all publishing tasks
            for platform_str, task in tasks:
                try:
                    result = await task
                    
                    # Create publication record
                    publication = Publication(
                        project_id=project_id,
                        social_account_id=result['social_account_id'],
                        platform_post_id=result['platform_post_id'],
                        url=result['url'],
                        title=title,
                        description=description,
                        is_published=result.get('is_published', True),
                        published_at=datetime.utcnow() if not scheduled_for else None,
                        scheduled_for=scheduled_for
                    )
                    db.add(publication)
                    
                    if scheduled_for:
                        results['scheduled'].append({
                            'platform': platform_str,
                            'scheduled_for': scheduled_for.isoformat()
                        })
                    else:
                        results['successful'].append({
                            'platform': platform_str,
                            'url': result['url'],
                            'post_id': result['platform_post_id']
                        })
                        
                except Exception as e:
                    logger.error(f"Publishing to {platform_str} failed: {e}")
                    results['failed'].append({
                        'platform': platform_str,
                        'error': str(e)
                    })
            
            await db.commit()
        
        return results
    
    async def _publish_to_platform(
        self,
        project: Project,
        social_account: SocialAccount,
        title: str,
        description: str,
        hashtags: List[str],
        scheduled_for: Optional[datetime],
        platform_settings: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Publish to a specific platform"""
        
        service = self.services[social_account.platform]
        
        # Ensure video is accessible
        video_url = await self._ensure_public_url(project.video_file_path)
        thumbnail_url = None
        if project.thumbnail_path:
            thumbnail_url = await self._ensure_public_url(project.thumbnail_path)
        
        # Platform-specific publishing
        if social_account.platform == Platform.YOUTUBE:
            result = await service.upload_video(
                social_account,
                video_url,
                title,
                description,
                hashtags,
                privacy_status=platform_settings.get('privacy_status', 'public') if platform_settings else 'public',
                thumbnail_path=thumbnail_url
            )
            
        elif social_account.platform == Platform.INSTAGRAM:
            # Format caption with hashtags
            caption = f"{description}\n\n" + ' '.join(f'#{tag}' for tag in hashtags)
            
            result = await service.upload_reel(
                social_account,
                video_url,
                caption,
                cover_url=thumbnail_url,
                share_to_feed=platform_settings.get('share_to_feed', True) if platform_settings else True
            )
            
        elif social_account.platform == Platform.TIKTOK:
            # TikTok uses title for caption
            caption = f"{title}\n\n{description}\n\n" + ' '.join(f'#{tag}' for tag in hashtags)
            
            result = await service.upload_video(
                social_account,
                video_url,
                caption,
                privacy_level=platform_settings.get('privacy_level', 'PUBLIC') if platform_settings else 'PUBLIC'
            )
        
        else:
            raise ValueError(f"Unsupported platform: {social_account.platform}")
        
        # Add social account ID to result
        result['social_account_id'] = social_account.id
        result['is_published'] = scheduled_for is None
        
        return result
    
    async def update_publication_analytics(self, publication_id: int):
        """Update analytics for a publication"""
        
        async with AsyncSessionLocal() as db:
            # Get publication with social account
            publication = await db.get(Publication, publication_id)
            if not publication:
                return
            
            social_account = await db.get(SocialAccount, publication.social_account_id)
            if not social_account:
                return
            
            service = self.services[social_account.platform]
            
            try:
                # Get platform-specific analytics
                if social_account.platform == Platform.YOUTUBE:
                    analytics = await service.get_video_analytics(
                        social_account,
                        publication.platform_post_id
                    )
                    
                elif social_account.platform == Platform.INSTAGRAM:
                    analytics = await service.get_reel_insights(
                        social_account,
                        publication.platform_post_id
                    )
                    
                elif social_account.platform == Platform.TIKTOK:
                    result = await service.get_video_insights(
                        social_account,
                        [publication.platform_post_id]
                    )
                    analytics = result.get(publication.platform_post_id, {})
                
                # Update publication metrics
                publication.views = analytics.get('views', publication.views)
                publication.likes = analytics.get('likes', publication.likes)
                publication.comments = analytics.get('comments', publication.comments)
                publication.shares = analytics.get('shares', publication.shares)
                
                await db.commit()
                
            except Exception as e:
                logger.error(f"Failed to update analytics for publication {publication_id}: {e}")
    
    async def _get_user_social_accounts(
        self,
        db,
        user_id: int
    ) -> Dict[Platform, SocialAccount]:
        """Get user's connected social accounts"""
        
        from sqlalchemy import select
        
        result = await db.execute(
            select(SocialAccount).where(
                SocialAccount.user_id == user_id,
                SocialAccount.is_active == True
            )
        )
        accounts = result.scalars().all()
        
        return {account.platform: account for account in accounts}
    
    async def _ensure_public_url(self, file_path: str) -> str:
        """Ensure file has a publicly accessible URL"""
        
        # If already a public URL, return as is
        if file_path.startswith('http'):
            return file_path
        
        # Generate presigned URL for S3 files
        return storage_service.generate_presigned_url(file_path, expiration=3600)

# Initialize service
publishing_service = PublishingService()
```
