"""
Real-time WebSocket service for progress updates.

Uses Flask-SocketIO to push task progress updates to connected clients,
replacing the previous polling approach for better performance and UX.
"""

import logging
from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room

logger = logging.getLogger(__name__)

# Global SocketIO instance - initialized by init_socketio()
socketio = None


def init_socketio(app):
    """
    Initialize Flask-SocketIO with the Flask app.
    
    Args:
        app: Flask application instance
        
    Returns:
        SocketIO instance
    """
    global socketio
    
    # Create SocketIO with async_mode based on environment
    # Use 'threading' for development, 'eventlet' or 'gevent' for production
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode='threading',  # Works without additional dependencies
        logger=True,
        engineio_logger=True
    )
    
    # Register event handlers
    @socketio.on('connect')
    def handle_connect():
        logger.info(f"Client connected: {request.sid}")
    
    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info(f"Client disconnected: {request.sid}")
    
    @socketio.on('subscribe_task')
    def handle_subscribe(data):
        """Subscribe to updates for a specific task"""
        task_id = data.get('task_id')
        if task_id:
            join_room(task_id)
            logger.info(f"Client {request.sid} subscribed to task {task_id}")
            emit('subscribed', {'task_id': task_id, 'status': 'connected'})
    
    @socketio.on('unsubscribe_task')
    def handle_unsubscribe(data):
        """Unsubscribe from task updates"""
        task_id = data.get('task_id')
        if task_id:
            leave_room(task_id)
            logger.info(f"Client {request.sid} unsubscribed from task {task_id}")
    
    # Register batch handlers
    register_batch_handlers(socketio)
    
    logger.info("Flask-SocketIO initialized successfully")
    return socketio


def emit_task_progress(task_id: str, progress: int, step: str, message: str, status: str = 'processing'):
    """
    Emit task progress update to all subscribed clients.
    
    Args:
        task_id: The Celery task ID
        progress: Progress percentage (0-100)
        step: Current step name
        message: Human-readable status message
        status: Task status (processing, completed, error)
    """
    global socketio
    
    if socketio is None:
        logger.warning("SocketIO not initialized - cannot emit progress")
        return
    
    payload = {
        'task_id': task_id,
        'progress': progress,
        'step': step,
        'message': message,
        'status': status
    }
    
    # Emit to the task-specific room
    socketio.emit('task_progress', payload, room=task_id)
    logger.debug(f"Emitted progress for task {task_id}: {progress}%")


def emit_task_complete(task_id: str, result: dict):
    """
    Emit task completion to all subscribed clients.
    
    Args:
        task_id: The Celery task ID
        result: The optimization result dictionary
    """
    global socketio
    
    if socketio is None:
        logger.warning("SocketIO not initialized - cannot emit completion")
        return
    
    payload = {
        'task_id': task_id,
        'status': 'completed',
        **result
    }
    
    socketio.emit('task_complete', payload, room=task_id)
    logger.info(f"Emitted completion for task {task_id}")


def emit_task_error(task_id: str, error: str, category: str = 'Unknown Error', details: str = None):
    """
    Emit task error to all subscribed clients.
    
    Args:
        task_id: The Celery task ID
        error: Error message
        category: Error category
        details: Technical error details
    """
    global socketio
    
    if socketio is None:
        logger.warning("SocketIO not initialized - cannot emit error")
        return
    
    payload = {
        'task_id': task_id,
        'status': 'error',
        'error': error,
        'category': category,
        'details': details
    }
    
    socketio.emit('task_error', payload, room=task_id)
    logger.info(f"Emitted error for task {task_id}: {error}")


def get_socketio():
    """Get the current SocketIO instance"""
    return socketio


# ============ Batch WebSocket Functions ============

def emit_batch_progress(batch_id: str, completed: int, total: int, current_task: dict = None):
    """
    Emit batch progress update to all subscribed clients.
    
    Args:
        batch_id: The batch UUID
        completed: Number of completed tasks
        total: Total number of tasks
        current_task: Optional dict with current task info
    """
    global socketio
    
    if socketio is None:
        return
    
    payload = {
        'batch_id': batch_id,
        'completed': completed,
        'total': total,
        'progress_percent': (completed / total * 100) if total > 0 else 0,
        'current_task': current_task
    }
    
    # Emit to batch-specific room (prefixed to avoid collision with task rooms)
    socketio.emit('batch_progress', payload, room=f'batch_{batch_id}')
    logger.debug(f"Emitted batch progress: {completed}/{total}")


def emit_batch_complete(batch_id: str, summary: dict):
    """
    Emit batch completion to all subscribed clients.
    
    Args:
        batch_id: The batch UUID
        summary: Summary dict with totals
    """
    global socketio
    
    if socketio is None:
        return
    
    payload = {
        'batch_id': batch_id,
        'status': 'completed',
        **summary
    }
    
    socketio.emit('batch_complete', payload, room=f'batch_{batch_id}')
    logger.info(f"Emitted batch completion for {batch_id}")


def register_batch_handlers(socketio_instance):
    """Register batch-specific WebSocket event handlers"""
    
    @socketio_instance.on('subscribe_batch')
    def handle_batch_subscribe(data):
        """Subscribe to updates for a batch"""
        batch_id = data.get('batch_id')
        if batch_id:
            join_room(f'batch_{batch_id}')
            logger.info(f"Client {request.sid} subscribed to batch {batch_id}")
            emit('batch_subscribed', {'batch_id': batch_id, 'status': 'connected'})
    
    @socketio_instance.on('unsubscribe_batch')
    def handle_batch_unsubscribe(data):
        """Unsubscribe from batch updates"""
        batch_id = data.get('batch_id')
        if batch_id:
            leave_room(f'batch_{batch_id}')
            logger.info(f"Client {request.sid} unsubscribed from batch {batch_id}")
