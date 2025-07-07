import os
from celery import Celery

# Configure Celery
def make_celery(app_name=__name__):
    # Use Redis as the broker and result backend
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    
    celery = Celery(
        app_name,
        broker=redis_url,
        backend=redis_url,
        include=['tasks']
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
        
        # Task routing and limits
        task_routes={
            'tasks.optimize_glb_file': {'queue': 'optimization'},
        },
        
        # Result expiration
        result_expires=3600,  # Results expire after 1 hour
        
        # Monitoring
        worker_send_task_events=True,
        task_send_sent_event=True,
    )
    
    return celery

# Create Celery instance
celery = make_celery()

if __name__ == '__main__':
    celery.start()