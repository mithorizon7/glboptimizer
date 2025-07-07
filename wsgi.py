#!/usr/bin/env python3
"""
Simple WSGI entry point for deployment.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set basic environment variables
os.environ.setdefault('SESSION_SECRET', 'production_secret_change_me')
os.environ.setdefault('FLASK_ENV', 'production')

# Simple Flask app import
try:
    # Try to import from main.py factory
    from main import create_app
    application = create_app()
except ImportError:
    # Fallback to direct Flask app
    from flask import Flask, render_template, request, jsonify
    application = Flask(__name__)
    application.secret_key = os.environ.get("SESSION_SECRET", "fallback_secret")
    
    @application.route('/')
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
    
    @application.route('/health')
    def health():
        return jsonify({'status': 'ok', 'message': 'Basic service is running'})

if __name__ == "__main__":
    application.run(host='0.0.0.0', port=5000, debug=False)