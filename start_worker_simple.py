#!/usr/bin/env python3
"""
Simple Celery worker starter for debugging
"""
import os
import sys

# Add current directory to Python path
sys.path.insert(0, '.')

# Set environment variables
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/0')

# Import and run worker
from celery_app import celery

if __name__ == '__main__':
    # Start worker
    celery.worker_main(['worker', '--loglevel=info', '--concurrency=1'])