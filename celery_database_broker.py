import os
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_database_celery():
    """Create Celery instance with database broker - isolated configuration"""
    
    # Get database URL and force database broker
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not found - cannot create database broker")
    
    # Force database broker URL
    broker_url = f"db+{database_url}"
    result_backend = f"db+{database_url}"
    
    print(f"🔗 Creating Celery with database broker: {broker_url[:50]}...")
    
    # Create Celery with forced database configuration
    celery_app = Celery(
        'glb_optimizer_db',
        broker=broker_url,
        backend=result_backend,
        include=['tasks', 'cleanup_scheduler', 'pipeline_tasks']
    )
    
    # Override any existing configuration completely
    celery_app.conf.clear()
    
    # Set database broker configuration directly
    celery_app.conf.update({
        'broker_url': broker_url,
        'result_backend': result_backend,
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
    
    # Verify configuration
    final_broker = celery_app.conf.broker_url
    final_backend = celery_app.conf.result_backend
    
    print(f"✅ Final broker: {final_broker[:50]}...")
    print(f"✅ Final backend: {final_backend[:50]}...")
    
    if not final_broker.startswith('db+postgresql'):
        raise ValueError(f"Configuration failed! Got broker: {final_broker}")
    
    return celery_app

# Create the database-specific Celery instance
celery = create_database_celery()

# Force task discovery
try:
    import tasks
    import cleanup_scheduler  
    import pipeline_tasks
    print("✅ Task modules imported successfully")
except ImportError as e:
    print(f"⚠️ Task import warning: {e}")