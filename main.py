#!/usr/bin/env python3
import os
import subprocess
import time
import logging
import atexit
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

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
            'celery', '-A', 'tasks', 'worker',
            '--loglevel=info',
            '--concurrency=1',
            '--detach'
        ])
        logger.info("Celery worker started in background")
        return True
    except Exception as e:
        logger.error(f"Failed to start Celery worker: {e}")
        return False

# --- THE APPLICATION FACTORY ---
# App creation now handled in app.py to avoid circular imports

# --- ONE-TIME SERVICE INITIALIZATION ---
def initialize_services():
    """
    This function runs the one-time setup for all services.
    It should only be called once by the main process.
    """
    logger.info("Initializing services...")
    
    # Set environment variables
    os.environ['REDIS_URL'] = 'redis://localhost:6379/0'
    os.environ['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
    os.environ['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'

    # Ensure Redis is running
    ensure_redis_running()

    # Initialize database
    try:
        logger.info("Initializing database...")
        from database import init_database
        init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    # Start Celery worker
    start_celery_worker()

    # Give services time to start
    time.sleep(2)

# --- DEVELOPMENT SERVER ENTRY POINT ---
if __name__ == '__main__':
    # This block only runs when you execute "python main.py"
    # It will NOT run when Gunicorn imports the file.
    
    # Run the one-time service initializations
    initialize_services()
    
    # Create the app using the factory
    app = create_app()
    
    # Start the Flask development server
    logger.info("Starting Flask development server...")
    app.run(host='0.0.0.0', port=5000, debug=True)
