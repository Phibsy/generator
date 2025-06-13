# backend/app/api/assets.py
"""
📦 REELS GENERATOR - Asset Management API
Endpoints for asset library management
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from ..database import get_db
from ..models import User
from ..models.assets import Asset, AssetType, AssetStatus, AssetCollection, AssetUsage, CopyrightReport, LicenseType
from ..schemas.assets import (
    AssetResponse,
    AssetSearchParams,
    AssetUsageRequest,
    CopyrightReportRequest,
    AssetCollectionResponse
)
from ..services.asset_management import asset_service
from ..services.copyright_compliance import copyright_service
from ..services.cdn_manager import cdn_manager
from .auth import get_current_active_user

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()

# ============================================================================
# ASSET UPLOAD AND MANAGEMENT
# ============================================================================

@router.post("/upload", response_model=AssetResponse)
async def upload_asset(
    file: UploadFile = File(...),
    asset_type: AssetType = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    license_type: LicenseType = Form(LicenseType.ROYALTY_FREE),
    attribution_required: bool = Form(False),
    attribution_text: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_active_user)
) -> AssetResponse:
    """
    Upload a new asset to the library
    
    Supports videos, music, sound effects, images, fonts, and templates
    """
    
    # Prepare metadata
    metadata = {
        "name": name,
        "description": description,
        "license_type": license_type.value,
        "attribution_required": attribution_required,
        "attribution_text": attribution_text,
        "file_size": file.size,
        "tags": tags.split(",") if tags else []
    }
    
    try:
        # Upload asset
        asset = await asset_service.upload_asset(
            file_data=file.file,
            filename=file.filename,
            asset_type=asset_type,
            metadata=metadata,
            user_id=current_user.id
        )
        
        # Queue processing
        from ..tasks.asset_tasks import process_asset_task
        background_tasks.add_task(
            process_asset_task.delay,
            asset.id
        )
        
        return asset
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Asset upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Asset upload failed"
        )

@router.get("/search", response_model=Dict[str, Any])
async def search_assets(
    query: Optional[str] = Query(None),
    asset_type: Optional[AssetType] = Query(None),
    tags: Optional[List[str]] = Query(None),
    categories: Optional[List[str]] = Query(None),
    license_types: Optional[List[LicenseType]] = Query(None),
    min_duration: Optional[float] = Query(None),
    max_duration: Optional[float] = Query(None),
    sort_by: str = Query("popularity", regex="^(popularity|newest|usage|name)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Search assets with advanced filtering
    
    Supports filtering by type, tags, categories, license, duration, etc.
    """
    
    result = await asset_service.search_assets(
        query=query,
        asset_type=asset_type,
        tags=tags,
        categories=categories,
        license_types=license_types,
        min_duration=min_duration,
        max_duration=max_duration,
        sort_by=sort_by,
        limit=limit,
        offset=offset
    )
    
    return result

@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> AssetResponse:
    """Get detailed information about a specific asset"""
    
    result = await db.execute(
        select(Asset).where(Asset.asset_id == asset_id)
    )
    asset = result.scalar_one_or_none()
    
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )
    
    return asset

# ============================================================================
# ASSET COLLECTIONS
# ============================================================================

@router.get("/collections/featured", response_model=List[Dict[str, Any]])
async def get_featured_collections(
    current_user: User = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """Get featured asset collections"""
    
    collections = await asset_service.get_featured_collections()
    return collections

@router.get("/collections/{collection_id}")
async def get_collection_assets(
    collection_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Get assets in a specific collection"""
    
    # Map collection IDs to search parameters
    collection_mappings = {
        "viral_gaming": {"tags": ["gaming", "viral"], "asset_type": AssetType.BACKGROUND_VIDEO},
        "upbeat_music": {"tags": ["upbeat", "energetic"], "asset_type": AssetType.MUSIC},
        "nature_calm": {"tags": ["nature", "calm"], "asset_type": AssetType.BACKGROUND_VIDEO},
        "tech_modern": {"tags": ["tech", "modern"], "asset_type": AssetType.BACKGROUND_VIDEO}
    }
    
    if collection_id not in collection_mappings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found"
        )
    
    params = collection_mappings[collection_id]
    
    result = await asset_service.search_assets(
        **params,
        sort_by="popularity",
        limit=limit,
        offset=offset
    )
    
    return {
        "collection_id": collection_id,
        "assets": result["assets"],
        "total": result["total"],
        "limit": limit,
        "offset": offset
    }

# ============================================================================
# ASSET USAGE TRACKING
# ============================================================================

@router.post("/track-usage")
async def track_asset_usage(
    request: AssetUsageRequest,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, str]:
    """Track usage of an asset in a project"""
    
    try:
        usage = await asset_service.track_asset_usage(
            asset_id=request.asset_id,
            project_id=request.project_id,
            user_id=current_user.id,
            usage_type=request.usage_type,
            usage_duration=request.usage_duration,
            usage_context=request.usage_context
        )
        
        return {
            "status": "tracked",
            "usage_id": str(usage.id)
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

@router.get("/usage/history")
async def get_usage_history(
    asset_id: Optional[str] = Query(None),
    project_id: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """Get asset usage history"""
    
    query = select(AssetUsage).where(AssetUsage.user_id == current_user.id)
    
    if asset_id:
        query = query.join(Asset).where(Asset.asset_id == asset_id)
    
    if project_id:
        query = query.where(AssetUsage.project_id == project_id)
    
    if start_date:
        query = query.where(AssetUsage.used_at >= start_date)
    
    if end_date:
        query = query.where(AssetUsage.used_at <= end_date)
    
    result = await db.execute(query.options(selectinload(AssetUsage.asset)))
    usages = result.scalars().all()
    
    return [
        {
            "asset_id": usage.asset.asset_id,
            "asset_name": usage.asset.name,
            "project_id": usage.project_id,
            "usage_type": usage.usage_type,
            "used_at": usage.used_at.isoformat(),
            "duration": usage.usage_duration
        }
        for usage in usages
    ]

# ============================================================================
# COPYRIGHT COMPLIANCE
# ============================================================================

@router.post("/validate-usage")
async def validate_asset_usage(
    asset_id: str,
    usage_context: Dict[str, Any],
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Validate if asset usage complies with licensing"""
    
    # Add user context
    usage_context["user_id"] = current_user.id
    
    validation = await copyright_service.validate_asset_usage(
        asset_id=asset_id,
        usage_context=usage_context
    )
    
    return validation

@router.get("/compliance/report")
async def generate_compliance_report(
    project_id: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Generate copyright compliance report"""
    
    report = await copyright_service.generate_usage_report(
        user_id=current_user.id,
        project_id=project_id,
        start_date=start_date,
        end_date=end_date
    )
    
    return report

@router.post("/compliance/scan/{project_id}")
async def scan_project_compliance(
    project_id: int,
    current_user: User = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """Scan project for copyright compliance issues"""
    
    violations = await copyright_service.scan_for_violations(project_id)
    return violations

@router.post("/report-copyright")
async def report_copyright_issue(
    request: CopyrightReportRequest,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, str]:
    """Report a copyright issue with an asset"""
    
    try:
        report = await copyright_service.file_copyright_report(
            asset_id=request.asset_id,
            reporter_id=current_user.id,
            reason=request.reason,
            evidence_url=request.evidence_url
        )
        
        return {
            "status": "reported",
            "report_id": str(report.id)
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

# ============================================================================
# ASSET RECOMMENDATIONS
# ============================================================================

@router.get("/recommend/{project_id}")
async def get_asset_recommendations(
    project_id: int,
    asset_type: AssetType,
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_active_user)
) -> List[AssetResponse]:
    """Get AI-powered asset recommendations for a project"""
    
    try:
        recommendations = await asset_service.get_recommended_assets(
            project_id=project_id,
            asset_type=asset_type,
            limit=limit
        )
        
        return recommendations
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

# ============================================================================
# CDN MANAGEMENT
# ============================================================================

@router.post("/cdn/invalidate")
async def invalidate_cdn_cache(
    paths: List[str],
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, str]:
    """Invalidate CDN cache for specific assets"""
    
    # Check admin permission
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    invalidation_id = await cdn_manager.invalidate_cache(paths)
    
    return {
        "status": "invalidated",
        "invalidation_id": invalidation_id
    }

@router.get("/cdn/stats")
async def get_cdn_statistics(
    start_date: datetime,
    end_date: datetime,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Get CDN usage statistics"""
    
    # Check admin permission
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    stats = await cdn_manager.get_cdn_usage_stats(start_date, end_date)
    return stats

# ============================================================================
# BULK OPERATIONS
# ============================================================================

@router.post("/bulk/import")
async def bulk_import_assets(
    import_config: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Bulk import assets from external source"""
    
    # Check admin permission
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    from ..tasks.asset_tasks import bulk_import_assets_task
    
    # Queue bulk import task
    task = bulk_import_assets_task.delay(
        import_config,
        current_user.id
    )
    
    return {
        "status": "importing",
        "task_id": task.id,
        "message": "Bulk import started. Check task status for progress."
    }
