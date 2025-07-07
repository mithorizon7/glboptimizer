# conftest.py
"""
Pytest configuration and shared fixtures for GLB Optimizer tests
"""
import pytest
import os
import tempfile
import shutil
from unittest.mock import patch

# Set test environment before any imports
os.environ['FLASK_ENV'] = 'testing'
os.environ['REDIS_URL'] = 'redis://localhost:6379/1'
os.environ['CELERY_BROKER_URL'] = 'redis://localhost:6379/1'
os.environ['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/1'

from app import app as flask_app
from database import SessionLocal, init_database
from models import OptimizationTask, PerformanceMetric, UserSession
from test_config import TestConfig

@pytest.fixture(scope='session')
def app():
    """Create application for testing"""
    flask_app.config.from_object(TestConfig)
    
    with flask_app.app_context():
        # Initialize test database
        init_database()
        yield flask_app

@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()

@pytest.fixture
def db_session(app):
    """Create database session for tests"""
    with app.app_context():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

@pytest.fixture
def test_dirs():
    """Create temporary directories for test files"""
    test_upload_dir = tempfile.mkdtemp(prefix='test_uploads_')
    test_output_dir = tempfile.mkdtemp(prefix='test_output_')
    
    # Patch the config to use test directories
    with patch('config.Config.UPLOAD_FOLDER', test_upload_dir), \
         patch('config.Config.OUTPUT_FOLDER', test_output_dir):
        yield {
            'upload_dir': test_upload_dir,
            'output_dir': test_output_dir
        }
    
    # Cleanup
    shutil.rmtree(test_upload_dir, ignore_errors=True)
    shutil.rmtree(test_output_dir, ignore_errors=True)

@pytest.fixture
def sample_glb_file(test_dirs):
    """Create a sample GLB file for testing"""
    upload_dir = test_dirs['upload_dir']
    glb_file = os.path.join(upload_dir, 'test_model.glb')
    
    # Create minimal valid GLB file
    with open(glb_file, 'wb') as f:
        # GLB header: magic, version, length
        f.write(b'glTF')  # Magic
        f.write((2).to_bytes(4, 'little'))  # Version
        f.write((200).to_bytes(4, 'little'))  # Total length
        
        # JSON chunk
        json_data = b'{"scene":0,"scenes":[{"nodes":[0]}],"nodes":[{"mesh":0}]}'
        json_chunk_len = len(json_data)
        f.write(json_chunk_len.to_bytes(4, 'little'))
        f.write(b'JSON')
        f.write(json_data)
        
        # Pad to reach declared length
        current_size = 4 + 4 + 4 + 4 + 4 + len(json_data)
        padding_needed = 200 - current_size
        f.write(b'\x00' * padding_needed)
    
    return glb_file

@pytest.fixture
def sample_optimization_task(db_session):
    """Create sample optimization task for testing"""
    task = OptimizationTask(
        id='test_task_123',
        original_filename='test_model.glb',
        secure_filename='test_model_secure.glb',
        original_size=1000000,
        compressed_size=500000,
        compression_ratio=0.5,
        quality_level='high',
        status='completed',
        progress=100,
        processing_time=45.2
    )
    db_session.add(task)
    db_session.commit()
    return task

@pytest.fixture
def sample_user_session(db_session):
    """Create sample user session for testing"""
    user_session = UserSession(
        session_id='test_session_456',
        total_uploads=5,
        total_optimizations=4,
        total_downloads=3,
        total_original_size=5000000,
        total_compressed_size=2000000,
        total_savings=3000000
    )
    db_session.add(user_session)
    db_session.commit()
    return user_session

@pytest.fixture
def mock_celery_task():
    """Mock Celery task for testing"""
    with patch('tasks.optimize_glb_file.delay') as mock_task:
        mock_task.return_value.id = 'mock_task_789'
        mock_task.return_value.state = 'PENDING'
        yield mock_task

@pytest.fixture
def mock_optimizer():
    """Mock GLB optimizer for testing"""
    with patch('optimizer.GLBOptimizer') as mock_opt:
        # Configure mock to return success by default
        mock_instance = mock_opt.return_value
        mock_instance.optimize.return_value = {
            'success': True,
            'original_size': 1000000,
            'optimized_size': 400000,
            'compression_ratio': 0.6,
            'processing_time': 30.5,
            'performance_metrics': {
                'gpu_memory_savings': 0.7,
                'load_time_improvement': 0.6
            }
        }
        yield mock_instance