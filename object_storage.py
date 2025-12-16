"""
Object Storage Integration for GLB Optimizer
Provides unified interface for cloud storage providers with local fallback
"""

import os
import logging
import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any, Union
from datetime import datetime, timezone, timedelta
from abc import ABC, abstractmethod
from urllib.parse import urlparse
import hashlib
import json
from config import Config

logger = logging.getLogger(__name__)

class StorageProvider(ABC):
    """Abstract base class for storage providers"""
    
    @abstractmethod
    def upload(self, local_path: str, remote_key: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Upload file to storage and return public URL"""
        pass
    
    @abstractmethod
    def download(self, remote_key: str, local_path: str) -> bool:
        """Download file from storage to local path"""
        pass
    
    @abstractmethod
    def delete(self, remote_key: str) -> bool:
        """Delete file from storage"""
        pass
    
    @abstractmethod
    def exists(self, remote_key: str) -> bool:
        """Check if file exists in storage"""
        pass
    
    @abstractmethod
    def get_url(self, remote_key: str, expires_in: int = 3600) -> str:
        """Get signed/public URL for file"""
        pass
    
    @abstractmethod
    def list_files(self, prefix: str = "") -> list:
        """List files with optional prefix"""
        pass
    
    @abstractmethod
    def cleanup_old_files(self, days: int = 7) -> int:
        """Clean up files older than specified days"""
        pass

class LocalFileStorage(StorageProvider):
    """Local filesystem storage provider"""
    
    def __init__(self, base_path: str = "storage"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
    def _get_file_path(self, remote_key: str) -> Path:
        """Get local file path for remote key"""
        return self.base_path / remote_key
    
    def upload(self, local_path: str, remote_key: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Upload file to local storage"""
        try:
            source_path = Path(local_path)
            if not source_path.exists():
                raise FileNotFoundError(f"Source file not found: {local_path}")
            
            dest_path = self._get_file_path(remote_key)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            dest_path.write_bytes(source_path.read_bytes())
            
            # Store metadata if provided
            if metadata:
                metadata_path = dest_path.with_suffix('.metadata.json')
                metadata_path.write_text(json.dumps(metadata, indent=2))
            
            logger.info(f"Uploaded file to local storage: {remote_key}")
            return f"/storage/{remote_key}"
            
        except Exception as e:
            logger.error(f"Failed to upload {local_path} to {remote_key}: {e}")
            raise
    
    def download(self, remote_key: str, local_path: str) -> bool:
        """Download file from local storage"""
        try:
            source_path = self._get_file_path(remote_key)
            if not source_path.exists():
                return False
            
            dest_path = Path(local_path)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(source_path.read_bytes())
            
            logger.info(f"Downloaded file from local storage: {remote_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download {remote_key} to {local_path}: {e}")
            return False
    
    def delete(self, remote_key: str) -> bool:
        """Delete file from local storage"""
        try:
            file_path = self._get_file_path(remote_key)
            if file_path.exists():
                file_path.unlink()
                
                # Also delete metadata if it exists
                metadata_path = file_path.with_suffix('.metadata.json')
                if metadata_path.exists():
                    metadata_path.unlink()
                
                logger.info(f"Deleted file from local storage: {remote_key}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete {remote_key}: {e}")
            return False
    
    def exists(self, remote_key: str) -> bool:
        """Check if file exists in local storage"""
        return self._get_file_path(remote_key).exists()
    
    def get_url(self, remote_key: str, expires_in: int = 3600) -> str:
        """Get URL for local file"""
        return f"/storage/{remote_key}"
    
    def list_files(self, prefix: str = "") -> list:
        """List files in local storage"""
        try:
            prefix_path = self.base_path / prefix if prefix else self.base_path
            files = []
            
            for file_path in prefix_path.rglob("*"):
                if file_path.is_file() and not file_path.name.endswith('.metadata.json'):
                    relative_path = file_path.relative_to(self.base_path)
                    files.append(str(relative_path))
            
            return files
            
        except Exception as e:
            logger.error(f"Failed to list files with prefix {prefix}: {e}")
            return []
    
    def cleanup_old_files(self, days: int = 7) -> int:
        """Clean up local files older than specified days"""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
            deleted_count = 0
            
            for file_path in self.base_path.rglob("*"):
                if file_path.is_file():
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
                    if file_mtime < cutoff_time:
                        file_path.unlink()
                        deleted_count += 1
                        
                        # Also delete metadata if it exists
                        metadata_path = file_path.with_suffix('.metadata.json')
                        if metadata_path.exists():
                            metadata_path.unlink()
            
            logger.info(f"Cleaned up {deleted_count} old files from local storage")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old files: {e}")
            return 0

class S3Storage(StorageProvider):
    """AWS S3 storage provider"""
    
    def __init__(self, bucket_name: str, aws_access_key_id: str, aws_secret_access_key: str, region: str = "us-east-1"):
        self.bucket_name = bucket_name
        self.region = region
        
        try:
            import boto3
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=region
            )
            
            # Test connection
            self.s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"Successfully connected to S3 bucket: {bucket_name}")
            
        except ImportError:
            raise ImportError("boto3 is required for S3 storage. Install with: pip install boto3")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to S3: {e}")
    
    def upload(self, local_path: str, remote_key: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Upload file to S3"""
        try:
            extra_args = {}
            
            # Set content type
            content_type = mimetypes.guess_type(local_path)[0] or 'application/octet-stream'
            extra_args['ContentType'] = content_type
            
            # Add metadata
            if metadata:
                extra_args['Metadata'] = {k: str(v) for k, v in metadata.items()}
            
            # Upload file
            self.s3_client.upload_file(local_path, self.bucket_name, remote_key, ExtraArgs=extra_args)
            
            url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{remote_key}"
            logger.info(f"Uploaded file to S3: {remote_key}")
            return url
            
        except Exception as e:
            logger.error(f"Failed to upload {local_path} to S3: {e}")
            raise
    
    def download(self, remote_key: str, local_path: str) -> bool:
        """Download file from S3"""
        try:
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            self.s3_client.download_file(self.bucket_name, remote_key, local_path)
            
            logger.info(f"Downloaded file from S3: {remote_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download {remote_key} from S3: {e}")
            return False
    
    def delete(self, remote_key: str) -> bool:
        """Delete file from S3"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=remote_key)
            logger.info(f"Deleted file from S3: {remote_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete {remote_key} from S3: {e}")
            return False
    
    def exists(self, remote_key: str) -> bool:
        """Check if file exists in S3"""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=remote_key)
            return True
        except:
            return False
    
    def get_url(self, remote_key: str, expires_in: int = 3600) -> str:
        """Get signed URL for S3 file"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': remote_key},
                ExpiresIn=expires_in
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate signed URL for {remote_key}: {e}")
            # Return public URL as fallback
            return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{remote_key}"
    
    def list_files(self, prefix: str = "") -> list:
        """List files in S3"""
        try:
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            files = []
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    files.append(obj['Key'])
            
            return files
            
        except Exception as e:
            logger.error(f"Failed to list S3 files with prefix {prefix}: {e}")
            return []
    
    def cleanup_old_files(self, days: int = 7) -> int:
        """Clean up S3 files older than specified days"""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
            deleted_count = 0
            
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name)
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    if obj['LastModified'] < cutoff_time:
                        self.s3_client.delete_object(Bucket=self.bucket_name, Key=obj['Key'])
                        deleted_count += 1
            
            logger.info(f"Cleaned up {deleted_count} old files from S3")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old S3 files: {e}")
            return 0

class ObjectStorageManager:
    """Unified object storage manager with multiple provider support"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.provider = self._initialize_provider()
        
    def _initialize_provider(self) -> StorageProvider:
        """Initialize storage provider based on configuration"""
        storage_type = self.config.STORAGE_TYPE.lower()
        
        if storage_type == 's3':
            return self._initialize_s3()
        elif storage_type == 'gcs':
            return self._initialize_gcs()
        elif storage_type == 'azure':
            return self._initialize_azure()
        else:
            return self._initialize_local()
    
    def _initialize_s3(self) -> StorageProvider:
        """Initialize S3 storage provider"""
        try:
            bucket_name = os.environ.get('S3_BUCKET_NAME')
            aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
            aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
            region = self.config.AWS_REGION
            
            if not all([bucket_name, aws_access_key_id, aws_secret_access_key]):
                logger.warning("S3 credentials not found, falling back to local storage")
                return self._initialize_local()
            
            return S3Storage(bucket_name, aws_access_key_id, aws_secret_access_key, region)
            
        except Exception as e:
            logger.error(f"Failed to initialize S3 storage: {e}")
            logger.info("Falling back to local storage")
            return self._initialize_local()
    
    def _initialize_gcs(self) -> StorageProvider:
        """Initialize Google Cloud Storage provider"""
        # TODO: Implement GCS provider
        logger.warning("Google Cloud Storage not implemented yet, falling back to local storage")
        return self._initialize_local()
    
    def _initialize_azure(self) -> StorageProvider:
        """Initialize Azure Blob Storage provider"""
        # TODO: Implement Azure provider
        logger.warning("Azure Blob Storage not implemented yet, falling back to local storage")
        return self._initialize_local()
    
    def _initialize_local(self) -> StorageProvider:
        """Initialize local filesystem storage provider"""
        storage_path = self.config.STORAGE_PATH
        return LocalFileStorage(storage_path)
    
    def generate_storage_key(self, task_id: str, file_type: str, original_filename: str = None) -> str:
        """Generate storage key for file"""
        timestamp = datetime.now(timezone.utc).strftime('%Y/%m/%d')
        
        if file_type == 'original':
            extension = Path(original_filename).suffix if original_filename else '.glb'
            return f"uploads/{timestamp}/{task_id}{extension}"
        elif file_type == 'optimized':
            return f"outputs/{timestamp}/{task_id}_optimized.glb"
        elif file_type == 'logs':
            return f"logs/{timestamp}/{task_id}.log"
        else:
            return f"misc/{timestamp}/{task_id}_{file_type}"
    
    def upload_file(self, local_path: str, task_id: str, file_type: str, 
                   original_filename: str = None, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Upload file to storage"""
        try:
            storage_key = self.generate_storage_key(task_id, file_type, original_filename)
            
            # Add default metadata
            file_metadata = {
                'task_id': task_id,
                'file_type': file_type,
                'upload_time': datetime.now(timezone.utc).isoformat(),
                'original_filename': original_filename or Path(local_path).name,
                'file_size': Path(local_path).stat().st_size
            }
            
            if metadata:
                file_metadata.update(metadata)
            
            url = self.provider.upload(local_path, storage_key, file_metadata)
            
            logger.info(f"Uploaded {file_type} file for task {task_id}: {storage_key}")
            return url
            
        except Exception as e:
            logger.error(f"Failed to upload {file_type} file for task {task_id}: {e}")
            raise
    
    def download_file(self, task_id: str, file_type: str, local_path: str, 
                     original_filename: str = None) -> bool:
        """Download file from storage"""
        try:
            storage_key = self.generate_storage_key(task_id, file_type, original_filename)
            success = self.provider.download(storage_key, local_path)
            
            if success:
                logger.info(f"Downloaded {file_type} file for task {task_id}: {storage_key}")
            else:
                logger.warning(f"Failed to download {file_type} file for task {task_id}: {storage_key}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to download {file_type} file for task {task_id}: {e}")
            return False
    
    def delete_file(self, task_id: str, file_type: str, original_filename: str = None) -> bool:
        """Delete file from storage"""
        try:
            storage_key = self.generate_storage_key(task_id, file_type, original_filename)
            success = self.provider.delete(storage_key)
            
            if success:
                logger.info(f"Deleted {file_type} file for task {task_id}: {storage_key}")
            else:
                logger.warning(f"Failed to delete {file_type} file for task {task_id}: {storage_key}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete {file_type} file for task {task_id}: {e}")
            return False
    
    def file_exists(self, task_id: str, file_type: str, original_filename: str = None) -> bool:
        """Check if file exists in storage"""
        try:
            storage_key = self.generate_storage_key(task_id, file_type, original_filename)
            return self.provider.exists(storage_key)
            
        except Exception as e:
            logger.error(f"Failed to check existence of {file_type} file for task {task_id}: {e}")
            return False
    
    def get_file_url(self, task_id: str, file_type: str, original_filename: str = None, 
                    expires_in: int = 3600) -> str:
        """Get URL for file"""
        try:
            storage_key = self.generate_storage_key(task_id, file_type, original_filename)
            return self.provider.get_url(storage_key, expires_in)
            
        except Exception as e:
            logger.error(f"Failed to get URL for {file_type} file for task {task_id}: {e}")
            return None
    
    def cleanup_old_files(self, days: int = 7) -> int:
        """Clean up old files from storage"""
        try:
            return self.provider.cleanup_old_files(days)
            
        except Exception as e:
            logger.error(f"Failed to cleanup old files: {e}")
            return 0
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        try:
            files = self.provider.list_files()
            
            stats = {
                'total_files': len(files),
                'storage_type': type(self.provider).__name__,
                'files_by_type': {
                    'uploads': len([f for f in files if f.startswith('uploads/')]),
                    'outputs': len([f for f in files if f.startswith('outputs/')]),
                    'logs': len([f for f in files if f.startswith('logs/')]),
                    'misc': len([f for f in files if f.startswith('misc/')])
                }
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {'error': str(e)}

# Global storage manager instance
storage_manager = None

def get_storage_manager() -> ObjectStorageManager:
    """Get global storage manager instance"""
    global storage_manager
    if storage_manager is None:
        storage_manager = ObjectStorageManager()
    return storage_manager

def init_storage():
    """Initialize storage manager"""
    global storage_manager
    storage_manager = ObjectStorageManager()
    logger.info(f"Storage manager initialized with {type(storage_manager.provider).__name__}")
    return storage_manager