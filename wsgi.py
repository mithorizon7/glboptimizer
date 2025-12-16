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

# Set production environment variables - no defaults here, Config is the source of truth
os.environ.setdefault('FLASK_ENV', 'production')

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
        
        # Import the app factory and create app
        from app import create_app
        app = create_app()
        
        logger.info("Flask application created successfully")
        return app
        
    except Exception as e:
        logger.error(f"Failed to create application: {e}")
        # Create minimal fallback app
        from flask import Flask, jsonify
        from config import Config
        app = Flask(__name__)
        app.secret_key = Config.SECRET_KEY
        
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
    from config import Config
    application.run(host=Config.HOST, port=Config.PORT, debug=False)