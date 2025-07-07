"""
Proper Celery configuration with Redis following Replit best practices
Based on the comprehensive guide for using Celery in Replit
"""

import os
import subprocess
import logging
from celery import Celery
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

def check_redis_availability():
    """Check if Redis server is available"""
    try:
        result = subprocess.run(['redis-cli', 'ping'], 
                              capture_output=True, text=True, timeout=3)
        return result.returncode == 0 and 'PONG' in result.stdout
    except Exception:
        return False

def create_celery_with_redis():
    """Create Celery instance with Redis following Replit best practices"""
    
    # Redis configuration for Replit environment
    redis_url = 'redis://127.0.0.1:6379/0'
    
    logger.info(f"Creating Celery with Redis: {redis_url}")
    
    # Create Celery instance with Redis
    celery_app = Celery(
        'glb_optimizer_redis',
        broker=redis_url,
        backend=redis_url,
        include=['tasks', 'cleanup_scheduler', 'pipeline_tasks']
    )
    
    # Configure Celery following the guide
    celery_app.conf.update({
        'task_serializer': 'json',
        'accept_content': ['json'],
        'result_serializer': 'json',
        'timezone': 'UTC',
        'enable_utc': True,
        'task_track_started': True,
        'task_time_limit': 600,  # 10 minutes
        'task_soft_time_limit': 540,  # 9 minutes
        'worker_prefetch_multiplier': 1,
        'worker_max_memory_per_child': 512000,  # 512MB
        'task_acks_late': True,
        'task_reject_on_worker_lost': True,
        'result_expires': 3600,  # 1 hour
        'broker_connection_retry_on_startup': True,
        'broker_connection_retry': True
    })
    
    return celery_app

def create_celery_with_database_fallback():
    """Fallback to database broker when Redis unavailable"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not found for fallback")
    
    broker_url = f"db+{database_url}"
    
    logger.info(f"Creating Celery with database fallback: {broker_url[:50]}...")
    
    celery_app = Celery(
        'glb_optimizer_db_fallback',
        broker=broker_url,
        backend=broker_url,
        include=['tasks', 'cleanup_scheduler', 'pipeline_tasks']
    )
    
    celery_app.conf.update({
        'task_serializer': 'json',
        'accept_content': ['json'],
        'result_serializer': 'json',
        'timezone': 'UTC',
        'enable_utc': True,
        'task_track_started': True,
        'task_time_limit': 600,
        'task_soft_time_limit': 540,
        'worker_prefetch_multiplier': 1,
        'worker_max_memory_per_child': 512000,
        'task_acks_late': True,
        'task_reject_on_worker_lost': True,
        'result_expires': 3600,
        'database_short_lived_sessions': True,
        'database_table_names': {
            'task': 'celery_taskmeta',
            'group': 'celery_groupmeta',
        }
    })
    
    return celery_app

def get_celery_instance():
    """Get the appropriate Celery instance based on Redis availability"""
    
    if check_redis_availability():
        logger.info("✅ Redis available - using Redis broker")
        try:
            celery_app = create_celery_with_redis()
            # Test the connection
            celery_app.control.inspect().ping()
            return celery_app, 'redis'
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
    
    logger.info("⚠️ Redis unavailable - using database fallback")
    try:
        celery_app = create_celery_with_database_fallback()
        return celery_app, 'database'
    except Exception as e:
        logger.error(f"Database fallback failed: {e}")
        return None, 'none'

# Create the Celery instance
celery, broker_type = get_celery_instance()

if celery:
    logger.info(f"✅ Celery initialized with {broker_type} broker")
else:
    logger.warning("⚠️ Celery unavailable - will use synchronous processing")

# Import tasks to register them
try:
    import tasks
    import cleanup_scheduler
    import pipeline_tasks
    logger.info("✅ Celery tasks imported successfully")
except ImportError as e:
    logger.warning(f"Task import warning: {e}")