#!/usr/bin/env python3
"""
GLB Optimizer Production Server
===============================

Production deployment script that manages all services using production-grade
servers and proper process management for scalable deployment.

Usage:
    python run_production.py

Features:
- Gunicorn WSGI server for Flask
- Redis server with production settings  
- Celery worker with optimized configuration
- Celery beat for automated cleanup tasks
- Proper signal handling and graceful shutdown
- Health checks and monitoring
- Systemd-compatible process management
"""

import os
import sys
import subprocess
import time
import logging
import signal
import json

# Configure production logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('glb_optimizer_production.log')
    ]
)
logger = logging.getLogger('production')

class ProductionServer:
    """Production server manager for GLB Optimizer"""
    
    def __init__(self):
        self.processes = {}
        self.shutdown_requested = False
        
    def setup_environment(self):
        """Set up production environment variables"""
        env_vars = {
            'FLASK_ENV': 'production',
            'FLASK_DEBUG': 'false',
            'REDIS_URL': 'redis://localhost:6379/0',
            'CELERY_BROKER_URL': 'redis://localhost:6379/0',
            'CELERY_RESULT_BACKEND': 'redis://localhost:6379/0',
            'LOG_LEVEL': 'INFO',
            'CLEANUP_ENABLED': 'true',
            'FILE_RETENTION_HOURS': '24',
            'MAX_CONCURRENT_TASKS': '2',
            'TASK_TIMEOUT_SECONDS': '600'
        }
        
        for key, value in env_vars.items():
            os.environ.setdefault(key, value)
        
        # Ensure required secrets are set
        required_secrets = ['SESSION_SECRET']
        missing_secrets = [
            secret for secret in required_secrets 
            if not os.environ.get(secret)
        ]
        
        if missing_secrets:
            logger.error(f"Missing required environment variables: {missing_secrets}")
            logger.error("Please set these variables before starting production server")
            return False
        
        logger.info("Production environment configured")
        return True
    
    def start_redis(self):
        """Start Redis server with production configuration"""
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
        except:
            pass
        
        logger.info("Starting Redis server...")
        try:
            self.processes['redis'] = subprocess.Popen([
                'redis-server',
                '--daemonize', 'no',
                '--port', '6379',
                '--bind', '127.0.0.1',
                '--maxmemory', '512mb',
                '--maxmemory-policy', 'allkeys-lru',
                '--save', '900 1',
                '--stop-writes-on-bgsave-error', 'no',
                '--rdbcompression', 'yes',
                '--dbfilename', 'glb_optimizer.rdb'
            ])
            
            time.sleep(3)
            
            # Verify Redis is running
            result = subprocess.run(
                ['redis-cli', 'ping'], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            if result.returncode == 0:
                logger.info("Redis server started successfully")
                return True
            else:
                logger.error("Redis server failed to start properly")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start Redis: {e}")
            return False
    
    def start_celery_worker(self):
        """Start Celery worker with production settings"""
        logger.info("Starting Celery worker...")
        try:
            self.processes['celery_worker'] = subprocess.Popen([
                'celery', '-A', 'tasks', 'worker',
                '--loglevel=info',
                '--concurrency=2',
                '--pool=prefork',
                '--queues=optimization,cleanup',
                '--max-tasks-per-child=50',
                '--task-events',
                '--time-limit=600',
                '--soft-time-limit=540'
            ])
            
            time.sleep(5)
            
            if self.processes['celery_worker'].poll() is None:
                logger.info("Celery worker started successfully")
                return True
            else:
                logger.error("Celery worker failed to start")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start Celery worker: {e}")
            return False
    
    def start_celery_beat(self):
        """Start Celery beat for scheduled tasks"""
        logger.info("Starting Celery beat scheduler...")
        try:
            self.processes['celery_beat'] = subprocess.Popen([
                'celery', '-A', 'tasks', 'beat',
                '--loglevel=info',
                '--schedule=/tmp/celerybeat-schedule',
                '--pidfile=/tmp/celerybeat.pid'
            ])
            
            time.sleep(3)
            
            if self.processes['celery_beat'].poll() is None:
                logger.info("Celery beat started successfully")
                return True
            else:
                logger.error("Celery beat failed to start")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start Celery beat: {e}")
            return False
    
    def initialize_database(self):
        """Initialize database for production"""
        try:
            from database import init_database
            init_database()
            logger.info("Database initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            return False
    
    def health_check(self):
        """Perform health check on all services"""
        health_status = {}
        
        # Check Redis
        try:
            result = subprocess.run(
                ['redis-cli', 'ping'], 
                capture_output=True, 
                text=True, 
                timeout=2
            )
            health_status['redis'] = result.returncode == 0
        except:
            health_status['redis'] = False
        
        # Check Celery worker
        health_status['celery_worker'] = (
            'celery_worker' in self.processes and 
            self.processes['celery_worker'].poll() is None
        )
        
        # Check Celery beat
        health_status['celery_beat'] = (
            'celery_beat' in self.processes and 
            self.processes['celery_beat'].poll() is None
        )
        
        return health_status
    
    def start_gunicorn(self):
        """Start Gunicorn WSGI server"""
        logger.info("Starting Gunicorn WSGI server...")
        
        # Health check before starting
        health = self.health_check()
        failed_services = [service for service, status in health.items() if not status]
        
        if failed_services:
            logger.warning(f"Some services are not healthy: {failed_services}")
            logger.warning("Starting Gunicorn anyway, but functionality may be limited")
        
        try:
            # Log final status
            logger.info("=" * 50)
            logger.info("GLB Optimizer Production Server Ready")
            logger.info("Application URL: http://0.0.0.0:5000")
            logger.info("Health Status: " + json.dumps(health, indent=2))
            logger.info("=" * 50)
            
            # Use exec to replace current process with Gunicorn
            os.execvp('gunicorn', [
                'gunicorn',
                '--bind', '0.0.0.0:5000',
                '--workers', '3',
                '--worker-class', 'sync',
                '--worker-connections', '1000',
                '--timeout', '120',
                '--keepalive', '5',
                '--max-requests', '1000',
                '--max-requests-jitter', '100',
                '--preload',
                '--access-logfile', 'access.log',
                '--error-logfile', 'error.log',
                '--log-level', 'info',
                '--capture-output',
                'main:app'
            ])
        except Exception as e:
            logger.error(f"Failed to start Gunicorn: {e}")
            return False
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True
        self.shutdown()
        sys.exit(0)
    
    def shutdown(self):
        """Gracefully shutdown all services"""
        if self.shutdown_requested:
            return
        
        self.shutdown_requested = True
        logger.info("Initiating production server shutdown...")
        
        # Shutdown order: Gunicorn (handled by signal), Celery beat, Celery worker, Redis
        shutdown_order = ['celery_beat', 'celery_worker', 'redis']
        
        for service_name in shutdown_order:
            if service_name in self.processes:
                process = self.processes[service_name]
                if process.poll() is None:
                    logger.info(f"Stopping {service_name}...")
                    try:
                        process.terminate()
                        process.wait(timeout=15)
                        logger.info(f"{service_name} stopped gracefully")
                    except subprocess.TimeoutExpired:
                        logger.warning(f"Force killing {service_name}...")
                        process.kill()
                        process.wait()
        
        logger.info("Production server shutdown complete")
    
    def run(self):
        """Main production server entry point"""
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        logger.info("Starting GLB Optimizer Production Server...")
        
        # Setup environment
        if not self.setup_environment():
            sys.exit(1)
        
        # Initialize database
        if not self.initialize_database():
            logger.error("Database initialization failed, exiting...")
            sys.exit(1)
        
        # Start services in dependency order
        services = [
            ('Redis', self.start_redis),
            ('Celery Worker', self.start_celery_worker),
            ('Celery Beat', self.start_celery_beat)
        ]
        
        for service_name, start_func in services:
            if not start_func():
                logger.error(f"Failed to start {service_name}, exiting...")
                self.shutdown()
                sys.exit(1)
        
        # Start Gunicorn (this will replace the current process)
        self.start_gunicorn()

def main():
    """Production server main entry point"""
    # Verify we're in production mode
    if os.environ.get('FLASK_ENV') == 'development':
        print("Warning: Starting production server in development environment")
        print("Consider using develop.py for development work")
        
    server = ProductionServer()
    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        server.shutdown()
    except Exception as e:
        logger.error(f"Production server error: {e}")
        server.shutdown()
        sys.exit(1)

if __name__ == '__main__':
    main()