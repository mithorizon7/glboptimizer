#!/usr/bin/env python3
"""
Production startup script with automatic cleanup scheduling
Starts Redis, Celery worker, Celery beat scheduler, and Flask application
"""

import os
import signal
import subprocess
import time
import sys
import logging
from config import get_config

# Load configuration
config = get_config()

# Configure logging
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)

class ProductionServerWithCleanup:
    def __init__(self):
        self.processes = {}
        self.running = True
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def start_redis(self):
        """Start Redis server"""
        try:
            # Check if Redis is already running
            result = subprocess.run(['redis-cli', 'ping'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                logger.info("Redis is already running")
                return
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        logger.info("Starting Redis server...")
        try:
            redis_process = subprocess.Popen(
                ['redis-server', '--daemonize', 'yes', '--port', '6379'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            time.sleep(2)  # Give Redis time to start
            
            # Verify Redis started
            result = subprocess.run(['redis-cli', 'ping'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                logger.info("Redis server started successfully")
                self.processes['redis'] = redis_process
            else:
                logger.error("Failed to start Redis server")
                sys.exit(1)
                
        except Exception as e:
            logger.error(f"Error starting Redis: {e}")
            sys.exit(1)
    
    def start_celery_worker(self):
        """Start Celery worker"""
        logger.info("Starting Celery worker...")
        try:
            worker_process = subprocess.Popen(
                ['celery', '-A', 'celery_app.celery', 'worker', 
                 '--loglevel=info', '--concurrency=1'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self.processes['celery_worker'] = worker_process
            logger.info("Celery worker started")
            time.sleep(3)  # Give worker time to initialize
            
        except Exception as e:
            logger.error(f"Error starting Celery worker: {e}")
            sys.exit(1)
    
    def start_celery_beat(self):
        """Start Celery beat scheduler for automatic cleanup"""
        if not config.CLEANUP_ENABLED:
            logger.info("Cleanup is disabled, skipping Celery beat scheduler")
            return
            
        logger.info("Starting Celery beat scheduler...")
        try:
            beat_process = subprocess.Popen(
                ['celery', '-A', 'celery_app.celery', 'beat', 
                 '--loglevel=info'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self.processes['celery_beat'] = beat_process
            logger.info("Celery beat scheduler started")
            time.sleep(2)  # Give beat time to initialize
            
        except Exception as e:
            logger.error(f"Error starting Celery beat: {e}")
            # Don't exit on beat failure, it's not critical for core functionality
            logger.warning("Continuing without automatic cleanup scheduling")
    
    def start_flask_app(self):
        """Start Flask application"""
        logger.info("Starting Flask application...")
        try:
            flask_process = subprocess.Popen(
                ['gunicorn', '--bind', '0.0.0.0:5000', '--reuse-port', 
                 '--reload', 'main:app'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self.processes['flask'] = flask_process
            logger.info("Flask application started on port 5000")
            
        except Exception as e:
            logger.error(f"Error starting Flask application: {e}")
            sys.exit(1)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        self.shutdown()
    
    def shutdown(self):
        """Shutdown all processes"""
        logger.info("Shutting down all processes...")
        
        # Shutdown order: Flask -> Celery Beat -> Celery Worker -> Redis
        shutdown_order = ['flask', 'celery_beat', 'celery_worker', 'redis']
        
        for process_name in shutdown_order:
            if process_name in self.processes:
                process = self.processes[process_name]
                if process.poll() is None:  # Process is still running
                    logger.info(f"Stopping {process_name}...")
                    try:
                        process.terminate()
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        logger.warning(f"Force killing {process_name}...")
                        process.kill()
                        process.wait()
                    logger.info(f"{process_name} stopped")
        
        logger.info("All processes stopped")
        sys.exit(0)
    
    def run(self):
        """Main run method"""
        logger.info("Starting GLB Optimizer with cleanup scheduling...")
        logger.info(f"Configuration: {config.get_config_summary()}")
        
        try:
            # Start services in order
            self.start_redis()
            self.start_celery_worker()
            self.start_celery_beat()
            self.start_flask_app()
            
            logger.info("All services started successfully!")
            logger.info("GLB Optimizer is ready to accept requests")
            
            # Keep the main process alive and monitor subprocesses
            while self.running:
                time.sleep(5)
                
                # Check if critical processes are still running
                critical_processes = ['flask', 'celery_worker']
                for proc_name in critical_processes:
                    if proc_name in self.processes:
                        if self.processes[proc_name].poll() is not None:
                            logger.error(f"Critical process {proc_name} has died!")
                            self.shutdown()
                            sys.exit(1)
                            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
            self.shutdown()
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            self.shutdown()
            sys.exit(1)

def manual_cleanup():
    """Run manual cleanup for testing"""
    logger.info("Running manual cleanup...")
    try:
        from cleanup_scheduler import manual_cleanup
        file_result, task_result = manual_cleanup()
        logger.info(f"Manual cleanup completed: {file_result}, {task_result}")
    except Exception as e:
        logger.error(f"Manual cleanup failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'cleanup':
        manual_cleanup()
    else:
        server = ProductionServerWithCleanup()
        server.run()