# backend/app/models/assets.py
"""
🎮 REELS GENERATOR - Asset Management Models
Database models for media assets and licensing
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey, Enum as SQLEnum, Float, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum
import uuid

from ..database import Base

# ============================================================================
# ENUMS
# ============================================================================

class AssetType(str, Enum):
    BACKGROUND_VIDEO = "background_video"
    MUSIC = "music"
    SOUND_EFFECT = "sound_effect"
    IMAGE = "image"
    FONT = "font"
    TEMPLATE = "template"

class AssetStatus(str, Enum):
    PROCESSING = "processing"
    ACTIVE = "active"
    ARCHIVED = "archived"
    FAILED = "failed"

class LicenseType(str, Enum):
    ROYALTY_FREE = "royalty_free"
    CREATIVE_COMMONS = "creative_commons"
    PURCHASED = "purchased"
    CUSTOM = "custom"
    PUBLIC_DOMAIN = "public_domain"

class ContentRating(str, Enum):
    GENERAL = "general"
    TEEN = "teen"
    MATURE = "mature"

# ============================================================================
# ASSET MODEL
# ============================================================================

class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        Index('idx_asset_type_status', 'asset_type', 'status'),
        Index('idx_asset_tags', 'tags', postgresql_using='gin'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(String(100), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    
    # Basic Information
    name = Column(String(200), nullable=False)
    description = Column(Text)
    asset_type = Column(SQLEnum(AssetType), nullable=False, index=True)
    status = Column(SQLEnum(AssetStatus), default=AssetStatus.PROCESSING)
    
    # File Information
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)  # bytes
    file_format = Column(String(50))
    duration = Column(Float)  # seconds (for video/audio)
    resolution = Column(String(50))  # e.g., "1920x1080"
    
    # CDN Information
    cdn_url = Column(String(500))
    thumbnail_url = Column(String(500))
    preview_url = Column(String(500))
    
    # Metadata
    metadata = Column(JSON, default={})
    tags = Column(JSON, default=[])  # AI-generated tags
    categories = Column(JSON, default=[])
    
    # Content Analysis
    content_rating = Column(SQLEnum(ContentRating), default=ContentRating.GENERAL)
    energy_level = Column(Float)  # 0-1 scale for music/video energy
    tempo = Column(Integer)  # BPM for music
    dominant_colors = Column(JSON)  # For visual assets
    
    # Licensing
    license_type = Column(SQLEnum(LicenseType), nullable=False)
    license_details = Column(JSON, default={})
    attribution_required = Column(Boolean, default=False)
    attribution_text = Column(Text)
    
    # Usage Tracking
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime)
    popularity_score = Column(Float, default=0.0)
    
    # Source Information
    source_url = Column(String(500))
    source_attribution = Column(String(500))
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    uploader = relationship("User", backref="uploaded_assets")
    usage_logs = relationship("AssetUsage", back_populates="asset")
    collections = relationship("CollectionAsset", back_populates="asset")
    
    def __repr__(self):
        return f"<Asset(name='{self.name}', type='{self.asset_type}')>"

# ============================================================================
# ASSET COLLECTION MODEL
# ============================================================================

class AssetCollection(Base):
    __tablename__ = "asset_collections"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    collection_type = Column(String(50))  # e.g., "gameplay", "music_pack"
    
    # Metadata
    tags = Column(JSON, default=[])
    is_featured = Column(Boolean, default=False)
    is_public = Column(Boolean, default=True)
    
    # Creator
    created_by = Column(Integer, ForeignKey("users.id"))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    creator = relationship("User", backref="asset_collections")
    assets = relationship("CollectionAsset", back_populates="collection")

# ============================================================================
# COLLECTION ASSET ASSOCIATION
# ============================================================================

class CollectionAsset(Base):
    __tablename__ = "collection_assets"
    
    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, ForeignKey("asset_collections.id"))
    asset_id = Column(Integer, ForeignKey("assets.id"))
    
    # Order in collection
    sort_order = Column(Integer, default=0)
    
    # Timestamps
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    collection = relationship("AssetCollection", back_populates="assets")
    asset = relationship("Asset", back_populates="collections")

# ============================================================================
# ASSET USAGE TRACKING
# ============================================================================

class AssetUsage(Base):
    __tablename__ = "asset_usage"
    __table_args__ = (
        Index('idx_usage_asset_project', 'asset_id', 'project_id'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Usage Details
    usage_type = Column(String(50))  # e.g., "background", "music", "effect"
    usage_duration = Column(Float)  # seconds used
    usage_context = Column(JSON, default={})
    
    # Timestamps
    used_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    asset = relationship("Asset", back_populates="usage_logs")
    project = relationship("Project")
    user = relationship("User")

# ============================================================================
# COPYRIGHT REPORT MODEL
# ============================================================================

class CopyrightReport(Base):
    __tablename__ = "copyright_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    reported_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Report Details
    reason = Column(Text, nullable=False)
    evidence_url = Column(String(500))
    status = Column(String(50), default="pending")  # pending, resolved, dismissed
    resolution = Column(Text)
    
    # Timestamps
    reported_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime)
    
    # Relationships
    asset = relationship("Asset")
    reporter = relationship("User")
