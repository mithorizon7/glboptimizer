#!/usr/bin/env python3
"""
Production-ready GLB Optimizer Application Runner
Handles all dependencies and environment setup automatically
"""

import os
import subprocess
import time
import logging
import signal
import sys
from threading import Thread

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GLBOptimizerRunner:
    def __init__(self):
        self.redis_process = None
        self.celery_process = None
        self.flask_process = None
        
    def setup_environment(self):
        """Set up all required environment variables"""
        env_vars = {
            'REDIS_URL': 'redis://localhost:6379/0',
            'CELERY_BROKER_URL': 'redis://localhost:6379/0',
            'CELERY_RESULT_BACKEND': 'redis://localhost:6379/0',
            'FLASK_SECRET_KEY': 'dev_secret_key_change_in_production',
            'FLASK_ENV': 'development',
            'FLASK_DEBUG': 'true'
        }
        
        for key, value in env_vars.items():
            os.environ.setdefault(key, value)
            
        logger.info("Environment variables configured")
        
    def start_redis(self):
        """Start Redis server"""
        try:
            # Check if Redis is already running
            result = subprocess.run(['redis-cli', 'ping'], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                logger.info("Redis is already running")
                return True
        except:
            pass
            
        try:
            # Start Redis server
            logger.info("Starting Redis server...")
            self.redis_process = subprocess.Popen([
                'redis-server', 
                '--daemonize', 'yes',
                '--port', '6379',
                '--bind', '127.0.0.1'
            ])
            time.sleep(2)
            
            # Verify Redis is running
            result = subprocess.run(['redis-cli', 'ping'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                logger.info("Redis server started successfully")
                return True
            else:
                logger.error("Redis server failed to start")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start Redis: {e}")
            return False
            
    def start_celery_worker(self):
        """Start Celery worker in background"""
        try:
            logger.info("Starting Celery worker...")
            self.celery_process = subprocess.Popen([
                'celery', '-A', 'celery_app.celery', 'worker',
                '--loglevel=info',
                '--concurrency=1'
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(3)
            logger.info("Celery worker started successfully")
            return True
        except Exception as e:
            logger.warning(f"Celery worker failed to start: {e}")
            logger.info("Application will run without background processing")
            return False
            
    def start_flask_app(self):
        """Start Flask application"""
        try:
            logger.info("Starting Flask application...")
            
            # Import the Flask app
            from app import app
            
            # Start the application
            app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
            
        except Exception as e:
            logger.error(f"Flask application failed to start: {e}")
            return False
            
    def cleanup(self):
        """Clean up all processes"""
        logger.info("Shutting down GLB Optimizer...")
        
        if self.celery_process:
            self.celery_process.terminate()
            self.celery_process.wait(timeout=5)
            
        if self.redis_process:
            self.redis_process.terminate()
            self.redis_process.wait(timeout=5)
            
        logger.info("Cleanup completed")
        
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.cleanup()
        sys.exit(0)
        
    def run(self):
        """Main application runner"""
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        logger.info("🚀 Starting GLB Optimizer Application")
        logger.info("=" * 50)
        
        # Setup environment
        self.setup_environment()
        
        # Start Redis
        if not self.start_redis():
            logger.warning("Redis failed to start, continuing without task queue")
            
        # Start Celery worker
        self.start_celery_worker()
        
        # Start Flask application
        try:
            self.start_flask_app()
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            self.cleanup()

if __name__ == '__main__':
    runner = GLBOptimizerRunner()
    runner.run()