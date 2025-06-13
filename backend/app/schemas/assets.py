# backend/app/schemas/assets.py
"""
📋 REELS GENERATOR - Asset Management Schemas
Pydantic schemas for asset-related requests and responses
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from ..models.assets import AssetType, AssetStatus, LicenseType, ContentRating

# ============================================================================
# ASSET SCHEMAS
# ============================================================================

class AssetBase(BaseModel):
    """Base asset schema"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    asset_type: AssetType
    tags: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)

class AssetCreate(AssetBase):
    """Schema for asset creation"""
    license_type: LicenseType
    attribution_required: bool = False
    attribution_text: Optional[str] = None
    source_url: Optional[str] = None
    source_attribution: Optional[str] = None

class AssetUpdate(BaseModel):
    """Schema for asset updates"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    tags: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    attribution_text: Optional[str] = None

class AssetResponse(AssetBase):
    """Schema for asset response"""
    id: int
    asset_id: str
    status: AssetStatus
    file_path: str
    file_size: Optional[int] = None
    file_format: Optional[str] = None
    duration: Optional[float] = None
    resolution: Optional[str] = None
    cdn_url: str
    thumbnail_url: Optional[str] = None
    preview_url: Optional[str] = None
    content_rating: ContentRating
    energy_level: Optional[float] = None
    tempo: Optional[int] = None
    dominant_colors: List[str] = Field(default_factory=list)
    license_type: LicenseType
    license_details: Dict[str, Any] = Field(default_factory=dict)
    attribution_required: bool
    attribution_text: Optional[str] = None
    usage_count: int
    popularity_score: float
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# ============================================================================
# ASSET SEARCH SCHEMAS
# ============================================================================

class AssetSearchParams(BaseModel):
    """Schema for asset search parameters"""
    query: Optional[str] = None
    asset_type: Optional[AssetType] = None
    tags: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    license_types: Optional[List[LicenseType]] = None
    min_duration: Optional[float] = Field(None, ge=0)
    max_duration: Optional[float] = Field(None, ge=0)
    sort_by: str = Field(default="popularity", regex="^(popularity|newest|usage|name)$")
    
    @validator('max_duration')
    def validate_duration_range(cls, v, values):
        if v is not None and 'min_duration' in values and values['min_duration'] is not None:
            if v < values['min_duration']:
                raise ValueError('max_duration must be greater than min_duration')
        return v

# ============================================================================
# ASSET USAGE SCHEMAS
# ============================================================================

class AssetUsageRequest(BaseModel):
    """Schema for tracking asset usage"""
    asset_id: str
    project_id: int
    usage_type: str = Field(..., min_length=1, max_length=50)
    usage_duration: Optional[float] = Field(None, ge=0)
    usage_context: Dict[str, Any] = Field(default_factory=dict)

class AssetUsageResponse(BaseModel):
    """Schema for asset usage response"""
    id: int
    asset_id: int
    project_id: int
    user_id: int
    usage_type: str
    usage_duration: Optional[float] = None
    used_at: datetime
    
    class Config:
        from_attributes = True

# ============================================================================
# COPYRIGHT SCHEMAS
# ============================================================================

class CopyrightReportRequest(BaseModel):
    """Schema for copyright report request"""
    asset_id: str
    reason: str = Field(..., min_length=10, max_length=1000)
    evidence_url: Optional[str] = Field(None, max_length=500)

class CopyrightReportResponse(BaseModel):
    """Schema for copyright report response"""
    id: int
    asset_id: int
    reported_by: int
    reason: str
    evidence_url: Optional[str] = None
    status: str
    reported_at: datetime
    resolved_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# ============================================================================
# COLLECTION SCHEMAS
# ============================================================================

class AssetCollectionBase(BaseModel):
    """Base collection schema"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    tags: List[str] = Field(default_factory=list)

class AssetCollectionCreate(AssetCollectionBase):
    """Schema for collection creation"""
    collection_type: Optional[str] = None
    is_public: bool = True

class AssetCollectionResponse(AssetCollectionBase):
    """Schema for collection response"""
    id: int
    collection_type: Optional[str] = None
    is_featured: bool
    is_public: bool
    created_by: int
    created_at: datetime
    asset_count: Optional[int] = None
    
    class Config:
        from_attributes = True

# ============================================================================
# COMPLIANCE SCHEMAS
# ============================================================================

class ComplianceValidationRequest(BaseModel):
    """Schema for compliance validation request"""
    asset_id: str
    usage_context: Dict[str, Any]

class ComplianceValidationResponse(BaseModel):
    """Schema for compliance validation response"""
    valid: bool
    asset_id: Optional[str] = None
    license_type: Optional[LicenseType] = None
    attribution_required: Optional[bool] = None
    attribution_text: Optional[str] = None
    restrictions: List[str] = Field(default_factory=list)
    reason: Optional[str] = None

class ComplianceReportResponse(BaseModel):
    """Schema for compliance report response"""
    total_uses: int
    period: Dict[str, Optional[str]]
    by_license_type: Dict[str, int]
    attribution_required: List[Dict[str, Any]]
    commercial_use: List[Dict[str, Any]]
    detailed_usage: List[Dict[str, Any]]

# ============================================================================
# BULK OPERATION SCHEMAS
# ============================================================================

class BulkImportConfig(BaseModel):
    """Schema for bulk import configuration"""
    source: str = Field(..., regex="^(s3_bucket|url_list|asset_pack)$")
    bucket: Optional[str] = None
    prefix: Optional[str] = None
    urls: Optional[List[str]] = None
    asset_type: AssetType
    default_license: LicenseType = LicenseType.ROYALTY_FREE
    auto_analyze: bool = True
