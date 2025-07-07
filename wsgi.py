#!/usr/bin/env python3
"""
WSGI Entry Point for GLB Optimizer
Clean entry point for production deployment with gunicorn
"""

import os
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Set critical environment variables for Celery and Redis
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/0')
os.environ.setdefault('CELERY_BROKER_URL', 'redis://localhost:6379/0')
os.environ.setdefault('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# Import the Flask application
from app import app

# This is the WSGI application object that gunicorn will use
application = app

if __name__ == "__main__":
    # Only run in development mode
    app.run(host='0.0.0.0', port=5000, debug=True)