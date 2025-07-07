#!/bin/bash

# GLB Optimizer Production Startup Script
# This script ensures all dependencies are running and environment is configured

echo "🚀 Starting GLB Optimizer Production Environment"
echo "=================================================="

# Set environment variables
export REDIS_URL=redis://localhost:6379/0
export CELERY_BROKER_URL=redis://localhost:6379/0
export CELERY_RESULT_BACKEND=redis://localhost:6379/0
export FLASK_SECRET_KEY=dev_secret_key_change_in_production
export FLASK_ENV=production
export FLASK_DEBUG=false

echo "✅ Environment variables configured"

# Start Redis server
echo "🔄 Starting Redis server..."
redis-server --daemonize yes --port 6379 --bind 127.0.0.1 2>/dev/null || true
sleep 2

# Verify Redis is running
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis server running"
else
    echo "⚠️  Redis server not responding, continuing without task queue"
fi

# Start Celery worker in background
echo "🔄 Starting Celery worker..."
celery -A celery_app.celery worker --loglevel=info --concurrency=1 --detach 2>/dev/null || {
    echo "⚠️  Celery worker failed to start, continuing without background processing"
}

# Start the Flask application
echo "🔄 Starting Flask application..."
echo "=================================================="
exec gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app