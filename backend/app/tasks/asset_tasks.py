# backend/app/tasks/asset_tasks.py
"""
📦 REELS GENERATOR - Asset Processing Tasks
Celery tasks for asset management and processing
"""

from celery import shared_task, Task
from typing import Dict, Any, List
import logging
from datetime import datetime

from ..services.asset_management import asset_service
from ..services.asset_analysis import asset_analysis_service
from ..services.cdn_manager import cdn_manager
from ..database import AsyncSessionLocal
from ..models.assets import Asset, AssetStatus
from sqlalchemy import select, update

logger = logging.getLogger(__name__)

# ============================================================================
# ASSET PROCESSING TASKS
# ============================================================================

@shared_task(
    bind=True,
    name="process_asset",
    queue="content",
    max_retries=3
)
def process_asset_task(self: Task, asset_id: int) -> Dict[str, Any]:
    """
    Process newly uploaded asset
    
    - Analyze content
    - Generate tags and metadata
    - Create thumbnails/previews
    - Update CDN
    """
    
    task_id = self.request.id
    logger.info(f"Processing asset {asset_id}")
    
    try:
        self.update_progress(task_id, 0, "loading_asset")
        
        # Get asset
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            asset = loop.run_until_complete(get_asset_by_id(asset_id))
            
            if not asset:
                raise ValueError(f"Asset {asset_id} not found")
            
            self.update_progress(task_id, 20, "analyzing_content")
            
            # Analyze asset
            analysis_result = loop.run_until_complete(
                asset_analysis_service.analyze_asset(asset)
            )
            
            self.update_progress(task_id, 60, "generating_previews")
            
            # Generate previews
            preview_urls = loop.run_until_complete(
                generate_asset_previews(asset)
            )
            
            self.update_progress(task_id, 80, "updating_cdn")
            
            # Warm CDN cache
            loop.run_until_complete(
                cdn_manager.warm_cache([asset.cdn_url] + preview_urls)
            )
            
            self.update_progress(task_id, 100, "completed")
            
            logger.info(f"✅ Asset {asset_id} processed successfully")
            
            return {
                "asset_id": asset_id,
                "status": "processed",
                "analysis": analysis_result,
                "previews": preview_urls
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Asset processing failed: {e}")
        
        # Update asset status to failed
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            update_asset_status(asset_id, AssetStatus.FAILED)
        )
        loop.close()
        
        raise self.retry(exc=e)

@shared_task(
    bind=True,
    name="bulk_import_assets",
    queue="content",
    max_retries=1
)
def bulk_import_assets_task(
    self: Task,
    import_config: Dict[str, Any],
    user_id: int
) -> Dict[str, Any]:
    """
    Bulk import assets from external source
    
    Supports importing from:
    - S3 bucket
    - External URLs
    - Asset packs
    """
    
    task_id = self.request.id
    logger.info(f"Starting bulk import: {import_config['source']}")
    
    results = {
        "imported": 0,
        "failed": 0,
        "errors": []
    }
    
    try:
        self.update_progress(task_id, 0, "initializing")
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Get asset list
            assets_to_import = loop.run_until_complete(
                get_import_asset_list(import_config)
            )
            
            total = len(assets_to_import)
            
            for i, asset_info in enumerate(assets_to_import):
                progress = (i / total) * 100
                self.update_progress(
                    task_id,
                    progress,
                    f"importing_{i+1}_of_{total}"
                )
                
                try:
                    # Import individual asset
                    loop.run_until_complete(
                        import_single_asset(asset_info, user_id)
                    )
                    results["imported"] += 1
                    
                except Exception as e:
                    logger.error(f"Failed to import {asset_info['url']}: {e}")
                    results["failed"] += 1
                    results["errors"].append({
                        "asset": asset_info["url"],
                        "error": str(e)
                    })
            
            self.update_progress(task_id, 100, "completed")
            
            logger.info(f"✅ Bulk import completed: {results['imported']} imported, {results['failed']} failed")
            
            return results
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Bulk import failed: {e}")
        raise

@shared_task(
    name="cleanup_unused_assets",
    queue="celery"
)
def cleanup_unused_assets_task() -> Dict[str, Any]:
    """
    Clean up assets that haven't been used in 90 days
    
    Scheduled task that runs monthly
    """
    
    try:
        import asyncio
        from datetime import timedelta
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=90)
            
            # Find unused assets
            unused_assets = loop.run_until_complete(
                find_unused_assets(cutoff_date)
            )
            
            archived = 0
            
            for asset in unused_assets:
                # Archive instead of delete
                loop.run_until_complete(
                    update_asset_status(asset.id, AssetStatus.ARCHIVED)
                )
                archived += 1
            
            logger.info(f"Archived {archived} unused assets")
            
            return {
                "archived": archived,
                "cutoff_date": cutoff_date.isoformat()
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Asset cleanup failed: {e}")
        raise

@shared_task(
    name="update_asset_popularity",
    queue="celery"
)
def update_asset_popularity_task() -> Dict[str, Any]:
    """
    Update asset popularity scores based on usage
    
    Scheduled task that runs daily
    """
    
    try:
        import asyncio
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Get all active assets
            assets = loop.run_until_complete(get_active_assets())
            
            updated = 0
            
            for asset in assets:
                # Recalculate popularity
                new_score = loop.run_until_complete(
                    calculate_asset_popularity(asset)
                )
                
                # Update if changed
                if abs(asset.popularity_score - new_score) > 0.01:
                    loop.run_until_complete(
                        update_asset_popularity(asset.id, new_score)
                    )
                    updated += 1
            
            logger.info(f"Updated popularity for {updated} assets")
            
            return {
                "total_assets": len(assets),
                "updated": updated
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Popularity update failed: {e}")
        raise

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def get_asset_by_id(asset_id: int) -> Optional[Asset]:
    """Get asset by ID"""
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Asset).where(Asset.id == asset_id)
        )
        return result.scalar_one_or_none()

async def update_asset_status(asset_id: int, status: AssetStatus):
    """Update asset status"""
    
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Asset)
            .where(Asset.id == asset_id)
            .values(status=status, updated_at=datetime.utcnow())
        )
        await db.commit()

async def generate_asset_previews(asset: Asset) -> List[str]:
    """Generate preview files for asset"""
    
    preview_urls = []
    
    if asset.asset_type == AssetType.BACKGROUND_VIDEO:
        # Generate thumbnail
        from ..utils.ffmpeg_utils import ffmpeg_utils
        
        thumbnail_path = await ffmpeg_utils.create_thumbnail(
            Path(asset.file_path),
            Path(f"/tmp/thumb_{asset.asset_id}.jpg")
        )
        
        # Upload to S3
        thumbnail_key = f"previews/videos/{asset.asset_id}_thumb.jpg"
        thumbnail_url = await storage_service.upload_file(
            open(thumbnail_path, 'rb'),
            thumbnail_key
        )
        
        preview_urls.append(thumbnail_url)
        
        # Update asset
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Asset)
                .where(Asset.id == asset.id)
                .values(thumbnail_url=thumbnail_url)
            )
            await db.commit()
    
    elif asset.asset_type == AssetType.MUSIC:
        # Generate waveform visualization
        # Implementation would create waveform image
        pass
    
    return preview_urls

async def get_import_asset_list(import_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get list of assets to import based on config"""
    
    assets = []
    
    if import_config["source"] == "s3_bucket":
        # List objects in S3 bucket
        import boto3
        
        s3 = boto3.client('s3')
        response = s3.list_objects_v2(
            Bucket=import_config["bucket"],
            Prefix=import_config.get("prefix", "")
        )
        
        for obj in response.get('Contents', []):
            assets.append({
                "url": f"s3://{import_config['bucket']}/{obj['Key']}",
                "key": obj['Key'],
                "size": obj['Size']
            })
    
    elif import_config["source"] == "url_list":
        # Import from list of URLs
        for url in import_config["urls"]:
            assets.append({"url": url})
    
    return assets

async def import_single_asset(asset_info: Dict[str, Any], user_id: int):
    """Import a single asset"""
    
    # Download asset
    # Analyze and process
    # Save to library
    
    # Simplified implementation
    pass

async def find_unused_assets(cutoff_date: datetime) -> List[Asset]:
    """Find assets not used since cutoff date"""
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Asset).where(
                Asset.status == AssetStatus.ACTIVE,
                or_(
                    Asset.last_used_at < cutoff_date,
                    Asset.last_used_at.is_(None)
                )
            )
        )
        return result.scalars().all()

async def get_active_assets() -> List[Asset]:
    """Get all active assets"""
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Asset).where(Asset.status == AssetStatus.ACTIVE)
        )
        return result.scalars().all()

async def calculate_asset_popularity(asset: Asset) -> float:
    """Calculate asset popularity score"""
    
    # Get recent usage stats
    async with AsyncSessionLocal() as db:
        from sqlalchemy import func
        
        # Usage in last 30 days
        recent_usage = await db.scalar(
            select(func.count(AssetUsage.id))
            .where(
                AssetUsage.asset_id == asset.id,
                AssetUsage.used_at >= datetime.utcnow() - timedelta(days=30)
            )
        )
        
        # Calculate score (simplified)
        base_score = asset.usage_count * 0.1
        recent_boost = recent_usage * 0.5
        
        return min(100.0, base_score + recent_boost)

async def update_asset_popularity(asset_id: int, score: float):
    """Update asset popularity score"""
    
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Asset)
            .where(Asset.id == asset_id)
            .values(popularity_score=score)
        )
        await db.commit()
