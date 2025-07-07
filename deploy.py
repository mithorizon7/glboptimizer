#!/usr/bin/env python3
"""
GLB Optimizer Deployment Script
Comprehensive production deployment with environment setup
"""

import os
import sys
import subprocess
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_environment():
    """Setup all required environment variables"""
    env_config = {
        'REDIS_URL': 'redis://localhost:6379/0',
        'CELERY_BROKER_URL': 'redis://localhost:6379/0',
        'CELERY_RESULT_BACKEND': 'redis://localhost:6379/0',
        'SESSION_SECRET': 'production_secret_key_12345',
        'FLASK_SECRET_KEY': 'production_secret_key_12345',
        'FLASK_ENV': 'production',
        'PYTHONPATH': '/home/runner/workspace'
    }
    
    for key, value in env_config.items():
        os.environ[key] = value
    
    logger.info("Environment variables configured")

def start_redis():
    """Start Redis server"""
    try:
        # Check if Redis is running
        result = subprocess.run(['redis-cli', 'ping'], capture_output=True, timeout=3)
        if result.returncode == 0:
            logger.info("Redis already running")
            return True
    except:
        pass
    
    # Start Redis
    subprocess.run(['redis-server', '--daemonize', 'yes', '--port', '6379'], check=False)
    time.sleep(2)
    logger.info("Redis server started")
    return True

def run_application():
    """Run the Flask application"""
    setup_environment()
    start_redis()
    
    logger.info("Starting GLB Optimizer Application")
    
    # Import and run Flask app
    try:
        from main import app
        logger.info("Flask app imported successfully")
        
        # Run with Gunicorn for production
        os.execvp('gunicorn', [
            'gunicorn',
            '--bind', '0.0.0.0:5000',
            '--workers', '1',
            '--timeout', '120',
            '--keep-alive', '2',
            '--max-requests', '1000',
            'main:app'
        ])
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        # Fallback to direct Flask
        from main import app
        app.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == '__main__':
    run_application()