# backend/app/services/asset_management.py
"""
📦 REELS GENERATOR - Asset Management Service
Core service for managing media assets
"""

import asyncio
from pathlib import Path
import json
import uuid
from typing import Dict, Any, List, Optional, BinaryIO
import logging
import hashlib
from datetime import datetime
import mimetypes

from ..config import settings
from ..services.file_storage import storage_service
from ..database import AsyncSessionLocal
from ..models.assets import Asset, AssetType, AssetStatus, LicenseType, AssetUsage
from sqlalchemy import select, update, and_, or_, func
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

class AssetManagementService:
    """Service for comprehensive asset management"""
    
    def __init__(self):
        self.s3_bucket = settings.S3_BUCKET_NAME
        self.cdn_url = f"https://cdn.reelsgenerator.com"
        
        # Asset organization structure
        self.asset_paths = {
            AssetType.BACKGROUND_VIDEO: "assets/backgrounds/videos",
            AssetType.MUSIC: "assets/music",
            AssetType.SOUND_EFFECT: "assets/sounds",
            AssetType.IMAGE: "assets/images",
            AssetType.FONT: "assets/fonts",
            AssetType.TEMPLATE: "assets/templates"
        }
        
        # File format validation
        self.allowed_formats = {
            AssetType.BACKGROUND_VIDEO: ["mp4", "mov", "avi", "webm"],
            AssetType.MUSIC: ["mp3", "wav", "m4a", "ogg"],
            AssetType.SOUND_EFFECT: ["mp3", "wav", "ogg"],
            AssetType.IMAGE: ["jpg", "jpeg", "png", "gif", "webp"],
            AssetType.FONT: ["ttf", "otf", "woff", "woff2"],
            AssetType.TEMPLATE: ["json", "yaml"]
        }
    
    # ========================================================================
    # ASSET UPLOAD AND REGISTRATION
    # ========================================================================
    
    async def upload_asset(
        self,
        file_data: BinaryIO,
        filename: str,
        asset_type: AssetType,
        metadata: Dict[str, Any],
        user_id: int
    ) -> Asset:
        """Upload and register a new asset"""
        
        try:
            # Validate file format
            file_ext = filename.split('.')[-1].lower()
            if file_ext not in self.allowed_formats.get(asset_type, []):
                raise ValueError(f"Invalid file format for {asset_type}: {file_ext}")
            
            # Generate unique asset ID
            asset_id = str(uuid.uuid4())
            
            # Calculate file hash for deduplication
            file_hash = await self._calculate_file_hash(file_data)
            
            # Check for duplicates
            existing = await self._find_duplicate_asset(file_hash)
            if existing:
                logger.info(f"Duplicate asset detected: {existing.asset_id}")
                return existing
            
            # Prepare S3 key
            s3_key = f"{self.asset_paths[asset_type]}/{asset_id}/{filename}"
            
            # Upload to S3
            file_data.seek(0)
            s3_url = await storage_service.upload_file(
                file_data,
                s3_key,
                content_type=mimetypes.guess_type(filename)[0]
            )
            
            # Create database record
            async with AsyncSessionLocal() as db:
                asset = Asset(
                    asset_id=asset_id,
                    name=metadata.get("name", filename),
                    description=metadata.get("description", ""),
                    asset_type=asset_type,
                    status=AssetStatus.PROCESSING,
                    file_path=s3_key,
                    file_size=metadata.get("file_size", 0),
                    file_format=file_ext,
                    cdn_url=f"{self.cdn_url}/{s3_key}",
                    license_type=LicenseType(metadata.get("license_type", "royalty_free")),
                    license_details=metadata.get("license_details", {}),
                    attribution_required=metadata.get("attribution_required", False),
                    attribution_text=metadata.get("attribution_text", ""),
                    source_url=metadata.get("source_url", ""),
                    source_attribution=metadata.get("source_attribution", ""),
                    uploaded_by=user_id,
                    metadata={
                        "original_filename": filename,
                        "file_hash": file_hash,
                        **metadata.get("custom_metadata", {})
                    }
                )
                
                db.add(asset)
                await db.commit()
                await db.refresh(asset)
                
                logger.info(f"✅ Asset uploaded: {asset.asset_id}")
                
                # Queue processing tasks
                await self._queue_asset_processing(asset)
                
                return asset
                
        except Exception as e:
            logger.error(f"💥 Asset upload failed: {e}")
            raise
    
    # ========================================================================
    # ASSET SEARCH AND DISCOVERY
    # ========================================================================
    
    async def search_assets(
        self,
        query: Optional[str] = None,
        asset_type: Optional[AssetType] = None,
        tags: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        license_types: Optional[List[LicenseType]] = None,
        min_duration: Optional[float] = None,
        max_duration: Optional[float] = None,
        sort_by: str = "popularity",
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Search assets with advanced filtering"""
        
        async with AsyncSessionLocal() as db:
            # Build query
            query_obj = select(Asset).where(Asset.status == AssetStatus.ACTIVE)
            
            # Apply filters
            if asset_type:
                query_obj = query_obj.where(Asset.asset_type == asset_type)
            
            if query:
                search_term = f"%{query}%"
                query_obj = query_obj.where(
                    or_(
                        Asset.name.ilike(search_term),
                        Asset.description.ilike(search_term)
                    )
                )
            
            if tags:
                # PostgreSQL JSON containment
                for tag in tags:
                    query_obj = query_obj.where(
                        Asset.tags.contains([tag])
                    )
            
            if categories:
                for category in categories:
                    query_obj = query_obj.where(
                        Asset.categories.contains([category])
                    )
            
            if license_types:
                query_obj = query_obj.where(Asset.license_type.in_(license_types))
            
            if min_duration is not None:
                query_obj = query_obj.where(Asset.duration >= min_duration)
            
            if max_duration is not None:
                query_obj = query_obj.where(Asset.duration <= max_duration)
            
            # Apply sorting
            if sort_by == "popularity":
                query_obj = query_obj.order_by(Asset.popularity_score.desc())
            elif sort_by == "newest":
                query_obj = query_obj.order_by(Asset.created_at.desc())
            elif sort_by == "usage":
                query_obj = query_obj.order_by(Asset.usage_count.desc())
            elif sort_by == "name":
                query_obj = query_obj.order_by(Asset.name)
            
            # Count total
            count_query = select(func.count()).select_from(query_obj.subquery())
            total = await db.scalar(count_query)
            
            # Apply pagination
            query_obj = query_obj.offset(offset).limit(limit)
            
            # Execute query
            result = await db.execute(query_obj)
            assets = result.scalars().all()
            
            return {
                "assets": assets,
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total
            }
    
    # ========================================================================
    # ASSET USAGE TRACKING
    # ========================================================================
    
    async def track_asset_usage(
        self,
        asset_id: str,
        project_id: int,
        user_id: int,
        usage_type: str,
        usage_duration: Optional[float] = None,
        usage_context: Optional[Dict[str, Any]] = None
    ) -> AssetUsage:
        """Track asset usage for analytics and licensing"""
        
        async with AsyncSessionLocal() as db:
            # Get asset
            result = await db.execute(
                select(Asset).where(Asset.asset_id == asset_id)
            )
            asset = result.scalar_one_or_none()
            
            if not asset:
                raise ValueError(f"Asset not found: {asset_id}")
            
            # Create usage record
            usage = AssetUsage(
                asset_id=asset.id,
                project_id=project_id,
                user_id=user_id,
                usage_type=usage_type,
                usage_duration=usage_duration,
                usage_context=usage_context or {}
            )
            
            db.add(usage)
            
            # Update asset statistics
            asset.usage_count += 1
            asset.last_used_at = datetime.utcnow()
            
            # Update popularity score (simple algorithm)
            asset.popularity_score = self._calculate_popularity_score(
                asset.usage_count,
                asset.created_at,
                asset.last_used_at
            )
            
            await db.commit()
            await db.refresh(usage)
            
            logger.info(f"📊 Tracked usage of asset {asset_id} in project {project_id}")
            
            return usage
    
    # ========================================================================
    # ASSET COLLECTIONS
    # ========================================================================
    
    async def get_featured_collections(self) -> List[Dict[str, Any]]:
        """Get featured asset collections"""
        
        # Pre-defined collections
        collections = [
            {
                "id": "viral_gaming",
                "name": "Viral Gaming Backgrounds",
                "description": "Popular gaming footage for engaging content",
                "asset_count": 25,
                "preview_assets": await self._get_collection_previews("gaming", 4)
            },
            {
                "id": "upbeat_music",
                "name": "Upbeat Music Pack",
                "description": "High-energy tracks perfect for viral content",
                "asset_count": 30,
                "preview_assets": await self._get_collection_previews("upbeat", 4)
            },
            {
                "id": "nature_calm",
                "name": "Nature & Calm",
                "description": "Peaceful backgrounds for educational content",
                "asset_count": 20,
                "preview_assets": await self._get_collection_previews("nature", 4)
            },
            {
                "id": "tech_modern",
                "name": "Tech & Modern",
                "description": "Futuristic visuals for tech content",
                "asset_count": 15,
                "preview_assets": await self._get_collection_previews("tech", 4)
            }
        ]
        
        return collections
    
    # ========================================================================
    # ASSET RECOMMENDATIONS
    # ========================================================================
    
    async def get_recommended_assets(
        self,
        project_id: int,
        asset_type: AssetType,
        limit: int = 10
    ) -> List[Asset]:
        """Get AI-powered asset recommendations for a project"""
        
        async with AsyncSessionLocal() as db:
            # Get project details
            from ..models import Project
            result = await db.execute(
                select(Project).where(Project.id == project_id)
            )
            project = result.scalar_one_or_none()
            
            if not project:
                raise ValueError(f"Project not found: {project_id}")
            
            # Get recommendations based on project characteristics
            recommendations = await self._generate_recommendations(
                project,
                asset_type,
                limit
            )
            
            return recommendations
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    async def _calculate_file_hash(self, file_data: BinaryIO) -> str:
        """Calculate SHA256 hash of file for deduplication"""
        sha256_hash = hashlib.sha256()
        
        # Read file in chunks
        for chunk in iter(lambda: file_data.read(4096), b""):
            sha256_hash.update(chunk)
        
        file_data.seek(0)  # Reset file pointer
        return sha256_hash.hexdigest()
    
    async def _find_duplicate_asset(self, file_hash: str) -> Optional[Asset]:
        """Find existing asset with same file hash"""
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Asset).where(
                    Asset.metadata["file_hash"].astext == file_hash,
                    Asset.status == AssetStatus.ACTIVE
                )
            )
            return result.scalar_one_or_none()
    
    async def _queue_asset_processing(self, asset: Asset):
        """Queue processing tasks for new asset"""
        
        from ..tasks.asset_tasks import process_asset_task
        
        # Submit processing task
        process_asset_task.delay(asset.id)
    
    def _calculate_popularity_score(
        self,
        usage_count: int,
        created_at: datetime,
        last_used_at: Optional[datetime]
    ) -> float:
        """Calculate asset popularity score"""
        
        # Simple popularity algorithm
        # Score = usage_count * recency_factor * freshness_factor
        
        now = datetime.utcnow()
        
        # Recency factor (how recently used)
        if last_used_at:
            days_since_use = (now - last_used_at).days
            recency_factor = 1.0 / (1.0 + days_since_use * 0.1)
        else:
            recency_factor = 0.5
        
        # Freshness factor (newer assets get slight boost)
        days_since_creation = (now - created_at).days
        freshness_factor = 1.0 / (1.0 + days_since_creation * 0.01)
        
        score = usage_count * recency_factor * freshness_factor
        
        return min(100.0, score)  # Cap at 100
    
    async def _get_collection_previews(
        self,
        tag: str,
        limit: int
    ) -> List[Dict[str, str]]:
        """Get preview assets for a collection"""
        
        result = await self.search_assets(
            tags=[tag],
            sort_by="popularity",
            limit=limit
        )
        
        return [
            {
                "id": asset.asset_id,
                "thumbnail_url": asset.thumbnail_url,
                "name": asset.name
            }
            for asset in result["assets"]
        ]
    
    async def _generate_recommendations(
        self,
        project: Any,
        asset_type: AssetType,
        limit: int
    ) -> List[Asset]:
        """Generate AI-powered recommendations"""
        
        # Extract project characteristics
        tags = []
        
        if project.video_style:
            tags.append(project.video_style)
        
        if project.target_audience:
            if "young" in project.target_audience.lower():
                tags.extend(["energetic", "trendy", "viral"])
            elif "professional" in project.target_audience.lower():
                tags.extend(["professional", "clean", "minimal"])
        
        # Search for matching assets
        result = await self.search_assets(
            tags=tags,
            asset_type=asset_type,
            sort_by="popularity",
            limit=limit
        )
        
        return result["assets"]

# Initialize service
asset_service = AssetManagementService()
