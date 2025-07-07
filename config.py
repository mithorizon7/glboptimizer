"""
Configuration management for GLB Optimizer
Loads settings from environment variables with sensible defaults
"""

import os
from pathlib import Path

class Config:
    """Base configuration class with environment variable support"""
    
    # Flask Configuration
    SECRET_KEY = os.environ.get('SESSION_SECRET', 'dev_secret_key_change_in_production')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1', 'yes']
    
    # File Upload Configuration
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    OUTPUT_FOLDER = os.environ.get('OUTPUT_FOLDER', 'output')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_FILE_SIZE_MB', '100')) * 1024 * 1024
    ALLOWED_EXTENSIONS = {'glb'}
    
    # Optimization Configuration
    DEFAULT_QUALITY_LEVEL = os.environ.get('DEFAULT_QUALITY_LEVEL', 'high')
    ENABLE_LOD_BY_DEFAULT = os.environ.get('ENABLE_LOD_BY_DEFAULT', 'true').lower() in ['true', '1', 'yes']
    ENABLE_SIMPLIFICATION_BY_DEFAULT = os.environ.get('ENABLE_SIMPLIFICATION_BY_DEFAULT', 'true').lower() in ['true', '1', 'yes']
    
    # Celery/Redis Configuration
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', REDIS_URL)
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', REDIS_URL)
    
    # Task Queue Configuration
    MAX_CONCURRENT_TASKS = int(os.environ.get('MAX_CONCURRENT_TASKS', '1'))
    TASK_TIMEOUT_SECONDS = int(os.environ.get('TASK_TIMEOUT_SECONDS', '600'))  # 10 minutes
    
    # File Cleanup Configuration
    FILE_RETENTION_HOURS = int(os.environ.get('FILE_RETENTION_HOURS', '24'))
    CLEANUP_ENABLED = os.environ.get('CLEANUP_ENABLED', 'true').lower() in ['true', '1', 'yes']
    CLEANUP_SCHEDULE_CRON = os.environ.get('CLEANUP_SCHEDULE_CRON', '0 2 * * *')  # Daily at 2 AM
    
    # External Tool Paths (for custom installations)
    GLTF_TRANSFORM_PATH = os.environ.get('GLTF_TRANSFORM_PATH', 'gltf-transform')
    GLTFPACK_PATH = os.environ.get('GLTFPACK_PATH', 'gltfpack')
    
    # Security Configuration
    SECURE_FILENAME_ENABLED = os.environ.get('SECURE_FILENAME_ENABLED', 'true').lower() in ['true', '1', 'yes']
    CORS_ENABLED = os.environ.get('CORS_ENABLED', 'false').lower() in ['true', '1', 'yes']
    
    # Logging Configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
    LOG_TO_FILE = os.environ.get('LOG_TO_FILE', 'false').lower() in ['true', '1', 'yes']
    LOG_FILE_PATH = os.environ.get('LOG_FILE_PATH', 'glb_optimizer.log')
    
    # Performance Configuration
    COMPRESSION_THREADS = int(os.environ.get('COMPRESSION_THREADS', '0'))  # 0 = auto-detect
    MEMORY_LIMIT_MB = int(os.environ.get('MEMORY_LIMIT_MB', '2048'))
    
    @classmethod
    def ensure_directories(cls):
        """Create necessary directories if they don't exist"""
        for directory in [cls.UPLOAD_FOLDER, cls.OUTPUT_FOLDER]:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def validate_config(cls):
        """Validate configuration and return any issues"""
        issues = []
        
        # Check required directories
        for name, path in [('UPLOAD_FOLDER', cls.UPLOAD_FOLDER), ('OUTPUT_FOLDER', cls.OUTPUT_FOLDER)]:
            if not os.path.exists(path):
                try:
                    Path(path).mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    issues.append(f"Cannot create {name} directory '{path}': {e}")
        
        # Check file size limits
        if cls.MAX_CONTENT_LENGTH <= 0:
            issues.append("MAX_CONTENT_LENGTH must be positive")
        
        # Check retention settings
        if cls.FILE_RETENTION_HOURS <= 0:
            issues.append("FILE_RETENTION_HOURS must be positive")
        
        # Check task timeout
        if cls.TASK_TIMEOUT_SECONDS <= 0:
            issues.append("TASK_TIMEOUT_SECONDS must be positive")
        
        return issues
    
    @classmethod
    def get_config_summary(cls):
        """Get a summary of current configuration (safe for logging)"""
        return {
            'upload_folder': cls.UPLOAD_FOLDER,
            'output_folder': cls.OUTPUT_FOLDER,
            'max_file_size_mb': cls.MAX_CONTENT_LENGTH // (1024 * 1024),
            'file_retention_hours': cls.FILE_RETENTION_HOURS,
            'cleanup_enabled': cls.CLEANUP_ENABLED,
            'max_concurrent_tasks': cls.MAX_CONCURRENT_TASKS,
            'task_timeout_seconds': cls.TASK_TIMEOUT_SECONDS,
            'default_quality': cls.DEFAULT_QUALITY_LEVEL,
            'debug_mode': cls.DEBUG,
            'log_level': cls.LOG_LEVEL
        }

class DevelopmentConfig(Config):
    """Development-specific configuration"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'
    FILE_RETENTION_HOURS = 1  # Shorter retention for development
    CLEANUP_ENABLED = False  # Disable automatic cleanup in development
    LOG_TO_FILE = False  # Disable file logging in development to avoid path issues

class ProductionConfig(Config):
    """Production-specific configuration with enhanced security"""
    DEBUG = False
    LOG_LEVEL = 'INFO'
    LOG_TO_FILE = True
    CLEANUP_ENABLED = True
    SECURE_FILENAME_ENABLED = True
    
    @classmethod
    def validate_config(cls):
        """Enhanced validation for production security requirements"""
        issues = super().validate_config()
        
        # Critical security validations for production
        if cls.SECRET_KEY == 'dev_secret_key_change_in_production':
            issues.append("CRITICAL: SESSION_SECRET must be set to a strong random value in production")
        
        if len(cls.SECRET_KEY) < 32:
            issues.append("CRITICAL: SESSION_SECRET must be at least 32 characters long")
        
        if cls.DEBUG:
            issues.append("CRITICAL: DEBUG mode must be disabled in production (set FLASK_DEBUG=false)")
        
        # Check for HTTPS configuration hints
        if not os.environ.get('HTTPS_ENABLED'):
            issues.append("WARNING: Consider enabling HTTPS in production (set HTTPS_ENABLED=true)")
        
        # Check for security headers configuration
        if not os.environ.get('SECURITY_HEADERS_ENABLED'):
            issues.append("INFO: Consider enabling security headers (set SECURITY_HEADERS_ENABLED=true)")
        
        return issues

class TestingConfig(Config):
    """Testing-specific configuration"""
    DEBUG = True
    UPLOAD_FOLDER = 'test_uploads'
    OUTPUT_FOLDER = 'test_output'
    FILE_RETENTION_HOURS = 1
    CLEANUP_ENABLED = False

# Configuration mapping
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': Config
}

def get_config(config_name=None):
    """Get configuration class based on environment"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    return config_map.get(config_name, Config)