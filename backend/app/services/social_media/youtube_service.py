#### `backend/app/services/social_media/youtube_service.py`
```python
"""
📺 YouTube Service - YouTube Shorts Publishing
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
import aiofiles

from ...config import settings
from ...models import SocialAccount, Platform
from ..file_storage import storage_service

logger = logging.getLogger(__name__)

class YouTubeService:
    """Service for YouTube API interactions"""
    
    SCOPES = [
        'https://www.googleapis.com/auth/youtube.upload',
        'https://www.googleapis.com/auth/youtube.readonly',
        'https://www.googleapis.com/auth/youtubepartner'
    ]
    
    def __init__(self):
        self.client_id = settings.YOUTUBE_CLIENT_ID
        self.client_secret = settings.YOUTUBE_CLIENT_SECRET
        self.redirect_uri = f"{settings.FRONTEND_URL}/auth/youtube/callback"
    
    # ========================================================================
    # OAUTH FLOW
    # ========================================================================
    
    def get_auth_url(self, state: str) -> str:
        """Get YouTube OAuth authorization URL"""
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            },
            scopes=self.SCOPES
        )
        flow.redirect_uri = self.redirect_uri
        
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state,
            prompt='consent'
        )
        
        return auth_url
    
    async def handle_callback(self, code: str) -> Dict[str, Any]:
        """Handle OAuth callback and exchange code for tokens"""
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            },
            scopes=self.SCOPES
        )
        flow.redirect_uri = self.redirect_uri
        
        # Exchange code for token
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Get channel info
        youtube = build('youtube', 'v3', credentials=credentials)
        channel_response = youtube.channels().list(
            part='snippet,statistics',
            mine=True
        ).execute()
        
        if not channel_response.get('items'):
            raise ValueError("No YouTube channel found")
        
        channel = channel_response['items'][0]
        
        return {
            'access_token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_expires_at': credentials.expiry.isoformat() if credentials.expiry else None,
            'channel_id': channel['id'],
            'channel_title': channel['snippet']['title'],
            'subscriber_count': int(channel['statistics'].get('subscriberCount', 0))
        }
    
    # ========================================================================
    # VIDEO UPLOAD
    # ========================================================================
    
    async def upload_video(
        self,
        social_account: SocialAccount,
        video_path: str,
        title: str,
        description: str,
        tags: List[str],
        category_id: str = "22",  # People & Blogs
        privacy_status: str = "public",
        thumbnail_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Upload video to YouTube as a Short"""
        
        # Ensure credentials are valid
        credentials = await self._get_valid_credentials(social_account)
        youtube = build('youtube', 'v3', credentials=credentials)
        
        # Download video from S3 to temp file
        temp_video_path = await self._download_to_temp(video_path)
        
        try:
            # Prepare video metadata
            body = {
                'snippet': {
                    'title': title[:100],  # YouTube title limit
                    'description': self._format_description(description, tags),
                    'tags': tags[:500],  # YouTube tags limit
                    'categoryId': category_id
                },
                'status': {
                    'privacyStatus': privacy_status,
                    'selfDeclaredMadeForKids': False,
                    'shorts': {
                        'type': 'SHORTS'  # Mark as YouTube Short
                    }
                }
            }
            
            # Create media upload
            media = MediaFileUpload(
                temp_video_path,
                mimetype='video/mp4',
                resumable=True,
                chunksize=1024*1024  # 1MB chunks
            )
            
            # Execute upload
            request = youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.info(f"Upload progress: {int(status.progress() * 100)}%")
            
            video_id = response['id']
            
            # Upload thumbnail if provided
            if thumbnail_path:
                await self._upload_thumbnail(youtube, video_id, thumbnail_path)
            
            # Get video URL
            video_url = f"https://youtube.com/shorts/{video_id}"
            
            return {
                'platform_post_id': video_id,
                'url': video_url,
                'status': response['status']['uploadStatus'],
                'privacy_status': response['status']['privacyStatus']
            }
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_video_path):
                os.remove(temp_video_path)
    
    # ========================================================================
    # ANALYTICS
    # ========================================================================
    
    async def get_video_analytics(
        self,
        social_account: SocialAccount,
        video_id: str
    ) -> Dict[str, Any]:
        """Get analytics for a YouTube video"""
        
        credentials = await self._get_valid_credentials(social_account)
        youtube = build('youtube', 'v3', credentials=credentials)
        
        try:
            # Get video statistics
            response = youtube.videos().list(
                part='statistics,snippet',
                id=video_id
            ).execute()
            
            if not response.get('items'):
                return {}
            
            video = response['items'][0]
            stats = video.get('statistics', {})
            
            return {
                'views': int(stats.get('viewCount', 0)),
                'likes': int(stats.get('likeCount', 0)),
                'dislikes': int(stats.get('dislikeCount', 0)),
                'comments': int(stats.get('commentCount', 0)),
                'favorites': int(stats.get('favoriteCount', 0)),
                'title': video['snippet']['title'],
                'published_at': video['snippet']['publishedAt']
            }
            
        except HttpError as e:
            logger.error(f"YouTube API error: {e}")
            return {}
    
    async def get_channel_analytics(
        self,
        social_account: SocialAccount
    ) -> Dict[str, Any]:
        """Get channel analytics"""
        
        credentials = await self._get_valid_credentials(social_account)
        youtube_analytics = build('youtubeAnalytics', 'v2', credentials=credentials)
        
        # Get analytics for last 30 days
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
        
        try:
            response = youtube_analytics.reports().query(
                ids='channel==MINE',
                startDate=start_date.isoformat(),
                endDate=end_date.isoformat(),
                metrics='views,likes,comments,shares,estimatedMinutesWatched,subscribersGained',
                dimensions='day'
            ).execute()
            
            return {
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'totals': {
                    'views': sum(row[1] for row in response.get('rows', [])),
                    'likes': sum(row[2] for row in response.get('rows', [])),
                    'comments': sum(row[3] for row in response.get('rows', [])),
                    'shares': sum(row[4] for row in response.get('rows', [])),
                    'watch_time_minutes': sum(row[5] for row in response.get('rows', [])),
                    'subscribers_gained': sum(row[6] for row in response.get('rows', []))
                },
                'daily_data': response.get('rows', [])
            }
            
        except HttpError as e:
            logger.error(f"YouTube Analytics API error: {e}")
            return {}
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    async def _get_valid_credentials(self, social_account: SocialAccount) -> Credentials:
        """Get valid credentials, refreshing if necessary"""
        
        creds = Credentials(
            token=social_account.access_token,
            refresh_token=social_account.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret
        )
        
        # Check if token needs refresh
        if social_account.token_expires_at and datetime.utcnow() >= social_account.token_expires_at:
            creds.refresh(Request())
            
            # Update stored tokens
            from ...database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                social_account.access_token = creds.token
                social_account.token_expires_at = creds.expiry
                await db.commit()
        
        return creds
    
    async def _download_to_temp(self, s3_url: str) -> str:
        """Download video from S3 to temporary file"""
        
        import tempfile
        import aiohttp
        
        temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(s3_url) as response:
                async with aiofiles.open(temp_file.name, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
        
        return temp_file.name
    
    async def _upload_thumbnail(
        self,
        youtube,
        video_id: str,
        thumbnail_path: str
    ):
        """Upload thumbnail for video"""
        
        temp_thumbnail = await self._download_to_temp(thumbnail_path)
        
        try:
            media = MediaFileUpload(temp_thumbnail, mimetype='image/jpeg')
            
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=media
            ).execute()
            
        finally:
            if os.path.exists(temp_thumbnail):
                os.remove(temp_thumbnail)
    
    def _format_description(self, description: str, tags: List[str]) -> str:
        """Format description with hashtags"""
        
        # Add hashtags to description
        hashtags = ' '.join(f'#{tag}' for tag in tags[:30])
        
        return f"{description}\n\n{hashtags}\n\n#Shorts"

# Initialize service
youtube_service = YouTubeService()
```
