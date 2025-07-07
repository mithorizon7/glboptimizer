#!/usr/bin/env python3
"""
GLB Optimizer Development Server
================================

Local development script that runs Flask in debug mode with all services
in the same terminal for easy troubleshooting and development.

Usage:
    python develop.py

Features:
- Flask debug mode with auto-reload
- Redis auto-start and management
- Celery worker with visible logs
- Database auto-initialization
- Comprehensive error handling
- Process cleanup on exit
"""

import os
import sys
import subprocess
import time
import logging
import atexit
import signal
from pathlib import Path

# Set sane defaults BEFORE any other application imports
os.environ.setdefault('FLASK_ENV', 'development')
os.environ.setdefault('DATABASE_URL', os.environ.get('DATABASE_URL', 'sqlite:///dev.db'))
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/0')
os.environ.setdefault('CELERY_BROKER_URL', os.environ['REDIS_URL'])
os.environ.setdefault('CELERY_RESULT_BACKEND', os.environ['REDIS_URL'])
os.environ.setdefault('SESSION_SECRET', 'dev_secret_key_for_local_development_only')

# Configure development logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('develop')

# Track background processes for cleanup
processes = []

def cleanup_processes():
    """Clean up all background processes on exit"""
    logger.info("Shutting down development server...")
    for process in processes:
        if process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    logger.info("Development server shutdown complete")

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, shutting down...")
    cleanup_processes()
    sys.exit(0)

# Register cleanup handlers
atexit.register(cleanup_processes)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def setup_environment():
    """Set up development environment variables"""
    env_vars = {
        'REDIS_URL': 'redis://localhost:6379/0',
        'CELERY_BROKER_URL': 'redis://localhost:6379/0',
        'CELERY_RESULT_BACKEND': 'redis://localhost:6379/0',
        'FLASK_ENV': 'development',
        'FLASK_DEBUG': 'true',
        'SESSION_SECRET': 'dev_secret_key_change_in_production',
        'LOG_LEVEL': 'DEBUG',
        'CLEANUP_ENABLED': 'false',  # Disable automatic cleanup in development
        'FILE_RETENTION_HOURS': '24'
    }
    
    for key, value in env_vars.items():
        os.environ.setdefault(key, value)
    
    logger.info("Development environment configured")

def ensure_redis_running():
    """Start Redis server if not already running"""
    try:
        # Check if Redis is already running
        result = subprocess.run(
            ['redis-cli', 'ping'], 
            capture_output=True, 
            text=True, 
            timeout=2
        )
        if result.returncode == 0 and 'PONG' in result.stdout:
            logger.info("Redis server already running")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    logger.info("Starting Redis server...")
    try:
        # Start Redis in background
        process = subprocess.Popen([
            'redis-server',
            '--daemonize', 'yes',
            '--port', '6379',
            '--bind', '127.0.0.1',
            '--save', '""',  # Disable persistence for development
            '--appendonly', 'no'
        ])
        processes.append(process)
        
        # Wait for Redis to start
        time.sleep(2)
        
        # Verify Redis is running
        result = subprocess.run(
            ['redis-cli', 'ping'], 
            capture_output=True, 
            text=True, 
            timeout=5
        )
        if result.returncode == 0 and 'PONG' in result.stdout:
            logger.info("Redis server started successfully")
            return True
        else:
            logger.error("Failed to verify Redis startup")
            return False
            
    except Exception as e:
        logger.error(f"Failed to start Redis: {e}")
        return False

def start_celery_worker():
    """Start Celery worker with visible logs for development"""
    logger.info("Starting Celery worker...")
    try:
        # Start Celery worker with development settings
        process = subprocess.Popen([
            'celery', '-A', 'tasks', 'worker',
            '--loglevel=info',
            '--concurrency=1',
            '--pool=solo',  # Use solo pool for development (Windows compatible)
            '--without-heartbeat',
            '--without-mingle',
            '--without-gossip'
        ])
        processes.append(process)
        
        # Give Celery a moment to start
        time.sleep(3)
        
        if process.poll() is None:
            logger.info("Celery worker started successfully")
            return True
        else:
            logger.error("Celery worker failed to start")
            return False
            
    except Exception as e:
        logger.error(f"Failed to start Celery worker: {e}")
        logger.info("Application will continue without background task processing")
        return False

def initialize_database():
    """Initialize the database with tables"""
    try:
        from database import init_database
        init_database()
        logger.info("Database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False

def start_flask_app():
    """Start Flask application in development mode"""
    try:
        # Import Flask app after environment is set up
        from app import app
        
        logger.info("Starting Flask development server...")
        logger.info("=" * 50)
        logger.info("GLB Optimizer Development Server")
        logger.info("Application URL: http://localhost:5000")
        logger.info("Admin Dashboard: http://localhost:5000/admin/analytics")
        logger.info("Press Ctrl+C to stop the server")
        logger.info("=" * 50)
        
        # Run Flask in development mode
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=True,
            use_reloader=False,  # Disable reloader to prevent process duplication
            threaded=True
        )
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Flask application failed: {e}")
        raise

def check_dependencies():
    """Check if required tools are available"""
    required_tools = ['redis-server', 'redis-cli', 'celery']
    missing_tools = []
    
    for tool in required_tools:
        try:
            subprocess.run([tool, '--version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing_tools.append(tool)
    
    if missing_tools:
        logger.error(f"Missing required tools: {', '.join(missing_tools)}")
        logger.error("Please install missing dependencies before running development server")
        return False
    
    logger.info("All required dependencies are available")
    return True

def main():
    """Main development server entry point"""
    print("🚀 GLB Optimizer Development Server")
    print("=" * 40)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Set up environment
    setup_environment()
    
    # Start services
    services_status = {
        'redis': ensure_redis_running(),
        'database': initialize_database(),
        'celery': start_celery_worker()
    }
    
    # Report service status
    logger.info("Service Status:")
    for service, status in services_status.items():
        status_text = "✓ Running" if status else "✗ Failed"
        logger.info(f"  {service}: {status_text}")
    
    # Start Flask app (this will block until shutdown)
    try:
        start_flask_app()
    finally:
        cleanup_processes()

if __name__ == '__main__':
    main()