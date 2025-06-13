# backend/app/services/file_storage.py
"""
📦 REELS GENERATOR - File Storage Service
AWS S3 integration for media file storage and CDN delivery
"""

import boto3
from botocore.exceptions import ClientError
import io
from typing import BinaryIO, Optional, Dict, Any
import mimetypes
import uuid
from datetime import datetime, timedelta
import logging

from ..config import settings

logger = logging.getLogger(__name__)

class FileStorageService:
    """Service for managing file storage in AWS S3"""
    
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.bucket_name = settings.S3_BUCKET_NAME
        self.cdn_url = f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com"
        
        # Ensure bucket exists
        self._ensure_bucket_exists()
    
    # ========================================================================
    # AUDIO STORAGE
    # ========================================================================
    
    async def upload_audio(
        self,
        audio_data: bytes,
        key: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """Upload audio file to S3"""
        
        try:
            # Set metadata
            if metadata is None:
                metadata = {}
            
            metadata.update({
                'Content-Type': 'audio/mpeg',
                'uploaded-at': datetime.utcnow().isoformat(),
                'service': 'reels-generator'
            })
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=audio_data,
                ContentType='audio/mpeg',
                Metadata=metadata,
                CacheControl='max-age=31536000'  # Cache for 1 year
            )
            
            # Return CDN URL
            return f"{self.cdn_url}/{key}"
            
        except ClientError as e:
            logger.error(f"💥 S3 upload failed: {e}")
            raise
    
    # ========================================================================
    # VIDEO STORAGE
    # ========================================================================
    
    async def upload_video(
        self,
        video_data: BinaryIO,
        key: str,
        content_type: str = 'video/mp4'
    ) -> str:
        """Upload video file to S3"""
        
        try:
            self.s3_client.upload_fileobj(
                video_data,
                self.bucket_name,
                key,
                ExtraArgs={
                    'ContentType': content_type,
                    'CacheControl': 'max-age=31536000'
                }
            )
            
            return f"{self.cdn_url}/{key}"
            
        except ClientError as e:
            logger.error(f"💥 Video upload failed: {e}")
            raise
    
    # ========================================================================
    # PRESIGNED URLS
    # ========================================================================
    
    def generate_presigned_url(
        self,
        key: str,
        expiration: int = 3600,
        http_method: str = 'GET'
    ) -> str:
        """Generate presigned URL for direct S3 access"""
        
        try:
            url = self.s3_client.generate_presigned_url(
                ClientMethod='get_object' if http_method == 'GET' else 'put_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': key
                },
                ExpiresIn=expiration
            )
            return url
            
        except ClientError as e:
            logger.error(f"💥 Presigned URL generation failed: {e}")
            raise
    
    # ========================================================================
    # FILE MANAGEMENT
    # ========================================================================
    
    async def delete_file(self, key: str) -> bool:
        """Delete file from S3"""
        
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return True
            
        except ClientError as e:
            logger.error(f"💥 File deletion failed: {e}")
            return False
    
    async def file_exists(self, key: str) -> bool:
        """Check if file exists in S3"""
        
        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return True
            
        except ClientError:
            return False
    
    async def get_file_metadata(self, key: str) -> Dict[str, Any]:
        """Get file metadata from S3"""
        
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )
            
            return {
                'size': response['ContentLength'],
                'content_type': response['ContentType'],
                'last_modified': response['LastModified'],
                'metadata': response.get('Metadata', {})
            }
            
        except ClientError as e:
            logger.error(f"💥 Metadata retrieval failed: {e}")
            raise
    
    # ========================================================================
    # BUCKET MANAGEMENT
    # ========================================================================
    
    def _ensure_bucket_exists(self):
        """Ensure S3 bucket exists and is configured correctly"""
        
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"✅ S3 bucket '{self.bucket_name}' exists")
            
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                # Create bucket
                logger.info(f"Creating S3 bucket '{self.bucket_name}'...")
                
                if settings.AWS_REGION == 'us-east-1':
                    self.s3_client.create_bucket(Bucket=self.bucket_name)
                else:
                    self.s3_client.create_bucket(
                        Bucket=self.bucket_name,
                        CreateBucketConfiguration={
                            'LocationConstraint': settings.AWS_REGION
                        }
                    )
                
                # Set bucket CORS
                self._configure_bucket_cors()
                
                logger.info(f"✅ S3 bucket created successfully")
            else:
                logger.error(f"💥 Bucket check failed: {e}")
                raise
    
    def _configure_bucket_cors(self):
        """Configure CORS for the S3 bucket"""
        
        cors_configuration = {
            'CORSRules': [{
                'AllowedHeaders': ['*'],
                'AllowedMethods': ['GET', 'PUT', 'POST', 'DELETE', 'HEAD'],
                'AllowedOrigins': settings.ALLOWED_ORIGINS,
                'ExposeHeaders': ['ETag'],
                'MaxAgeSeconds': 3000
            }]
        }
        
        self.s3_client.put_bucket_cors(
            Bucket=self.bucket_name,
            CORSConfiguration=cors_configuration
        )

# Initialize service
storage_service = FileStorageService()
