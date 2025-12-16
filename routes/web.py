"""
Web routes for the GLB Optimizer application.

Contains user-facing HTML page routes.
"""

from flask import Blueprint, render_template, jsonify
from datetime import datetime, timezone

web_bp = Blueprint('web', __name__)


@web_bp.route('/')
def index():
    """Render the main optimization page"""
    return render_template('index.html')


@web_bp.route('/health')
def health_check():
    """Health check endpoint for Docker and load balancers"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'service': 'glb-optimizer'
    })

