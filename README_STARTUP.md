# GLB Optimizer Startup Guide

This document provides clear instructions for running the GLB Optimizer in different environments.

## Quick Start

### Development Mode
```bash
python develop.py
```

### Production Mode  
```bash
python run_production.py
```

## Development Server (`develop.py`)

**Purpose**: Local development with debugging and live reloading

**Features**:
- Flask debug mode with auto-reload
- All service logs visible in same terminal
- Redis auto-start and management
- Celery worker with visible output
- Comprehensive error reporting
- Process cleanup on exit

**Environment**: 
- Debug mode enabled
- File retention: 24 hours
- Cleanup: disabled
- Log level: DEBUG

**URL**: http://localhost:5000

### Usage:
```bash
# Standard development
python develop.py

# The script will:
# 1. Check dependencies (redis-server, celery, etc.)
# 2. Start Redis server
# 3. Initialize database
# 4. Start Celery worker
# 5. Launch Flask development server
```

## Production Server (`run_production.py`)

**Purpose**: Production deployment with optimized performance

**Features**:
- Gunicorn WSGI server (3 workers)
- Redis with production settings
- Celery worker pool (2 processes)
- Celery beat for scheduled cleanup
- Health checks and monitoring
- Graceful shutdown handling
- Comprehensive logging

**Environment**:
- Production mode
- File retention: 24 hours  
- Cleanup: enabled
- Log level: INFO

**URL**: http://0.0.0.0:5000

### Usage:
```bash
# Basic production start
python run_production.py

# With environment variables
SESSION_SECRET=your_secret_key python run_production.py

# The script will:
# 1. Set up production environment
# 2. Initialize database
# 3. Start Redis server
# 4. Start Celery worker and beat
# 5. Launch Gunicorn WSGI server
```

## Required Environment Variables

### Development
All variables have sensible defaults, no configuration required.

### Production
- `SESSION_SECRET`: Required for secure sessions
- `DATABASE_URL`: PostgreSQL connection string (optional, uses default)

### Optional Configuration
- `REDIS_URL`: Redis connection string (default: redis://localhost:6379/0)
- `MAX_CONCURRENT_TASKS`: Number of concurrent optimizations (default: 2)
- `FILE_RETENTION_HOURS`: Hours to keep files (default: 24)
- `CLEANUP_ENABLED`: Enable automatic cleanup (default: true in production)

## Dependencies

### Required System Tools
- `redis-server`: Redis database server
- `redis-cli`: Redis command line client  
- `celery`: Celery task queue
- `gunicorn`: WSGI HTTP server (production only)

### Installation
```bash
# Ubuntu/Debian
sudo apt install redis-server

# Python packages (installed via requirements)
pip install celery gunicorn redis
```

## Service Health Checks

### Development
Check service status in the terminal output:
```
✓ Redis: Running
✓ Database: Running  
✓ Celery: Running
```

### Production
Check logs in `glb_optimizer_production.log`:
```bash
tail -f glb_optimizer_production.log
```

## Process Management

### Development
- Use Ctrl+C to stop all services
- Automatic cleanup on exit
- No background processes remain

### Production  
- Use standard signals (SIGTERM, SIGINT)
- Graceful shutdown with 15-second timeout
- Systemd compatible

### Systemd Service (Production)
```ini
[Unit]
Description=GLB Optimizer Production Server
After=network.target

[Service]
Type=exec
User=glb-optimizer
WorkingDirectory=/path/to/glb-optimizer
Environment=SESSION_SECRET=your_secret_key
ExecStart=/usr/bin/python3 run_production.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Troubleshooting

### Common Issues

**Redis not starting**:
```bash
# Check if Redis is already running
redis-cli ping

# Start manually if needed
redis-server --port 6379
```

**Celery worker not starting**:
```bash
# Test Celery directly
celery -A tasks worker --loglevel=info
```

**Database connection errors**:
```bash
# Check PostgreSQL status
sudo systemctl status postgresql
```

### Logs Location
- Development: Console output
- Production: `glb_optimizer_production.log`, `access.log`, `error.log`

### Performance Monitoring
- Admin dashboard: http://localhost:5000/admin/analytics
- Database stats: http://localhost:5000/admin/stats

## Migration from Old Scripts

**Old scripts removed**:
- `main.py` → Use `develop.py`
- `start_app.py` → Use `develop.py`  
- `startup_fixed.py` → Use `develop.py`
- `start_production.sh` → Use `run_production.py`
- `deploy.py` → Use `run_production.py`

**Migration**:
1. Replace `python main.py` with `python develop.py`
2. Replace production scripts with `python run_production.py`
3. Update any deployment scripts to use the new consolidated approach