"""
Unified Celery Factory Module
============================
SINGLE SOURCE OF TRUTH for Celery initialization.

All task modules should import from this file:
    from celery_factory import celery, make_celery

This module handles:
- Redis connection (if available)
- Database fallback (PostgreSQL as broker)
- Synchronous fallback (when neither is available)
"""

import os
import logging
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_celery_instance = None
_broker_type = None


def check_redis_availability():
    """Check if Redis server is available"""
    try:
        import subprocess
        result = subprocess.run(
            ['redis-cli', 'ping'], 
            capture_output=True, 
            text=True, 
            timeout=2
        )
        return result.returncode == 0 and 'PONG' in result.stdout
    except Exception:
        return False


def get_broker_config():
    """
    Determine the best available broker configuration.
    Returns: tuple (broker_url, result_backend, broker_type)
    """
    redis_url = os.environ.get('REPLIT_REDIS_URL') or os.environ.get('REDIS_URL')
    database_url = os.environ.get('DATABASE_URL')
    
    if redis_url and redis_url != 'redis://localhost:6379/0':
        return redis_url, redis_url, 'redis'
    
    if check_redis_availability():
        local_redis = 'redis://127.0.0.1:6379/0'
        return local_redis, local_redis, 'redis'
    
    if database_url:
        db_broker = f"db+{database_url}"
        logger.info("Redis unavailable, using database as broker")
        return db_broker, db_broker, 'database'
    
    logger.warning("No broker available - Celery tasks will fail")
    return None, None, 'none'


def make_celery(app_name='glb_optimizer'):
    """
    Create and configure a Celery instance.
    
    Args:
        app_name: Name for the Celery application
        
    Returns:
        Configured Celery instance (or None if no broker available)
    """
    broker_url, result_backend, broker_type = get_broker_config()
    
    if not broker_url:
        logger.error("Cannot create Celery instance - no broker available")
        return None
    
    celery_app = Celery(
        app_name,
        broker=broker_url,
        backend=result_backend,
        include=['tasks', 'cleanup_scheduler']
    )
    
    celery_app.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        
        worker_concurrency=1,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        worker_max_tasks_per_child=10,
        
        task_time_limit=600,
        task_soft_time_limit=540,
        worker_max_memory_per_child=512000,
        
        task_track_started=True,
        task_reject_on_worker_lost=True,
        result_expires=3600,
        
        broker_connection_retry_on_startup=True,
        broker_connection_retry=True,
        
        task_routes={
            'tasks.optimize_glb_file': {'queue': 'optimization'},
            'cleanup.cleanup_old_files': {'queue': 'cleanup'},
            'cleanup.cleanup_orphaned_tasks': {'queue': 'cleanup'},
        },
        
        beat_schedule={
            'cleanup-old-files': {
                'task': 'cleanup.cleanup_old_files',
                'schedule': crontab(hour=2, minute=0),
            },
            'cleanup-orphaned-tasks': {
                'task': 'cleanup.cleanup_orphaned_tasks',
                'schedule': crontab(hour=2, minute=30),
            },
        } if os.environ.get('CLEANUP_ENABLED', 'true').lower() in ['true', '1', 'yes'] else {},
        
        worker_send_task_events=True,
        task_send_sent_event=True,
    )
    
    if broker_type == 'database':
        celery_app.conf.update(
            database_short_lived_sessions=True,
            database_table_names={
                'task': 'celery_taskmeta',
                'group': 'celery_groupmeta',
            }
        )
    
    logger.info(f"Celery initialized with {broker_type} broker: {broker_url[:50]}...")
    return celery_app


def get_celery():
    """
    Get the singleton Celery instance.
    Creates one if it doesn't exist.
    
    Returns:
        tuple: (celery_instance, broker_type)
    """
    global _celery_instance, _broker_type
    
    if _celery_instance is None:
        _, _, _broker_type = get_broker_config()
        _celery_instance = make_celery()
    
    return _celery_instance, _broker_type


def get_broker_type():
    """Get the current broker type without creating a new instance"""
    global _broker_type
    if _broker_type is None:
        _, _, _broker_type = get_broker_config()
    return _broker_type


celery, broker_type = get_celery()

if celery:
    logger.info(f"Celery factory initialized successfully with {broker_type} broker")
else:
    logger.warning("Celery unavailable - application will use synchronous processing")
