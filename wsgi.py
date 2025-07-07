#!/usr/bin/env python3
"""
Production WSGI entry point for Gunicorn.
This file creates the Flask application object using the factory pattern.
"""

import os
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Set critical environment variables for Celery and Redis
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/0')
os.environ.setdefault('CELERY_BROKER_URL', 'redis://localhost:6379/0')
os.environ.setdefault('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# Import the application factory
from main import create_app

# Gunicorn will look for this 'application' object by default.
application = create_app()

if __name__ == "__main__":
    # Only run in development mode
    application.run(host='0.0.0.0', port=5000, debug=True)