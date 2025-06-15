#### `backend/app/services/social_media/__init__.py`
```python
"""
📱 REELS GENERATOR - Social Media Services
Platform integrations for automated publishing
"""

from .youtube_service import YouTubeService, youtube_service
from .instagram_service import InstagramService, instagram_service
from .tiktok_service import TikTokService, tiktok_service
from .publishing_service import PublishingService, publishing_service

__all__ = [
    'YouTubeService', 'youtube_service',
    'InstagramService', 'instagram_service', 
    'TikTokService', 'tiktok_service',
    'PublishingService', 'publishing_service'
]
```
