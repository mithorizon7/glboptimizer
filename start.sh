#!/bin/bash

# Kill any existing Redis or Python processes
pkill redis-server 2>/dev/null || true
pkill gunicorn 2>/dev/null || true

echo "Starting Redis server in background..."
# Start Redis server in background
redis-server --daemonize yes --port 6379 --bind 127.0.0.1 --save "" --appendonly no --protected-mode no

# Wait a moment for Redis to start
sleep 2

# Check if Redis is running
if redis-cli ping >/dev/null 2>&1; then
    echo "✅ Redis server started successfully"
else
    echo "⚠️ Redis failed to start - using database fallback"
fi

echo "Starting GLB Optimizer web application..."
# Start the main application
uv pip sync pyproject.toml && gunicorn --bind 0.0.0.0:5000 --reuse-port --reload wsgi:application