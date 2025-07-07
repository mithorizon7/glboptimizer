#!/usr/bin/env python3
"""
Production startup script for GLB Optimizer with Celery task queue
This script starts Redis, Celery worker, and the Flask application
"""
import os
import sys
import subprocess
import time
import signal
import logging
import threading
from multiprocessing import Process

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProductionServer:
    def __init__(self):
        self.redis_process = None
        self.celery_process = None
        self.flask_process = None
        self.running = True
        
    def start_redis(self):
        """Start Redis server"""
        try:
            # Check if Redis is already running
            result = subprocess.run(['redis-cli', 'ping'], capture_output=True, text=True, timeout=2)
            if result.returncode == 0 and result.stdout.strip() == 'PONG':
                logger.info("Redis is already running")
                return True
        except:
            pass
        
        logger.info("Starting Redis server...")
        try:
            self.redis_process = subprocess.Popen(
                ['redis-server', '--port', '6379', '--daemonize', 'no'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
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
                    
            logger.error("Redis failed to start within 10 seconds")
            return False
            
        except Exception as e:
            logger.error(f"Failed to start Redis: {e}")
            return False
    
    def start_celery_worker(self):
        """Start Celery worker"""
        logger.info("Starting Celery worker...")
        
        # Set environment variables
        os.environ['REDIS_URL'] = 'redis://localhost:6379/0'
        
        try:
            self.celery_process = subprocess.Popen([
                sys.executable, '-m', 'celery', '-A', 'celery_app', 'worker',
                '--loglevel=info',
                '--concurrency=1',
                '--queues=optimization',
                '--hostname=worker@%h'
            ])
            
            logger.info("Celery worker started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Celery worker: {e}")
            return False
    
    def start_flask_app(self):
        """Start Flask application"""
        logger.info("Starting Flask application...")
        
        # Set environment variables
        os.environ['REDIS_URL'] = 'redis://localhost:6379/0'
        
        try:
            self.flask_process = subprocess.Popen([
                'gunicorn', '--bind', '0.0.0.0:5000', '--reuse-port', '--reload', 'main:app'
            ])
            
            logger.info("Flask application started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Flask application: {e}")
            return False
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("Received shutdown signal...")
        self.running = False
        self.shutdown()
    
    def shutdown(self):
        """Shutdown all processes"""
        logger.info("Shutting down all services...")
        
        if self.flask_process:
            logger.info("Stopping Flask application...")
            self.flask_process.terminate()
            try:
                self.flask_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.flask_process.kill()
        
        if self.celery_process:
            logger.info("Stopping Celery worker...")
            self.celery_process.terminate()
            try:
                self.celery_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.celery_process.kill()
        
        if self.redis_process:
            logger.info("Stopping Redis server...")
            self.redis_process.terminate()
            try:
                self.redis_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.redis_process.kill()
        
        logger.info("All services stopped")
    
    def run(self):
        """Main run method"""
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        try:
            # Start services in order
            if not self.start_redis():
                logger.error("Failed to start Redis, exiting...")
                return 1
            
            time.sleep(2)  # Give Redis time to fully start
            
            if not self.start_celery_worker():
                logger.error("Failed to start Celery worker, exiting...")
                return 1
            
            time.sleep(3)  # Give Celery time to start
            
            if not self.start_flask_app():
                logger.error("Failed to start Flask application, exiting...")
                return 1
            
            logger.info("GLB Optimizer is running in production mode!")
            logger.info("Services:")
            logger.info("  - Redis: localhost:6379")
            logger.info("  - Celery Worker: Processing optimization tasks")
            logger.info("  - Flask App: http://0.0.0.0:5000")
            logger.info("Press Ctrl+C to stop all services")
            
            # Wait for processes and monitor health
            while self.running:
                # Check if any process has died
                if self.redis_process and self.redis_process.poll() is not None:
                    logger.error("Redis process died unexpectedly")
                    break
                
                if self.celery_process and self.celery_process.poll() is not None:
                    logger.error("Celery worker process died unexpectedly")
                    break
                
                if self.flask_process and self.flask_process.poll() is not None:
                    logger.error("Flask process died unexpectedly")
                    break
                
                time.sleep(5)
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt...")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        finally:
            self.shutdown()
        
        return 0

if __name__ == '__main__':
    server = ProductionServer()
    sys.exit(server.run())