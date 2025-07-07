# test_config.py
"""
Testing configuration for GLB Optimizer
Isolated environment for safe testing without affecting production data
"""
from config import Config

class TestConfig(Config):
    """Test configuration with isolated settings"""
    TESTING = True
    DEBUG = True
    
    # Use in-memory SQLite database for fast, isolated tests
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Use different Redis database for testing
    REDIS_URL = 'redis://localhost:6379/1'
    CELERY_BROKER_URL = 'redis://localhost:6379/1'
    CELERY_RESULT_BACKEND = 'redis://localhost:6379/1'
    
    # Disable security features that interfere with testing
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    
    # Test-specific settings
    SECRET_KEY = 'test_secret_key'
    SESSION_SECRET = 'test_session_secret'
    
    # Faster file operations for testing
    UPLOAD_FOLDER = 'test_uploads'
    OUTPUT_FOLDER = 'test_output'
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB for testing
    
    # Disable cleanup during tests
    CLEANUP_ENABLED = False
    FILE_RETENTION_HOURS = 1
    
    # Test-optimized task settings
    MAX_CONCURRENT_TASKS = 1
    TASK_TIMEOUT_SECONDS = 30
    
    # Logging configuration for tests
    LOG_LEVEL = 'WARNING'  # Reduce noise in test output
    LOG_TO_FILE = False