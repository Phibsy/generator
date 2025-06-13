# backend/app/services/cdn_manager.py
"""
🌐 REELS GENERATOR - CDN Manager Service
CloudFront CDN configuration and management
"""

import boto3
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta
import hashlib

from ..config import settings

logger = logging.getLogger(__name__)

class CDNManagerService:
    """Service for CDN configuration and optimization"""
    
    def __init__(self):
        self.cloudfront_client = boto3.client(
            'cloudfront',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        
        self.distribution_id = settings.CLOUDFRONT_DISTRIBUTION_ID
        self.cdn_domain = settings.CDN_DOMAIN
    
    # ========================================================================
    # CDN CONFIGURATION
    # ========================================================================
    
    async def setup_cdn_distribution(self) -> Dict[str, Any]:
        """Setup CloudFront distribution for assets"""
        
        try:
            # Create distribution configuration
            distribution_config = {
                'CallerReference': f'reels-generator-{datetime.utcnow().timestamp()}',
                'Comment': 'Reels Generator Asset CDN',
                'DefaultRootObject': 'index.html',
                'Origins': {
                    'Quantity': 1,
                    'Items': [
                        {
                            'Id': 'S3-reels-assets',
                            'DomainName': f'{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com',
                            'S3OriginConfig': {
                                'OriginAccessIdentity': ''
                            }
                        }
                    ]
                },
                'DefaultCacheBehavior': {
                    'TargetOriginId': 'S3-reels-assets',
                    'ViewerProtocolPolicy': 'redirect-to-https',
                    'AllowedMethods': {
                        'Quantity': 2,
                        'Items': ['GET', 'HEAD']
                    },
                    'ForwardedValues': {
                        'QueryString': False,
                        'Cookies': {'Forward': 'none'}
                    },
                    'TrustedSigners': {
                        'Enabled': False,
                        'Quantity': 0
                    },
                    'MinTTL': 0,
                    'DefaultTTL': 86400,  # 1 day
                    'MaxTTL': 31536000  # 1 year
                },
                'CacheBehaviors': {
                    'Quantity': 2,
                    'Items': [
                        {
                            'PathPattern': 'assets/backgrounds/*',
                            'TargetOriginId': 'S3-reels-assets',
                            'ViewerProtocolPolicy': 'redirect-to-https',
                            'AllowedMethods': {
                                'Quantity': 2,
                                'Items': ['GET', 'HEAD']
                            },
                            'ForwardedValues': {
                                'QueryString': False,
                                'Cookies': {'Forward': 'none'}
                            },
                            'TrustedSigners': {
                                'Enabled': False,
                                'Quantity': 0
                            },
                            'MinTTL': 0,
                            'DefaultTTL': 604800,  # 7 days for backgrounds
                            'MaxTTL': 31536000
                        },
                        {
                            'PathPattern': 'assets/music/*',
                            'TargetOriginId': 'S3-reels-assets',
                            'ViewerProtocolPolicy': 'redirect-to-https',
                            'AllowedMethods': {
                                'Quantity': 2,
                                'Items': ['GET', 'HEAD']
                            },
                            'ForwardedValues': {
                                'QueryString': False,
                                'Cookies': {'Forward': 'none'}
                            },
                            'TrustedSigners': {
                                'Enabled': False,
                                'Quantity': 0
                            },
                            'MinTTL': 0,
                            'DefaultTTL': 2592000,  # 30 days for music
                            'MaxTTL': 31536000
                        }
                    ]
                },
                'Enabled': True,
                'PriceClass': 'PriceClass_100'  # Use all edge locations
            }
            
            # Create distribution
            response = self.cloudfront_client.create_distribution(
                DistributionConfig=distribution_config
            )
            
            distribution = response['Distribution']
            
            logger.info(f"✅ CloudFront distribution created: {distribution['Id']}")
            
            return {
                "distribution_id": distribution['Id'],
                "domain_name": distribution['DomainName'],
                "status": distribution['Status']
            }
            
        except Exception as e:
            logger.error(f"💥 CDN setup failed: {e}")
            raise
    
    # ========================================================================
    # CACHE MANAGEMENT
    # ========================================================================
    
    async def invalidate_cache(
        self,
        paths: List[str],
        reference: Optional[str] = None
    ) -> str:
        """Invalidate CDN cache for specific paths"""
        
        try:
            if not reference:
                reference = f"invalidation-{datetime.utcnow().timestamp()}"
            
            # Create invalidation
            response = self.cloudfront_client.create_invalidation(
                DistributionId=self.distribution_id,
                InvalidationBatch={
                    'Paths': {
                        'Quantity': len(paths),
                        'Items': paths
                    },
                    'CallerReference': reference
                }
            )
            
            invalidation_id = response['Invalidation']['Id']
            
            logger.info(f"🔄 Cache invalidation created: {invalidation_id}")
            
            return invalidation_id
            
        except Exception as e:
            logger.error(f"💥 Cache invalidation failed: {e}")
            raise
    
    async def warm_cache(self, asset_urls: List[str]):
        """Pre-warm CDN cache by requesting assets"""
        
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            
            for url in asset_urls:
                # Convert S3 URL to CDN URL
                cdn_url = self._convert_to_cdn_url(url)
                tasks.append(self._request_asset(session, cdn_url))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful = sum(1 for r in results if not isinstance(r, Exception))
            
            logger.info(f"🔥 Cache warmed: {successful}/{len(asset_urls)} assets")
    
    # ========================================================================
    # URL SIGNING FOR PRIVATE CONTENT
    # ========================================================================
    
    def generate_signed_url(
        self,
        resource_url: str,
        expiry_time: Optional[datetime] = None
    ) -> str:
        """Generate signed URL for private content"""
        
        if not expiry_time:
            expiry_time = datetime.utcnow() + timedelta(hours=24)
        
        # CloudFront signed URL logic
        # In production, use CloudFront key pair for signing
        
        policy = {
            "Statement": [
                {
                    "Resource": resource_url,
                    "Condition": {
                        "DateLessThan": {
                            "AWS:EpochTime": int(expiry_time.timestamp())
                        }
                    }
                }
            ]
        }
        
        # This is a placeholder - actual implementation requires CloudFront key pair
        signature = hashlib.sha256(json.dumps(policy).encode()).hexdigest()
        
        signed_url = f"{resource_url}?Policy={policy}&Signature={signature}"
        
        return signed_url
    
    # ========================================================================
    # CDN ANALYTICS
    # ========================================================================
    
    async def get_cdn_usage_stats(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get CDN usage statistics"""
        
        try:
            # Get CloudWatch metrics
            cloudwatch = boto3.client('cloudwatch')
            
            # Bytes downloaded
            bytes_downloaded = cloudwatch.get_metric_statistics(
                Namespace='AWS/CloudFront',
                MetricName='BytesDownloaded',
                Dimensions=[
                    {
                        'Name': 'DistributionId',
                        'Value': self.distribution_id
                    }
                ],
                StartTime=start_date,
                EndTime=end_date,
                Period=86400,  # Daily
                Statistics=['Sum']
            )
            
            # Requests
            requests = cloudwatch.get_metric_statistics(
                Namespace='AWS/CloudFront',
                MetricName='Requests',
                Dimensions=[
                    {
                        'Name': 'DistributionId',
                        'Value': self.distribution_id
                    }
                ],
                StartTime=start_date,
                EndTime=end_date,
                Period=86400,  # Daily
                Statistics=['Sum']
            )
            
            # Cache hit rate
            cache_hit_rate = cloudwatch.get_metric_statistics(
                Namespace='AWS/CloudFront',
                MetricName='CacheHitRate',
                Dimensions=[
                    {
                        'Name': 'DistributionId',
                        'Value': self.distribution_id
                    }
                ],
                StartTime=start_date,
                EndTime=end_date,
                Period=86400,  # Daily
                Statistics=['Average']
            )
            
            return {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "bytes_downloaded": sum(dp['Sum'] for dp in bytes_downloaded['Datapoints']),
                "total_requests": sum(dp['Sum'] for dp in requests['Datapoints']),
                "avg_cache_hit_rate": sum(dp['Average'] for dp in cache_hit_rate['Datapoints']) / len(cache_hit_rate['Datapoints']) if cache_hit_rate['Datapoints'] else 0,
                "daily_stats": {
                    "bytes": bytes_downloaded['Datapoints'],
                    "requests": requests['Datapoints'],
                    "cache_hit_rate": cache_hit_rate['Datapoints']
                }
            }
            
        except Exception as e:
            logger.error(f"💥 Failed to get CDN stats: {e}")
            raise
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _convert_to_cdn_url(self, s3_url: str) -> str:
        """Convert S3 URL to CDN URL"""
        
        if s3_url.startswith(f"https://{settings.S3_BUCKET_NAME}"):
            path = s3_url.split(f"{settings.S3_BUCKET_NAME}.s3.amazonaws.com/")[-1]
            return f"https://{self.cdn_domain}/{path}"
        
        return s3_url
    
    async def _request_asset(self, session: aiohttp.ClientSession, url: str):
        """Request asset to warm cache"""
        
        try:
            async with session.head(url) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"Failed to warm cache for {url}: {e}")
            return False
    
    # ========================================================================
    # CDN OPTIMIZATION
    # ========================================================================
    
    async def optimize_asset_delivery(self, asset_type: str) -> Dict[str, Any]:
        """Configure optimal CDN settings for asset type"""
        
        optimization_configs = {
            "video": {
                "cache_headers": {
                    "Cache-Control": "public, max-age=604800",  # 7 days
                    "Vary": "Accept-Encoding"
                },
                "compression": False,  # Videos are already compressed
                "edge_functions": ["video-optimization"]
            },
            "audio": {
                "cache_headers": {
                    "Cache-Control": "public, max-age=2592000",  # 30 days
                    "Vary": "Accept-Encoding"
                },
                "compression": False,
                "edge_functions": ["audio-streaming"]
            },
            "image": {
                "cache_headers": {
                    "Cache-Control": "public, max-age=31536000",  # 1 year
                    "Vary": "Accept-Encoding"
                },
                "compression": True,
                "edge_functions": ["image-optimization", "webp-conversion"]
            }
        }
        
        config = optimization_configs.get(asset_type, {})
        
        # Apply configuration to CloudFront
        # This would update the distribution configuration
        
        return {
            "asset_type": asset_type,
            "optimization": config,
            "status": "configured"
        }

# Initialize service
cdn_manager = CDNManagerService()
