import os
import subprocess
import time
import logging
from app import app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ensure_redis_running():
    """Ensure Redis is running, start it if needed"""
    try:
        # Check if Redis is accessible
        result = subprocess.run(['redis-cli', 'ping'], capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and result.stdout.strip() == 'PONG':
            logger.info("Redis is running")
            return True
    except:
        pass
    
    logger.info("Starting Redis server...")
    try:
        # Start Redis in background
        subprocess.Popen(['redis-server', '--daemonize', 'yes', '--port', '6379'])
        
        # Wait for Redis to start
        for i in range(10):
            time.sleep(1)
            try:
                result = subprocess.run(['redis-cli', 'ping'], capture_output=True, text=True, timeout=2)
                if result.returncode == 0 and result.stdout.strip() == 'PONG':
                    logger.info("Redis started successfully")
                    return True
            except:
                continue
        
        logger.warning("Redis may not have started properly")
        return False
        
    except Exception as e:
        logger.error(f"Failed to start Redis: {e}")
        return False

def start_celery_worker():
    """Start Celery worker in background"""
    try:
        logger.info("Starting Celery worker...")
        subprocess.Popen([
            'celery', '-A', 'celery_app', 'worker',
            '--loglevel=info',
            '--concurrency=1',
            '--queues=optimization',
            '--detach'
        ])
        logger.info("Celery worker started in background")
        return True
    except Exception as e:
        logger.error(f"Failed to start Celery worker: {e}")
        return False

if __name__ == '__main__':
    # Set environment
    os.environ['REDIS_URL'] = 'redis://localhost:6379/0'
    
    # Ensure Redis is running
    ensure_redis_running()
    
    # Start Celery worker
    start_celery_worker()
    
    # Give services time to start
    time.sleep(2)
    
    # Start Flask app
    logger.info("Starting Flask application...")
    app.run(host='0.0.0.0', port=5000, debug=True)
