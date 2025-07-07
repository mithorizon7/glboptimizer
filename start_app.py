#!/usr/bin/env python3
"""
Startup script for GLB Optimizer with automatic dependency management
Handles Redis, database initialization, and Flask application startup
"""

import os
import sys
import time
import subprocess
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def ensure_redis_running():
    """Ensure Redis is running, start it if needed"""
    try:
        # Check if Redis is already running
        result = subprocess.run(['redis-cli', 'ping'], 
                               capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and 'PONG' in result.stdout:
            logger.info("Redis is already running")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    try:
        # Start Redis server
        logger.info("Starting Redis server...")
        subprocess.Popen([
            'redis-server', 
            '--daemonize', 'yes',
            '--port', '6379',
            '--bind', '127.0.0.1'
        ])
        
        # Wait for Redis to start
        for i in range(30):  # Wait up to 30 seconds
            try:
                result = subprocess.run(['redis-cli', 'ping'], 
                                       capture_output=True, text=True, timeout=2)
                if result.returncode == 0 and 'PONG' in result.stdout:
                    logger.info("Redis started successfully")
                    return True
            except subprocess.TimeoutExpired:
                pass
            time.sleep(1)
        
        logger.error("Failed to start Redis within timeout")
        return False
        
    except Exception as e:
        logger.error(f"Failed to start Redis: {e}")
        return False

def setup_environment():
    """Set up environment variables"""
    # Set Redis URL
    if not os.environ.get('REDIS_URL'):
        os.environ['REDIS_URL'] = 'redis://localhost:6379/0'
        logger.info("Set REDIS_URL environment variable")
    
    # Ensure other required environment variables are set
    env_vars = {
        'CELERY_BROKER_URL': 'redis://localhost:6379/0',
        'CELERY_RESULT_BACKEND': 'redis://localhost:6379/0',
        'FLASK_SECRET_KEY': 'dev_secret_key_change_in_production'
    }
    
    for var, default in env_vars.items():
        if not os.environ.get(var):
            os.environ[var] = default
            logger.info(f"Set {var} environment variable")

def initialize_database():
    """Initialize database tables"""
    try:
        logger.info("Initializing database...")
        from database import init_database
        init_database()
        logger.info("Database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False

def start_celery_worker():
    """Start Celery worker in background"""
    try:
        logger.info("Starting Celery worker...")
        celery_cmd = [
            sys.executable, '-m', 'celery', 
            '-A', 'celery_app.celery', 
            'worker', 
            '--loglevel=info',
            '--concurrency=1'
        ]
        
        subprocess.Popen(celery_cmd, 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE)
        logger.info("Celery worker started")
        return True
    except Exception as e:
        logger.error(f"Failed to start Celery worker: {e}")
        return False

def main():
    """Main startup function"""
    logger.info("Starting GLB Optimizer application...")
    
    # Setup environment
    setup_environment()
    
    # Ensure Redis is running
    if not ensure_redis_running():
        logger.warning("Redis failed to start, some features may not work")
    
    # Initialize database
    if not initialize_database():
        logger.warning("Database initialization failed, continuing without database")
    
    # Start Celery worker
    if not start_celery_worker():
        logger.warning("Celery worker failed to start, tasks will run synchronously")
    
    # Import and run Flask app
    try:
        logger.info("Starting Flask application...")
        from app import app
        
        # Start Flask in production mode with Gunicorn-like settings
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,
            threaded=True
        )
        
    except Exception as e:
        logger.error(f"Failed to start Flask application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()