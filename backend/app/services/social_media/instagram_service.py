#### `backend/app/services/social_media/instagram_service.py`
```python
"""
📸 Instagram Service - Instagram Reels Publishing
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import json
import aiohttp
from pathlib import Path

from ...config import settings
from ...models import SocialAccount, Platform
from ..file_storage import storage_service

logger = logging.getLogger(__name__)

class InstagramService:
    """Service for Instagram Graph API interactions"""
    
    def __init__(self):
        self.client_id = settings.INSTAGRAM_CLIENT_ID
        self.client_secret = settings.INSTAGRAM_CLIENT_SECRET
        self.redirect_uri = f"{settings.FRONTEND_URL}/auth/instagram/callback"
        self.api_version = "v18.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
    
    # ========================================================================
    # OAUTH FLOW
    # ========================================================================
    
    def get_auth_url(self, state: str) -> str:
        """Get Instagram OAuth authorization URL"""
        
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': 'instagram_basic,instagram_content_publish,instagram_manage_insights,pages_show_list,pages_read_engagement',
            'response_type': 'code',
            'state': state
        }
        
        query_string = '&'.join(f"{k}={v}" for k, v in params.items())
        return f"https://www.facebook.com/{self.api_version}/dialog/oauth?{query_string}"
    
    async def handle_callback(self, code: str) -> Dict[str, Any]:
        """Handle OAuth callback and exchange code for tokens"""
        
        async with aiohttp.ClientSession() as session:
            # Exchange code for short-lived token
            token_url = f"{self.base_url}/oauth/access_token"
            token_params = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'redirect_uri': self.redirect_uri,
                'code': code
            }
            
            async with session.get(token_url, params=token_params) as response:
                token_data = await response.json()
                
                if 'error' in token_data:
                    raise ValueError(f"Token exchange failed: {token_data['error']['message']}")
                
                access_token = token_data['access_token']
            
            # Exchange for long-lived token
            long_lived_url = f"{self.base_url}/oauth/access_token"
            long_lived_params = {
                'grant_type': 'fb_exchange_token',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'fb_exchange_token': access_token
            }
            
            async with session.get(long_lived_url, params=long_lived_params) as response:
                long_lived_data = await response.json()
                access_token = long_lived_data['access_token']
            
            # Get user pages
            pages_url = f"{self.base_url}/me/accounts"
            pages_params = {'access_token': access_token}
            
            async with session.get(pages_url, params=pages_params) as response:
                pages_data = await response.json()
                
                if not pages_data.get('data'):
                    raise ValueError("No Instagram Business accounts found")
                
                # Get first page with Instagram account
                for page in pages_data['data']:
                    # Get Instagram Business Account ID
                    ig_url = f"{self.base_url}/{page['id']}?fields=instagram_business_account&access_token={page['access_token']}"
                    
                    async with session.get(ig_url) as ig_response:
                        ig_data = await ig_response.json()
                        
                        if 'instagram_business_account' in ig_data:
                            ig_account = ig_data['instagram_business_account']
                            
                            # Get Instagram account details
                            account_url = f"{self.base_url}/{ig_account['id']}"
                            account_params = {
                                'fields': 'username,followers_count,media_count',
                                'access_token': page['access_token']
                            }
                            
                            async with session.get(account_url, params=account_params) as account_response:
                                account_data = await account_response.json()
                                
                                return {
                                    'access_token': page['access_token'],
                                    'instagram_business_account_id': ig_account['id'],
                                    'username': account_data.get('username'),
                                    'followers_count': account_data.get('followers_count', 0),
                                    'page_id': page['id'],
                                    'page_name': page['name']
                                }
                
                raise ValueError("No Instagram Business account found on any page")
    
    # ========================================================================
    # REEL UPLOAD
    # ========================================================================
    
    async def upload_reel(
        self,
        social_account: SocialAccount,
        video_url: str,
        caption: str,
        cover_url: Optional[str] = None,
        share_to_feed: bool = True,
        location_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Upload video as Instagram Reel"""
        
        ig_account_id = social_account.platform_user_id
        access_token = social_account.access_token
        
        async with aiohttp.ClientSession() as session:
            # Step 1: Create media container
            container_url = f"{self.base_url}/{ig_account_id}/media"
            container_params = {
                'media_type': 'REELS',
                'video_url': video_url,
                'caption': self._format_caption(caption),
                'share_to_feed': share_to_feed,
                'access_token': access_token
            }
            
            if cover_url:
                container_params['cover_url'] = cover_url
            
            if location_id:
                container_params['location_id'] = location_id
            
            async with session.post(container_url, data=container_params) as response:
                container_data = await response.json()
                
                if 'error' in container_data:
                    raise ValueError(f"Container creation failed: {container_data['error']['message']}")
                
                container_id = container_data['id']
            
            # Step 2: Check container status
            await self._wait_for_container_ready(session, container_id, access_token)
            
            # Step 3: Publish the reel
            publish_url = f"{self.base_url}/{ig_account_id}/media_publish"
            publish_params = {
                'creation_id': container_id,
                'access_token': access_token
            }
            
            async with session.post(publish_url, data=publish_params) as response:
                publish_data = await response.json()
                
                if 'error' in publish_data:
                    raise ValueError(f"Publishing failed: {publish_data['error']['message']}")
                
                media_id = publish_data['id']
            
            # Get the published reel URL
            reel_url = await self._get_media_permalink(session, media_id, access_token)
            
            return {
                'platform_post_id': media_id,
                'url': reel_url,
                'status': 'published'
            }
    
    # ========================================================================
    # ANALYTICS
    # ========================================================================
    
    async def get_reel_insights(
        self,
        social_account: SocialAccount,
        media_id: str
    ) -> Dict[str, Any]:
        """Get insights for an Instagram Reel"""
        
        access_token = social_account.access_token
        
        async with aiohttp.ClientSession() as session:
            insights_url = f"{self.base_url}/{media_id}/insights"
            insights_params = {
                'metric': 'impressions,reach,likes,comments,shares,saves,plays,total_interactions',
                'access_token': access_token
            }
            
            async with session.get(insights_url, params=insights_params) as response:
                insights_data = await response.json()
                
                if 'error' in insights_data:
                    logger.error(f"Insights error: {insights_data['error']}")
                    return {}
                
                # Parse insights
                insights = {}
                for metric in insights_data.get('data', []):
                    insights[metric['name']] = metric['values'][0]['value']
                
                return insights
    
    async def get_account_insights(
        self,
        social_account: SocialAccount,
        period: str = "day"
    ) -> Dict[str, Any]:
        """Get account-level insights"""
        
        ig_account_id = social_account.platform_user_id
        access_token = social_account.access_token
        
        async with aiohttp.ClientSession() as session:
            insights_url = f"{self.base_url}/{ig_account_id}/insights"
            insights_params = {
                'metric': 'impressions,reach,follower_count,profile_views',
                'period': period,
                'access_token': access_token
            }
            
            async with session.get(insights_url, params=insights_params) as response:
                insights_data = await response.json()
                
                if 'error' in insights_data:
                    return {}
                
                # Parse insights
                insights = {
                    'period': period,
                    'metrics': {}
                }
                
                for metric in insights_data.get('data', []):
                    insights['metrics'][metric['name']] = metric['values'][0]['value']
                
                return insights
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    async def _wait_for_container_ready(
        self,
        session: aiohttp.ClientSession,
        container_id: str,
        access_token: str,
        max_attempts: int = 30
    ):
        """Wait for media container to be ready for publishing"""
        
        status_url = f"{self.base_url}/{container_id}"
        status_params = {
            'fields': 'status_code',
            'access_token': access_token
        }
        
        for attempt in range(max_attempts):
            async with session.get(status_url, params=status_params) as response:
                status_data = await response.json()
                
                status_code = status_data.get('status_code')
                
                if status_code == 'FINISHED':
                    return
                elif status_code == 'ERROR':
                    raise ValueError(f"Container processing failed")
                
                # Wait before next check
                await asyncio.sleep(2)
        
        raise TimeoutError("Container processing timed out")
    
    async def _get_media_permalink(
        self,
        session: aiohttp.ClientSession,
        media_id: str,
        access_token: str
    ) -> str:
        """Get permalink for published media"""
        
        media_url = f"{self.base_url}/{media_id}"
        media_params = {
            'fields': 'permalink',
            'access_token': access_token
        }
        
        async with session.get(media_url, params=media_params) as response:
            media_data = await response.json()
            return media_data.get('permalink', '')
    
    def _format_caption(self, caption: str) -> str:
        """Format caption with proper hashtag spacing"""
        
        # Instagram prefers hashtags at the end
        # Ensure proper spacing
        lines = caption.split('\n')
        
        # Find where hashtags start
        hashtag_start = -1
        for i, line in enumerate(lines):
            if line.strip().startswith('#'):
                hashtag_start = i
                break
        
        if hashtag_start > 0:
            # Add extra line break before hashtags
            lines.insert(hashtag_start, '')
        
        return '\n'.join(lines)

# Initialize service
instagram_service = InstagramService()
```
