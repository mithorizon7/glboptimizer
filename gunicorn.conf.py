# Production Gunicorn Configuration for GLB Optimizer
# Security-hardened settings for production deployment

import os
import multiprocessing

# Server socket - robust binding for Replit deployment
host = os.environ.get('HOST', '0.0.0.0')
port = os.environ.get('PORT', '5000')
bind = f"{host}:{port}"
backlog = 2048

# Worker processes
workers = int(os.environ.get('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"
worker_connections = 1000
timeout = 300  # 5 minutes for GLB processing
keepalive = 2

# Security
# Restart workers periodically to prevent memory leaks
max_requests = 1000
max_requests_jitter = 50

# Limit request line/header sizes to prevent attacks
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

# SSL (if terminating SSL at Gunicorn level)
keyfile = os.environ.get('SSL_KEY_PATH')
certfile = os.environ.get('SSL_CERT_PATH')

# Process naming
proc_name = 'glb-optimizer'

# User/group removed for Replit compatibility
# user = os.environ.get('GUNICORN_USER', 'www-data')  
# group = os.environ.get('GUNICORN_GROUP', 'www-data')

# Logging
accesslog = os.environ.get('GUNICORN_ACCESS_LOG', 'access.log')
errorlog = os.environ.get('GUNICORN_ERROR_LOG', 'error.log')
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Security headers (in addition to application-level headers)
def when_ready(server):
    server.log.info("GLB Optimizer server is ready for production")

def worker_int(worker):
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

# Environment variables validation
def on_starting(server):
    """Initialize database in the master process before forking."""
    server.log.info("Initializing services in Gunicorn master process...")
    os.environ['GUNICORN_PROCESS'] = 'master'

    try:
        from database import init_database
        init_database()
        server.log.info("Database initialized successfully.")
    except Exception as e:
        server.log.error(f"Failed to initialize database in Gunicorn: {e}")
        # Exit if the database can't be reached.
        import sys
        sys.exit(1)