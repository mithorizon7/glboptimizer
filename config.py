"""
Configuration management for GLB Optimizer
Loads settings from environment variables with sensible defaults
"""

import os
import json
from typing import Dict, Any
from pathlib import Path

# GLB File Format Constants
class GLBConstants:
    """GLB file format specification constants"""
    
    # GLB Header Structure (12 bytes total)
    HEADER_LENGTH = 12                    # Total GLB header size
    MAGIC_NUMBER = b'glTF'               # GLB magic number (4 bytes)
    VERSION_OFFSET = 4                   # Version field offset (4 bytes)
    LENGTH_OFFSET = 8                    # File length offset (4 bytes)
    SUPPORTED_VERSION = 2                # GLB version 2.0
    
    # GLB Chunk Structure  
    CHUNK_HEADER_LENGTH = 8              # Chunk header size (length + type)
    CHUNK_LENGTH_OFFSET = 0              # Chunk length field offset
    CHUNK_TYPE_OFFSET = 4                # Chunk type field offset
    JSON_CHUNK_TYPE = b'JSON'            # First chunk must be JSON
    BINARY_CHUNK_TYPE = b'BIN\x00'       # Binary chunk type
    
    # Validation Constants
    MIN_FILE_WITH_CHUNK = HEADER_LENGTH + CHUNK_HEADER_LENGTH  # 20 bytes minimum
    MIN_VALID_GLB_SIZE = 12              # Minimum for valid GLB header

# Optimization Thresholds and Ratios
class OptimizationThresholds:
    """Centralized optimization thresholds and magic numbers"""
    
    # Compression Method Selection Thresholds
    HIGH_VERTEX_COUNT_THRESHOLD = 50_000     # Threshold for Draco compression consideration
    VERY_HIGH_VERTEX_COUNT = 100_000         # Threshold for hybrid compression
    LARGE_FILE_SIZE_THRESHOLD = 5_000_000    # 5MB threshold for advanced compression
    
    # Geometry Simplification Ratios
    SIMPLIFY_RATIOS = {
        'high': 0.8,                # 80% triangle count (preserve quality)
        'balanced': 0.6,            # 60% triangle count (balance quality/size)
        'maximum_compression': 0.4   # 40% triangle count (maximum compression)
    }
    
    # Error Thresholds
    SIMPLIFY_ERROR_THRESHOLD = 0.01     # Low error threshold for quality preservation
    
    # Texture Compression Thresholds
    WEBP_SIZE_ADVANTAGE_THRESHOLD = 0.8  # WebP must be 20% smaller than KTX2 to be selected
    
    # Performance Estimation Constants
    LOAD_TIME_COMPRESSION_FACTOR = 0.8   # Load time improvement factor
    MAX_LOAD_TIME_IMPROVEMENT = 85       # Maximum load time improvement percentage
    
    # Memory Estimation Constants
    TEXTURE_MEMORY_MULTIPLIER = 4        # Uncompressed texture memory multiplier
    KTX2_MEMORY_REDUCTION = 0.75         # 75% memory reduction with KTX2
    
    # File Size Categories (bytes)
    SMALL_MODEL_THRESHOLD = 1_000_000    # 1MB
    MEDIUM_MODEL_THRESHOLD = 10_000_000  # 10MB
    LARGE_MODEL_THRESHOLD = 50_000_000   # 50MB

class OptimizationConfig:
    """Centralized optimization configuration with environment variable support"""
    
    def __init__(self):
        """Initialize configuration with environment variable support"""
        # File limits
        self.MAX_FILE_SIZE = int(os.environ.get('GLB_MAX_FILE_SIZE', str(500 * 1024 * 1024)))  # 500MB default
        self.MIN_FILE_SIZE = int(os.environ.get('GLB_MIN_FILE_SIZE', '1024'))  # 1KB minimum for valid GLB
        self.SUBPROCESS_TIMEOUT = int(os.environ.get('GLB_SUBPROCESS_TIMEOUT', '300'))  # 5 minutes
        self.PARALLEL_TIMEOUT = int(os.environ.get('GLB_PARALLEL_TIMEOUT', '120'))  # 2 minutes
    
        # Quality presets with comprehensive settings
        self.QUALITY_PRESETS = {
            'high': {
            'description': 'Prioritizes visual quality with good compression',
            'simplify_ratio': 0.8,
            'texture_quality': 95,
            'compression_level': 7,
            'ktx2_quality': '255',
            'ktx2_rdo_lambda': '1.0',
            'ktx2_rdo_threshold': '1.0',
            'webp_quality': '95',
            'webp_lossless': False,
            'uastc_mode': True,         # UASTC for high quality
            'channel_packing': True,    # Channel packing optimization
            'draco_compression_level': '7',
            'draco_quantization_bits': {
                'position': 12,
                'normal': 8,
                'color': 8,
                'tex_coord': 10
            },
            'gltfpack_level': 'medium',
            'enable_ktx2': True,
            'enable_draco': True,
            'enable_meshopt': True
            },
            'balanced': {
            'description': 'Good balance between quality and file size',
            'simplify_ratio': 0.6,
            'texture_quality': 85,
            'compression_level': 8,
            'ktx2_quality': '128',
            'ktx2_rdo_lambda': '2.0',
            'ktx2_rdo_threshold': '1.25',
            'webp_quality': '85',
            'webp_lossless': False,
            'uastc_mode': False,        # ETC1S for balanced
            'channel_packing': True,    # Channel packing optimization
            'draco_compression_level': '8',
            'draco_quantization_bits': {
                'position': 10,
                'normal': 6,
                'color': 6,
                'tex_coord': 8
            },
            'gltfpack_level': 'medium',
            'enable_ktx2': True,  # FIXED: Enable KTX2 for balanced quality
            'enable_draco': True,
            'enable_meshopt': True
            },
            'maximum_compression': {
            'description': 'Maximum compression with acceptable quality loss',
            'simplify_ratio': 0.4,
            'texture_quality': 75,
            'compression_level': 10,
            'ktx2_quality': '64',
            'ktx2_rdo_lambda': '4.0',
            'ktx2_rdo_threshold': '2.0',
            'webp_quality': '75',
            'webp_lossless': False,
            'uastc_mode': False,        # ETC1S for compression
            'channel_packing': True,    # Channel packing optimization
            'draco_compression_level': '10',
            'draco_quantization_bits': {
                'position': 8,
                'normal': 4,
                'color': 4,
                'tex_coord': 6
            },
            'gltfpack_level': 'aggressive',
            'enable_ktx2': True,  # FIXED: Enable KTX2 for maximum compression
            'enable_draco': True,
            'enable_meshopt': True
            }
        }
        
        # Note: Texture compression settings are now centralized in QUALITY_PRESETS above
        # to eliminate configuration duplication and maintain single source of truth
    
    @classmethod
    def from_env(cls) -> 'OptimizationConfig':
        """Load configuration from environment variables and optional config file"""
        config = cls()
        
        # Check for JSON config file override
        config_file = os.environ.get('GLB_CONFIG_FILE')
        if config_file and Path(config_file).exists():
            try:
                with open(config_file, 'r') as f:
                    overrides = json.load(f)
                    
                # Override quality presets if provided
                if 'quality_presets' in overrides:
                    config.QUALITY_PRESETS.update(overrides['quality_presets'])
                
                # Override other settings
                for key, value in overrides.items():
                    if key != 'quality_presets' and hasattr(config, key.upper()):
                        setattr(config, key.upper(), value)
                        
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Warning: Could not load config file {config_file}: {e}")
        
        return config
    
    @classmethod
    def get_quality_settings(cls, quality_level: str) -> Dict[str, Any]:
        """Get comprehensive settings for specified quality level"""
        config = cls()
        if quality_level not in config.QUALITY_PRESETS:
            print(f"Warning: Unknown quality level '{quality_level}', using 'balanced'")
            quality_level = 'balanced'
        
        return config.QUALITY_PRESETS[quality_level].copy()
    
    @classmethod
    def get_available_quality_levels(cls) -> Dict[str, str]:
        """Get available quality levels with descriptions"""
        config = cls()
        return {
            level: settings['description'] 
            for level, settings in config.QUALITY_PRESETS.items()
        }
    
    @classmethod
    def validate_settings(cls) -> Dict[str, Any]:
        """Validate configuration settings and return any issues"""
        # Create a temporary instance to get current values
        config = cls() if not hasattr(cls, '_temp_instance') else cls._temp_instance
        issues = []
        
        # Validate file size limits
        if config.MAX_FILE_SIZE <= config.MIN_FILE_SIZE:
            issues.append("MAX_FILE_SIZE must be greater than MIN_FILE_SIZE")
        
        if config.MIN_FILE_SIZE < 12:  # GLB header minimum
            issues.append("MIN_FILE_SIZE should be at least 12 bytes for valid GLB")
        
        # Validate timeouts
        if config.SUBPROCESS_TIMEOUT <= 0:
            issues.append("SUBPROCESS_TIMEOUT must be positive")
        
        if config.PARALLEL_TIMEOUT <= 0:
            issues.append("PARALLEL_TIMEOUT must be positive")
        
        # Validate quality presets
        required_keys = ['simplify_ratio', 'texture_quality', 'compression_level']
        for level, settings in config.QUALITY_PRESETS.items():
            for key in required_keys:
                if key not in settings:
                    issues.append(f"Quality level '{level}' missing required key '{key}'")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'summary': f"Configuration validation: {len(issues)} issues found"
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Export configuration for logging (safe for logs)"""
        return {
            'max_file_size_mb': self.MAX_FILE_SIZE // (1024 * 1024),
            'min_file_size_bytes': self.MIN_FILE_SIZE,
            'subprocess_timeout': self.SUBPROCESS_TIMEOUT,
            'parallel_timeout': self.PARALLEL_TIMEOUT,
            'quality_levels': list(self.QUALITY_PRESETS.keys()),
            'quality_descriptions': self.get_available_quality_levels()
        }

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
    
    # File size validation configuration
    MAX_FILE_SIZE = int(os.environ.get('GLB_MAX_FILE_SIZE', str(100 * 1024 * 1024)))  # 100MB default
    MIN_FILE_SIZE = int(os.environ.get('GLB_MIN_FILE_SIZE', '12'))  # 12 bytes minimum (GLB header)
    EMPTY_FILE_THRESHOLD = int(os.environ.get('GLB_EMPTY_FILE_THRESHOLD', '100'))  # 100 bytes
    
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
    
    # Parallel processing configuration
    MAX_PARALLEL_WORKERS = int(os.environ.get('MAX_PARALLEL_WORKERS', '3'))  # Cap to avoid overload
    PARALLEL_TIMEOUT = int(os.environ.get('PARALLEL_TIMEOUT', '120'))  # 2 minutes per parallel task
    
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
            if not Path(path).exists():
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