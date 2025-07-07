import os
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Celery
def make_celery(app_name=__name__):
    # Use Replit's native Redis URL if available, otherwise fall back to database broker
    redis_url = os.environ.get('REPLIT_REDIS_URL') or os.environ.get('REDIS_URL')
    
    # If no Redis available, use database as broker (PostgreSQL)
    if not redis_url or redis_url == 'redis://localhost:6379/0':
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            # Use PostgreSQL as both broker and result backend
            broker_url = f"db+{database_url}"
            result_backend = f"db+{database_url}"
            print(f"Using database broker: {broker_url[:50]}...")
        else:
            # Final fallback to localhost Redis (will fail but explicit)
            broker_url = result_backend = 'redis://localhost:6379/0'
            print("Warning: No Redis or Database URL available, using localhost Redis")
    else:
        broker_url = result_backend = redis_url
        print(f"Using Redis broker: {broker_url}")
    
    celery = Celery(
        app_name,
        broker=broker_url,
        backend=result_backend,
        include=['tasks', 'cleanup_scheduler', 'pipeline_tasks']  # Include all task modules
    )
    
    # Force broker and backend configuration (override any cached values)
    celery.conf.broker_url = broker_url
    celery.conf.result_backend = result_backend
    
    # Verify configuration was set correctly
    actual_broker = getattr(celery.conf, 'broker_url', 'NOT SET')
    actual_backend = getattr(celery.conf, 'result_backend', 'NOT SET')
    print(f"✓ Final Celery broker config: {actual_broker[:70]}...")
    print(f"✓ Final Celery backend config: {actual_backend[:70]}...")
    
    # Additional force configuration for problematic environments
    celery.conf.update(broker_url=broker_url, result_backend=result_backend)
    
    # Configure Celery settings
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        
        # Worker configuration for optimization tasks
        worker_concurrency=1,  # Only run one optimization at a time to prevent resource exhaustion
        worker_prefetch_multiplier=1,  # Don't prefetch tasks
        task_acks_late=True,  # Acknowledge task only after completion
        worker_max_tasks_per_child=10,  # Restart worker after 10 tasks to prevent memory leaks
        
        # Time limits for tasks
        task_time_limit=600,  # Hard time limit: 10 minutes
        task_soft_time_limit=540,  # Soft time limit: 9 minutes
        
        # Memory limit per worker process (in KB)
        worker_max_memory_per_child=512000,  # 512MB
        
        # Task routing and limits
        task_routes={
            'tasks.optimize_glb_file': {'queue': 'optimization'},
            'cleanup.cleanup_old_files': {'queue': 'cleanup'},
            'cleanup.cleanup_orphaned_tasks': {'queue': 'cleanup'},
        },
        
        # Periodic task schedule for cleanup
        beat_schedule={
            'cleanup-old-files': {
                'task': 'cleanup.cleanup_old_files',
                'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
            },
            'cleanup-orphaned-tasks': {
                'task': 'cleanup.cleanup_orphaned_tasks',
                'schedule': crontab(hour=2, minute=30),  # Daily at 2:30 AM
            },
        } if os.environ.get('CLEANUP_ENABLED', 'true').lower() in ['true', '1', 'yes'] else {},
        
        # Result expiration
        result_expires=3600,  # Results expire after 1 hour
        
        # Monitoring
        worker_send_task_events=True,
        task_send_sent_event=True,
    )
    
    return celery

# Create the single, shared instance here
celery = None

def get_celery():
    """Get or create the Celery instance"""
    global celery
    if celery is None:
        celery = make_celery()
    return celery

# Initialize immediately
celery = get_celery()

# Force task discovery by importing task modules
try:
    import tasks  # This registers tasks.optimize_glb_file
    import cleanup_scheduler  # This registers cleanup tasks
    import pipeline_tasks  # This registers pipeline tasks
except ImportError as e:
    import logging
    logging.warning(f"Failed to import some task modules: {e}")