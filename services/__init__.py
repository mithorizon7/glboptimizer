"""
Services package for GLB Optimizer.

Contains business logic and external integrations.
"""

from services.realtime import init_socketio, emit_task_progress, emit_task_complete, emit_task_error

__all__ = [
    'init_socketio',
    'emit_task_progress',
    'emit_task_complete',
    'emit_task_error',
]
