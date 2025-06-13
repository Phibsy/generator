# backend/app/services/copyright_compliance.py
"""
©️ REELS GENERATOR - Copyright Compliance Service
Ensure legal compliance for all assets
"""

import asyncio
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta
import hashlib
import json

from ..database import AsyncSessionLocal
from ..models.assets import Asset, AssetUsage, CopyrightReport, LicenseType
from sqlalchemy import select, and_, func

logger = logging.getLogger(__name__)

class CopyrightComplianceService:
    """Service for copyright and licensing compliance"""
    
    def __init__(self):
        self.attribution_templates = {
            LicenseType.CREATIVE_COMMONS: "'{title}' by {author} is licensed under {license}. Source: {source}",
            LicenseType.ROYALTY_FREE: "Music: '{title}' from {source}",
            LicenseType.PURCHASED: "Licensed from {source}",
            LicenseType.CUSTOM: "{custom_attribution}",
            LicenseType.PUBLIC_DOMAIN: "Public Domain"
        }
    
    # ========================================================================
    # LICENSE VALIDATION
    # ========================================================================
    
    async def validate_asset_usage(
        self,
        asset_id: str,
        usage_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate if asset usage complies with license"""
        
        async with AsyncSessionLocal() as db:
            # Get asset
            result = await db.execute(
                select(Asset).where(Asset.asset_id == asset_id)
            )
            asset = result.scalar_one_or_none()
            
            if not asset:
                return {
                    "valid": False,
                    "reason": "Asset not found"
                }
            
            # Check license restrictions
            validation_result = await self._check_license_restrictions(
                asset,
                usage_context
            )
            
            if not validation_result["valid"]:
                return validation_result
            
            # Check usage limits
            usage_limits = await self._check_usage_limits(asset, usage_context)
            
            if not usage_limits["valid"]:
                return usage_limits
            
            # Generate attribution if required
            attribution = None
            if asset.attribution_required:
                attribution = self._generate_attribution(asset)
            
            return {
                "valid": True,
                "asset_id": asset.asset_id,
                "license_type": asset.license_type,
                "attribution_required": asset.attribution_required,
                "attribution_text": attribution,
                "restrictions": asset.license_details.get("restrictions", [])
            }
    
    # ========================================================================
    # USAGE REPORTING
    # ========================================================================
    
    async def generate_usage_report(
        self,
        user_id: Optional[int] = None,
        project_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Generate comprehensive usage report for compliance"""
        
        async with AsyncSessionLocal() as db:
            # Build query
            query = select(AssetUsage).join(Asset)
            
            if user_id:
                query = query.where(AssetUsage.user_id == user_id)
            
            if project_id:
                query = query.where(AssetUsage.project_id == project_id)
            
            if start_date:
                query = query.where(AssetUsage.used_at >= start_date)
            
            if end_date:
                query = query.where(AssetUsage.used_at <= end_date)
            
            # Execute query
            result = await db.execute(query.options(selectinload(AssetUsage.asset)))
            usages = result.scalars().all()
            
            # Compile report
            report = {
                "total_uses": len(usages),
                "period": {
                    "start": start_date.isoformat() if start_date else None,
                    "end": end_date.isoformat() if end_date else None
                },
                "by_license_type": {},
                "attribution_required": [],
                "commercial_use": [],
                "detailed_usage": []
            }
            
            for usage in usages:
                asset = usage.asset
                
                # Count by license type
                license_type = asset.license_type.value
                if license_type not in report["by_license_type"]:
                    report["by_license_type"][license_type] = 0
                report["by_license_type"][license_type] += 1
                
                # Track attribution requirements
                if asset.attribution_required:
                    report["attribution_required"].append({
                        "asset_id": asset.asset_id,
                        "asset_name": asset.name,
                        "attribution": self._generate_attribution(asset),
                        "used_at": usage.used_at.isoformat()
                    })
                
                # Track commercial use
                if usage.usage_context.get("commercial", False):
                    report["commercial_use"].append({
                        "asset_id": asset.asset_id,
                        "asset_name": asset.name,
                        "license_type": asset.license_type.value,
                        "allows_commercial": asset.license_details.get("commercial_use", True)
                    })
                
                # Detailed usage
                report["detailed_usage"].append({
                    "asset_id": asset.asset_id,
                    "asset_name": asset.name,
                    "asset_type": asset.asset_type.value,
                    "license_type": asset.license_type.value,
                    "used_at": usage.used_at.isoformat(),
                    "project_id": usage.project_id,
                    "usage_type": usage.usage_type,
                    "duration": usage.usage_duration
                })
            
            return report
    
    # ========================================================================
    # COPYRIGHT MONITORING
    # ========================================================================
    
    async def scan_for_violations(
        self,
        project_id: int
    ) -> List[Dict[str, Any]]:
        """Scan project for potential copyright violations"""
        
        violations = []
        
        async with AsyncSessionLocal() as db:
            # Get all assets used in project
            result = await db.execute(
                select(AssetUsage)
                .where(AssetUsage.project_id == project_id)
                .options(selectinload(AssetUsage.asset))
            )
            usages = result.scalars().all()
            
            for usage in usages:
                asset = usage.asset
                
                # Check missing attribution
                if asset.attribution_required and not usage.usage_context.get("attribution_included"):
                    violations.append({
                        "type": "missing_attribution",
                        "severity": "high",
                        "asset_id": asset.asset_id,
                        "asset_name": asset.name,
                        "required_attribution": self._generate_attribution(asset),
                        "recommendation": "Add required attribution to video description or credits"
                    })
                
                # Check commercial use restrictions
                if usage.usage_context.get("commercial", False):
                    if not asset.license_details.get("commercial_use", True):
                        violations.append({
                            "type": "commercial_use_violation",
                            "severity": "critical",
                            "asset_id": asset.asset_id,
                            "asset_name": asset.name,
                            "license_type": asset.license_type.value,
                            "recommendation": "Replace with commercial-use allowed asset"
                        })
                
                # Check modification restrictions
                if usage.usage_context.get("modified", False):
                    if not asset.license_details.get("allow_modifications", True):
                        violations.append({
                            "type": "modification_violation",
                            "severity": "high",
                            "asset_id": asset.asset_id,
                            "asset_name": asset.name,
                            "recommendation": "Use original asset without modifications"
                        })
            
            return violations
    
    # ========================================================================
    # COPYRIGHT REPORTS
    # ========================================================================
    
    async def file_copyright_report(
        self,
        asset_id: str,
        reporter_id: int,
        reason: str,
        evidence_url: Optional[str] = None
    ) -> CopyrightReport:
        """File a copyright infringement report"""
        
        async with AsyncSessionLocal() as db:
            # Get asset
            result = await db.execute(
                select(Asset).where(Asset.asset_id == asset_id)
            )
            asset = result.scalar_one_or_none()
            
            if not asset:
                raise ValueError(f"Asset not found: {asset_id}")
            
            # Create report
            report = CopyrightReport(
                asset_id=asset.id,
                reported_by=reporter_id,
                reason=reason,
                evidence_url=evidence_url,
                status="pending"
            )
            
            db.add(report)
            
            # Update asset status if multiple reports
            report_count = await db.scalar(
                select(func.count(CopyrightReport.id))
                .where(
                    CopyrightReport.asset_id == asset.id,
                    CopyrightReport.status == "pending"
                )
            )
            
            if report_count >= 3:
                # Automatically archive asset after 3 reports
                asset.status = AssetStatus.ARCHIVED
                logger.warning(f"Asset {asset_id} archived due to multiple copyright reports")
            
            await db.commit()
            await db.refresh(report)
            
            logger.info(f"Copyright report filed for asset {asset_id}")
            
            return report
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    async def _check_license_restrictions(
        self,
        asset: Asset,
        usage_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check if usage complies with license restrictions"""
        
        restrictions = asset.license_details.get("restrictions", {})
        
        # Check commercial use
        if usage_context.get("commercial", False):
            if not asset.license_details.get("commercial_use", True):
                return {
                    "valid": False,
                    "reason": "Asset does not allow commercial use"
                }
        
        # Check modifications
        if usage_context.get("modified", False):
            if not asset.license_details.get("allow_modifications", True):
                return {
                    "valid": False,
                    "reason": "Asset does not allow modifications"
                }
        
        # Check territory restrictions
        if "territories" in restrictions:
            user_territory = usage_context.get("territory", "US")
            if user_territory not in restrictions["territories"]:
                return {
                    "valid": False,
                    "reason": f"Asset not licensed for territory: {user_territory}"
                }
        
        # Check time restrictions
        if "expiry_date" in asset.license_details:
            expiry = datetime.fromisoformat(asset.license_details["expiry_date"])
            if datetime.utcnow() > expiry:
                return {
                    "valid": False,
                    "reason": "Asset license has expired"
                }
        
        return {"valid": True}
    
    async def _check_usage_limits(
        self,
        asset: Asset,
        usage_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check if usage exceeds license limits"""
        
        limits = asset.license_details.get("usage_limits", {})
        
        if not limits:
            return {"valid": True}
        
        async with AsyncSessionLocal() as db:
            # Check total usage limit
            if "max_uses" in limits:
                usage_count = await db.scalar(
                    select(func.count(AssetUsage.id))
                    .where(AssetUsage.asset_id == asset.id)
                )
                
                if usage_count >= limits["max_uses"]:
                    return {
                        "valid": False,
                        "reason": f"Asset usage limit reached ({limits['max_uses']} uses)"
                    }
            
            # Check per-user limit
            if "max_uses_per_user" in limits:
                user_id = usage_context.get("user_id")
                if user_id:
                    user_usage_count = await db.scalar(
                        select(func.count(AssetUsage.id))
                        .where(
                            AssetUsage.asset_id == asset.id,
                            AssetUsage.user_id == user_id
                        )
                    )
                    
                    if user_usage_count >= limits["max_uses_per_user"]:
                        return {
                            "valid": False,
                            "reason": f"User usage limit reached ({limits['max_uses_per_user']} uses)"
                        }
        
        return {"valid": True}
    
    def _generate_attribution(self, asset: Asset) -> str:
        """Generate proper attribution text"""
        
        if asset.attribution_text:
            return asset.attribution_text
        
        template = self.attribution_templates.get(
            asset.license_type,
            self.attribution_templates[LicenseType.CUSTOM]
        )
        
        attribution_data = {
            "title": asset.name,
            "author": asset.source_attribution or "Unknown",
            "source": asset.source_url or "Unknown",
            "license": asset.license_type.value,
            **asset.license_details.get("attribution_data", {})
        }
        
        try:
            return template.format(**attribution_data)
        except:
            return f"{asset.name} - {asset.license_type.value}"

# Initialize service
copyright_service = CopyrightComplianceService()
