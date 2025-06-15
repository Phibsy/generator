#### `backend/app/services/social_media/tiktok_service.py`
```python
"""
🎵 TikTok Service - TikTok Video Publishing
"""

import asyncio
import hashlib
import hmac
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import json
import aiohttp
from urllib.parse import urlencode

from ...config import settings
from ...models import SocialAccount, Platform

logger = logging.getLogger(__name__)

class TikTokService:
    """Service for TikTok API interactions"""
    
    def __init__(self):
        self.client_key = settings.TIKTOK_CLIENT_KEY
        self.client_secret = settings.TIKTOK_CLIENT_SECRET
        self.redirect_uri = f"{settings.FRONTEND_URL}/auth/tiktok/callback"
        self.base_url = "https://open-api.tiktok.com"
    
    # ========================================================================
    # OAUTH FLOW
    # ========================================================================
    
    def get_auth_url(self, state: str) -> str:
        """Get TikTok OAuth authorization URL"""
        
        # TikTok OAuth scopes
        scopes = [
            'user.info.basic',
            'video.list',
            'video.upload',
            'video.publish'
        ]
        
        params = {
            'client_key': self.client_key,
            'scope': ','.join(scopes),
            'response_type': 'code',
            'redirect_uri': self.redirect_uri,
            'state': state
        }
        
        return f"https://www.tiktok.com/auth/authorize/?{urlencode(params)}"
    
    async def handle_callback(self, code: str) -> Dict[str, Any]:
        """Handle OAuth callback and exchange code for tokens"""
        
        async with aiohttp.ClientSession() as session:
            # Exchange code for access token
            token_url = f"{self.base_url}/oauth/access_token/"
            token_data = {
                'client_key': self.client_key,
                'client_secret': self.client_secret,
                'code': code,
                'grant_type': 'authorization_code'
            }
            
            async with session.post(token_url, json=token_data) as response:
                result = await response.json()
                
                if result.get('data', {}).get('error_code'):
                    raise ValueError(f"Token exchange failed: {result['data']['description']}")
                
                token_info = result['data']
                access_token = token_info['access_token']
                open_id = token_info['open_id']
            
            # Get user info
            user_url = f"{self.base_url}/user/info/"
            headers = {
                'access-token': access_token
            }
            params = {
                'open_id': open_id,
                'fields': ['display_name', 'avatar_url', 'follower_count', 'following_count']
            }
            
            async with session.get(user_url, headers=headers, params=params) as response:
                user_result = await response.json()
                
                if user_result.get('data', {}).get('error_code'):
                    raise ValueError(f"Failed to get user info: {user_result['data']['description']}")
                
                user_data = user_result['data']['user']
                
                return {
                    'access_token': access_token,
                    'refresh_token': token_info.get('refresh_token'),
                    'open_id': open_id,
                    'username': user_data['display_name'],
                    'avatar_url': user_data.get('avatar_url'),
                    'followers_count': user_data.get('follower_count', 0)
                }
    
    # ========================================================================
    # VIDEO UPLOAD
    # ========================================================================
    
    async def upload_video(
        self,
        social_account: SocialAccount,
        video_url: str,
        title: str,
        privacy_level: str = "SELF_ONLY",  # SELF_ONLY, MUTUAL_FOLLOW_FRIENDS, FRIENDS_ONLY, PUBLIC
        allow_comments: bool = True,
        allow_duet: bool = True,
        allow_stitch: bool = True
    ) -> Dict[str, Any]:
        """Upload video to TikTok"""
        
        access_token = social_account.access_token
        open_id = social_account.platform_user_id
        
        async with aiohttp.ClientSession() as session:
            # Step 1: Initialize upload
            init_url = f"{self.base_url}/share/video/upload/"
            headers = {
                'access-token': access_token,
                'Content-Type': 'application/json'
            }
            
            init_data = {
                'open_id': open_id,
                'chunk_size': 10485760,  # 10MB chunks
                'total_byte_size': await self._get_video_size(video_url)
            }
            
            async with session.post(init_url, headers=headers, json=init_data) as response:
                init_result = await response.json()
                
                if init_result.get('data', {}).get('error_code'):
                    raise ValueError(f"Upload init failed: {init_result['data']['description']}")
                
                upload_id = init_result['data']['upload_id']
            
            # Step 2: Upload video chunks
            await self._upload_video_chunks(session, video_url, upload_id, access_token, open_id)
            
            # Step 3: Create video post
            post_url = f"{self.base_url}/share/video/post/"
            post_data = {
                'open_id': open_id,
                'upload_id': upload_id,
                'video_title': title[:150],  # TikTok title limit
                'privacy_level': privacy_level,
                'allow_comment': allow_comments,
                'allow_duet': allow_duet,
                'allow_stitch': allow_stitch
            }
            
            async with session.post(post_url, headers=headers, json=post_data) as response:
                post_result = await response.json()
                
                if post_result.get('data', {}).get('error_code'):
                    raise ValueError(f"Video post failed: {post_result['data']['description']}")
                
                share_id = post_result['data']['share_id']
            
            # Get video status
            status = await self._check_publish_status(session, share_id, access_token, open_id)
            
            return {
                'platform_post_id': share_id,
                'status': status['status'],
                'url': status.get('video_url', '')
            }
    
    # ========================================================================
    # ANALYTICS
    # ========================================================================
    
    async def get_video_insights(
        self,
        social_account: SocialAccount,
        video_ids: List[str]
    ) -> Dict[str, Any]:
        """Get insights for TikTok videos"""
        
        access_token = social_account.access_token
        open_id = social_account.platform_user_id
        
        async with aiohttp.ClientSession() as session:
            insights_url = f"{self.base_url}/video/data/"
            headers = {
                'access-token': access_token
            }
            params = {
                'open_id': open_id,
                'filters': {
                    'video_ids': video_ids
                }
            }
            
            async with session.post(insights_url, headers=headers, json=params) as response:
                result = await response.json()
                
                if result.get('data', {}).get('error_code'):
                    logger.error(f"Insights error: {result['data']['description']}")
                    return {}
                
                videos_data = {}
                for video in result['data']['videos']:
                    videos_data[video['item_id']] = {
                        'views': video.get('play_count', 0),
                        'likes': video.get('like_count', 0),
                        'comments': video.get('comment_count', 0),
                        'shares': video.get('share_count', 0),
                        'title': video.get('title', ''),
                        'create_time': video.get('create_time', '')
                    }
                
                return videos_data
    
    async def get_user_insights(
        self,
        social_account: SocialAccount
    ) -> Dict[str, Any]:
        """Get user account insights"""
        
        access_token = social_account.access_token
        open_id = social_account.platform_user_id
        
        async with aiohttp.ClientSession() as session:
            user_url = f"{self.base_url}/user/info/"
            headers = {
                'access-token': access_token
            }
            params = {
                'open_id': open_id,
                'fields': [
                    'display_name',
                    'follower_count',
                    'following_count',
                    'likes_count',
                    'video_count'
                ]
            }
            
            async with session.get(user_url, headers=headers, params=params) as response:
                result = await response.json()
                
                if result.get('data', {}).get('error_code'):
                    return {}
                
                user_data = result['data']['user']
                
                return {
                    'username': user_data.get('display_name'),
                    'followers': user_data.get('follower_count', 0),
                    'following': user_data.get('following_count', 0),
                    'total_likes': user_data.get('likes_count', 0),
                    'total_videos': user_data.get('video_count', 0)
                }
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    async def _get_video_size(self, video_url: str) -> int:
        """Get video file size from URL"""
        
        async with aiohttp.ClientSession() as session:
            async with session.head(video_url) as response:
                return int(response.headers.get('Content-Length', 0))
    
    async def _upload_video_chunks(
        self,
        session: aiohttp.ClientSession,
        video_url: str,
        upload_id: str,
        access_token: str,
        open_id: str
    ):
        """Upload video in chunks"""
        
        chunk_size = 10485760  # 10MB
        chunk_num = 0
        
        async with session.get(video_url) as video_response:
            while True:
                chunk = await video_response.content.read(chunk_size)
                if not chunk:
                    break
                
                # Upload chunk
                upload_url = f"{self.base_url}/share/video/upload/"
                headers = {
                    'access-token': access_token,
                    'Content-Type': 'application/octet-stream',
                    'Content-Range': f'bytes {chunk_num * chunk_size}-{chunk_num * chunk_size + len(chunk) - 1}/{await self._get_video_size(video_url)}'
                }
                
                params = {
                    'open_id': open_id,
                    'upload_id': upload_id,
                    'chunk': chunk_num
                }
                
                async with session.post(upload_url, headers=headers, data=chunk, params=params) as response:
                    result = await response.json()
                    
                    if result.get('data', {}).get('error_code'):
                        raise ValueError(f"Chunk upload failed: {result['data']['description']}")
                
                chunk_num += 1
    
    async def _check_publish_status(
        self,
        session: aiohttp.ClientSession,
        share_id: str,
        access_token: str,
        open_id: str,
        max_attempts: int = 30
    ) -> Dict[str, Any]:
        """Check video publish status"""
        
        status_url = f"{self.base_url}/share/video/query/"
        headers = {
            'access-token': access_token
        }
        params = {
            'open_id': open_id,
            'share_id': share_id
        }
        
        for _ in range(max_attempts):
            async with session.get(status_url, headers=headers, params=params) as response:
                result = await response.json()
                
                if result.get('data', {}).get('error_code'):
                    raise ValueError(f"Status check failed: {result['data']['description']}")
                
                status = result['data']['status']
                
                if status == 'PublishComplete':
                    return {
                        'status': 'published',
                        'video_url': result['data'].get('video_url', '')
                    }
                elif status == 'Failed':
                    raise ValueError("Video publishing failed")
                
                # Wait before next check
                await asyncio.sleep(2)
        
        return {'status': 'processing'}

# Initialize service
tiktok_service = TikTokService()
```
