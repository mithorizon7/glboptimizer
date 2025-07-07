#!/usr/bin/env python3
"""
Celery worker startup script for GLB optimization tasks
"""
import os
import sys
import subprocess
import time
import signal
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def start_redis():
    """Start Redis server"""
    try:
        # Check if Redis is already running
        result = subprocess.run(['redis-cli', 'ping'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip() == 'PONG':
            logger.info("Redis is already running")
            return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    logger.info("Starting Redis server...")
    redis_process = subprocess.Popen(
        ['redis-server', '--daemonize', 'no', '--port', '6379'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait a moment for Redis to start
    time.sleep(2)
    
    # Verify Redis is running
    try:
        result = subprocess.run(['redis-cli', 'ping'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip() == 'PONG':
            logger.info("Redis started successfully")
            return redis_process
        else:
            logger.error("Redis failed to start properly")
            return None
    except Exception as e:
        logger.error(f"Failed to verify Redis startup: {e}")
        return None

def start_celery_worker():
    """Start Celery worker"""
    logger.info("Starting Celery worker...")
    
    # Set environment variables
    os.environ['REDIS_URL'] = 'redis://localhost:6379/0'
    
    # Start Celery worker
    worker_process = subprocess.Popen([
        'celery', '-A', 'celery_app', 'worker',
        '--loglevel=info',
        '--concurrency=1',  # Only one optimization at a time
        '--queues=optimization',
        '--hostname=worker@%h'
    ])
    
    return worker_process

def main():
    """Main function to start Redis and Celery worker"""
    redis_process = None
    worker_process = None
    
    def signal_handler(signum, frame):
        logger.info("Received signal to shut down...")
        if worker_process:
            logger.info("Stopping Celery worker...")
            worker_process.terminate()
            worker_process.wait()
        if redis_process:
            logger.info("Stopping Redis server...")
            redis_process.terminate()
            redis_process.wait()
        sys.exit(0)
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start Redis
        redis_process = start_redis()
        
        # Start Celery worker
        worker_process = start_celery_worker()
        
        logger.info("GLB Optimizer task queue is running...")
        logger.info("Press Ctrl+C to stop")
        
        # Wait for worker process
        worker_process.wait()
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        signal_handler(None, None)

if __name__ == '__main__':
    main()