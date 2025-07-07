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
def create_app():
    """
    Creates and configures the Flask application object.
    This is the factory that Gunicorn will use via wsgi.py.
    """
    from config import get_config
    from celery_app import celery
    
    app = Flask(__name__)
    
    # Load configuration
    config = get_config()
    app.secret_key = config.SECRET_KEY
    app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH
    
    # Apply middleware
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # Import and register routes within app context
    with app.app_context():
        # Import route functions from app.py
        from app import (add_security_headers, get_db, get_or_create_user_session,
                        allowed_file, index, upload_file, get_progress, download_file,
                        cleanup_task, get_original_file, download_error_logs,
                        admin_analytics, admin_stats)
        
        # Register middleware
        app.after_request(add_security_headers)
        
        # Register routes
        app.add_url_rule('/', view_func=index, methods=['GET'])
        app.add_url_rule('/upload', view_func=upload_file, methods=['POST'])
        app.add_url_rule('/progress/<task_id>', view_func=get_progress, methods=['GET'])
        app.add_url_rule('/download/<task_id>', view_func=download_file, methods=['GET'])
        app.add_url_rule('/cleanup/<task_id>', view_func=cleanup_task, methods=['POST'])
        app.add_url_rule('/original/<task_id>', view_func=get_original_file, methods=['GET'])
        app.add_url_rule('/download_logs/<task_id>', view_func=download_error_logs, methods=['GET'])
        app.add_url_rule('/admin/analytics', view_func=admin_analytics, methods=['GET'])
        app.add_url_rule('/admin/stats', view_func=admin_stats, methods=['GET'])
        
    logger.info("Flask application created with factory pattern")
    return app

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

# Create app instance for backward compatibility with workflow (temporary)
app = None

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
else:
    # For Gunicorn compatibility - create app without service initialization
    app = create_app()
