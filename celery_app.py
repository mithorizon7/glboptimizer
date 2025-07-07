import os
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Celery
def make_celery(app_name=__name__):
    # Use Redis as the broker and result backend
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    
    celery = Celery(
        app_name,
        broker=redis_url,
        backend=redis_url,
        include=['tasks', 'cleanup_scheduler', 'pipeline_tasks']  # Include all task modules
    )
    
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
celery = make_celery()

# Force task discovery by importing task modules
try:
    import tasks  # This registers tasks.optimize_glb_file
    import cleanup_scheduler  # This registers cleanup tasks
    import pipeline_tasks  # This registers pipeline tasks
except ImportError as e:
    import logging
    logging.warning(f"Failed to import some task modules: {e}")