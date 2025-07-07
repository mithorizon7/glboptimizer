#!/usr/bin/env python3
"""
WSGI entry point for production deployment.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set production environment variables
os.environ.setdefault('SESSION_SECRET', 'production_secret_change_me')
os.environ.setdefault('FLASK_ENV', 'production')
os.environ.setdefault('DATABASE_URL', os.environ.get('DATABASE_URL', 'sqlite:///production.db'))
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/0')
os.environ.setdefault('CELERY_BROKER_URL', 'redis://localhost:6379/0')
os.environ.setdefault('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

def create_application():
    """Create and configure the Flask application for production"""
    try:
        from config import get_config
        from flask import Flask
        from werkzeug.middleware.proxy_fix import ProxyFix
        
        # Create Flask app
        app = Flask(__name__)
        
        # Load configuration
        config = get_config()
        app.secret_key = config.SECRET_KEY
        app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH
        
        # Apply middleware for reverse proxy
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
        
        # Initialize database
        try:
            from database import init_database
            init_database()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
        
        # Import and register routes
        from app import main_routes, add_security_headers
        app.register_blueprint(main_routes)
        app.after_request(add_security_headers)
        
        logger.info("Flask application created successfully")
        return app
        
    except Exception as e:
        logger.error(f"Failed to create application: {e}")
        # Create minimal fallback app
        from flask import Flask, jsonify
        app = Flask(__name__)
        app.secret_key = os.environ.get("SESSION_SECRET", "fallback_secret")
        
        @app.route('/')
        def index():
            return """
            <!DOCTYPE html>
            <html>
            <head><title>GLB Optimizer</title></head>
            <body>
                <h1>GLB Optimizer</h1>
                <p>Service is starting up. Please wait a moment and refresh.</p>
            </body>
            </html>
            """
        
        @app.route('/health')
        def health():
            return jsonify({'status': 'degraded', 'message': 'Service running in fallback mode'})
            
        return app

# Create the application instance
application = create_application()

if __name__ == "__main__":
    application.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == "__main__":
    application.run(host='0.0.0.0', port=5000, debug=False)