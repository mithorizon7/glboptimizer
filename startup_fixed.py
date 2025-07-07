#!/usr/bin/env python3
"""
Fixed GLB Optimizer Startup Script
Implements all the corrected fixes from the attached guidance
"""

import os
import subprocess
import time
import logging
import atexit

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Keep track of subprocesses to terminate them on exit
processes = []

def cleanup_processes():
    """Ensure all background processes are terminated when the app exits."""
    logger.info("Shutting down background processes...")
    for p in processes:
        if p.poll() is None:  # if the process is still running
            p.terminate()
            p.wait()
    logger.info("Cleanup complete.")

# Register the cleanup function to run on exit
atexit.register(cleanup_processes)

def ensure_redis_running():
    """Ensure Redis is running, start it if needed."""
    try:
        result = subprocess.run(['redis-cli', 'ping'], capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and 'PONG' in result.stdout:
            logger.info("✅ Redis is already running.")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.info("Redis not found or timed out, attempting to start.")

    logger.info("Starting Redis server in the background...")
    try:
        # Start Redis and let it run in the background
        p = subprocess.Popen(['redis-server', '--daemonize', 'yes', '--port', '6379'])
        processes.append(p)  # Track for cleanup
        time.sleep(2)  # Give it a moment to start
        # Verify it started
        result = subprocess.run(['redis-cli', 'ping'], capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and 'PONG' in result.stdout:
            logger.info("✅ Redis started successfully.")
            return True
        else:
            logger.error("❌ Failed to verify Redis startup.")
            return False
    except Exception as e:
        logger.error(f"❌ Failed to start Redis: {e}")
        return False

def start_celery_worker():
    """Start Celery worker in the same terminal for easy debugging."""
    logger.info("Starting Celery worker...")
    try:
        # Define the command to run Celery worker
        cmd = [
            'celery', '-A', 'tasks', 'worker',
            '--loglevel=info',
            '--concurrency=1',
            '--queues=optimization'
        ]
        # Use Popen to run it as a background process that logs to the same terminal
        p = subprocess.Popen(cmd)
        processes.append(p)  # Track for cleanup
        logger.info("✅ Celery worker started.")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start Celery worker: {e}")
        return False

if __name__ == '__main__':
    # Set critical environment variables first, before any other imports
    # This ensures Celery and Flask pick up the correct config
    os.environ['REDIS_URL'] = 'redis://localhost:6379/0'
    os.environ['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
    os.environ['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'
    os.environ['FLASK_ENV'] = 'development'
    os.environ['SESSION_SECRET'] = 'dev_secret_key_change_in_production'

    logger.info("🚀 Starting GLB Optimizer in Development Mode...")

    # 1. Ensure Redis is running
    ensure_redis_running()
    
    # 2. Initialize the database
    try:
        from database import init_database
        init_database()
        logger.info("✅ Database initialized successfully.")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        
    # 3. Start Celery worker
    start_celery_worker()
    
    # 4. Import and start Flask app
    try:
        from app import app
        logger.info("✅ Flask app loaded successfully.")
        
        # Start Flask in development mode
        logger.info("🌐 Starting Flask development server...")
        logger.info("   Application available at: http://0.0.0.0:5000")
        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"❌ Failed to start Flask app: {e}")
    finally:
        cleanup_processes()