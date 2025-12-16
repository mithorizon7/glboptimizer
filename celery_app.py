"""
Celery Application Module
========================
Backward compatibility wrapper for celery_factory.

All imports should work as before:
    from celery_app import celery
    from celery_app import make_celery

This module re-exports everything from celery_factory to maintain
backward compatibility with existing code.
"""

from celery_factory import (
    celery,
    make_celery,
    get_celery,
    get_broker_type,
    broker_type,
    check_redis_availability,
    get_broker_config
)

__all__ = [
    'celery',
    'make_celery', 
    'get_celery',
    'get_broker_type',
    'broker_type',
    'check_redis_availability',
    'get_broker_config'
]
