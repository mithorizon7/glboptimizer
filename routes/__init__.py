"""
Routes package for GLB Optimizer.

This package contains route blueprints for organizing the application:
- web: User-facing HTML pages
- api: REST API endpoints (when fully extracted)

Currently, most routes remain in app.py using the main_routes blueprint.
This package provides a structure for future modularization.
"""

from routes.web import web_bp

__all__ = ['web_bp']
