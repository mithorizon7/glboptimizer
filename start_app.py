#!/usr/bin/env python3
"""
Simple Flask application starter
Direct Flask development server with proper environment setup
"""

import os
import subprocess
import time

# Set all environment variables before any imports
os.environ['REDIS_URL'] = 'redis://localhost:6379/0'
os.environ['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
os.environ['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'
os.environ['FLASK_SECRET_KEY'] = 'dev_secret_key_change_in_production'
os.environ['SESSION_SECRET'] = 'dev_secret_key_change_in_production'

def start_services():
    """Start Redis and Celery services"""
    try:
        # Start Redis
        subprocess.run(['redis-server', '--daemonize', 'yes', '--port', '6379'], check=False)
        time.sleep(2)
        
        # Start Celery worker
        subprocess.Popen(['celery', '-A', 'celery_app.celery', 'worker', '--loglevel=info', '--detach'], 
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        
        print("Services started successfully")
    except Exception as e:
        print(f"Service startup warning: {e}")

if __name__ == '__main__':
    print("🚀 Starting GLB Optimizer Application")
    print("=" * 40)
    
    # Start background services
    start_services()
    
    # Import and run Flask app
    from main import app
    
    print("Flask development server starting...")
    print("Application available at: http://0.0.0.0:5000")
    print("=" * 40)
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)