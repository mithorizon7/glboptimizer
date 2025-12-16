#!/usr/bin/env python3
"""
Main Entry Point for GLB Optimizer
==================================
Simple entry point for the Flask application.

For development: python main.py
For production: gunicorn --bind 0.0.0.0:5000 wsgi:application

Note: Celery workers should be started separately using:
    celery -A celery_factory worker --loglevel=info
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    """Create and configure the Flask application"""
    from wsgi import create_app as wsgi_create_app
    return wsgi_create_app()


if __name__ == '__main__':
    logger.info("Starting GLB Optimizer in development mode...")
    
    try:
        from database import init_database
        init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
    
    app = create_app()
    
    logger.info("Starting Flask development server on port 5000...")
    app.run(host='0.0.0.0', port=5000, debug=True)
