import os
import time
import logging
from datetime import datetime, timezone
from celery_factory import celery
from optimizer import GLBOptimizer
from database import db_session
from models import OptimizationTask, PerformanceMetric

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if celery is None:
    logger.warning("Celery unavailable - tasks will execute synchronously")
    
    class DummyCeleryTask:
        """Dummy Celery task decorator for synchronous fallback"""
        def task(self, *args, **kwargs):
            def decorator(func):
                # Execute synchronously when called via .delay() or .apply_async()
                func.delay = func  # Direct call instead of queueing
                func.apply_async = lambda args=None, kwargs=None, **_: func(*(args or ()), **(kwargs or {}))
                return func
            return decorator
    
    celery = DummyCeleryTask()

@celery.task(bind=True, name='tasks.optimize_glb_file')
def optimize_glb_file(self, input_path, output_path, original_name, quality_level='high', enable_lod=True, enable_simplification=True):
    """
    Celery task for optimizing GLB files
    
    Args:
        input_path: Path to the input GLB file
        output_path: Path where optimized file should be saved
        original_name: Original filename without extension
        quality_level: Optimization quality level
        enable_lod: Whether to enable LOD generation
        enable_simplification: Whether to enable polygon simplification
    
    Returns:
        dict: Result containing success status, file sizes, and processing time
    """
    
    def progress_callback(step, progress, message):
        """Update task progress"""
        self.update_state(
            state='PROGRESS',
            meta={
                'step': step,
                'progress': progress,
                'message': message,
                'status': 'processing'
            }
        )
        logger.info(f"Task {self.request.id}: {step} - {progress}% - {message}")
        
        # Emit real-time WebSocket update
        try:
            from services.realtime import emit_task_progress
            emit_task_progress(self.request.id, progress, step, message)
        except Exception as ws_error:
            logger.debug(f"WebSocket emit failed (non-critical): {ws_error}")
        
        # Update database record using ORM
        try:
            with db_session() as db:
                task = db.query(OptimizationTask).filter(
                    OptimizationTask.id == self.request.id
                ).first()
                
                if task:
                    task.status = 'processing' if progress < 100 else 'completed'
                    task.progress = progress
                    task.current_step = step
                    if progress == 100:
                        task.completed_at = datetime.now(timezone.utc)
                    db.commit()
        except Exception as e:
            logger.error(f"Failed to update database progress: {e}")
    
    try:
        logger.info(f"Starting optimization task {self.request.id} for file: {original_name}")
        
        # Update initial state
        self.update_state(
            state='PROGRESS',
            meta={
                'step': 'Starting optimization...',
                'progress': 0,
                'message': 'Initializing optimization pipeline',
                'status': 'starting'
            }
        )
        
        # Create optimizer instance
        optimizer = GLBOptimizer(quality_level=quality_level)
        
        # Get original file size
        original_size = os.path.getsize(input_path)
        
        # Run optimization
        start_time = time.time()
        result = optimizer.optimize(input_path, output_path, progress_callback)
        processing_time = time.time() - start_time
        
        if result['success']:
            # Get optimized file size
            optimized_size = os.path.getsize(output_path)
            compression_ratio = ((original_size - optimized_size) / original_size) * 100
            
            logger.info(f"Optimization completed for task {self.request.id}")
            
            # Update database with completion results using ORM
            try:
                with db_session() as db:
                    task = db.query(OptimizationTask).filter(
                        OptimizationTask.id == self.request.id
                    ).first()
                    
                    if task:
                        task.status = 'completed'
                        task.progress = 100
                        task.compressed_size = optimized_size
                        task.compression_ratio = compression_ratio
                        task.processing_time = processing_time
                        task.completed_at = datetime.now(timezone.utc)
                        db.commit()
                        logger.info(f"Database updated for completed task {self.request.id}")
            except Exception as e:
                logger.error(f"Failed to update database with completion results: {e}")
            
            # Emit WebSocket completion event
            try:
                from services.realtime import emit_task_complete
                emit_task_complete(self.request.id, {
                    'original_size': original_size,
                    'optimized_size': optimized_size,
                    'compression_ratio': compression_ratio,
                    'processing_time': processing_time
                })
            except Exception as ws_error:
                logger.debug(f"WebSocket emit failed (non-critical): {ws_error}")
            
            # Collect detailed metrics for audit report
            audit_report = None
            try:
                from optimizer.metrics import collect_glb_metrics, compare_metrics
                before_metrics = collect_glb_metrics(input_path)
                after_metrics = collect_glb_metrics(output_path)
                audit_report = compare_metrics(before_metrics, after_metrics)
                logger.info(f"Collected audit report for task {self.request.id}")
            except Exception as metrics_error:
                logger.warning(f"Failed to collect audit metrics: {metrics_error}")
            
            return {
                'status': 'completed',
                'success': True,
                'original_size': original_size,
                'optimized_size': optimized_size,
                'compression_ratio': compression_ratio,
                'processing_time': processing_time,
                'output_file': os.path.basename(output_path),
                'original_name': original_name,
                'performance_metrics': result.get('performance_metrics'),
                'estimated_memory_savings': result.get('estimated_memory_savings'),
                'audit_report': audit_report
            }
        else:
            logger.error(f"Optimization failed for task {self.request.id}: {result.get('error')}")
            
            # Get detailed error information from optimizer
            detailed_logs = optimizer.get_detailed_logs()
            
            # Prepare enhanced error response
            error_response = {
                'status': 'error',
                'success': False,
                'error': result.get('error', 'Unknown error occurred'),
                'user_message': result.get('user_message', result.get('error', 'Optimization failed')),
                'category': result.get('category', 'Unknown Error'),
                'detailed_error': detailed_logs,
                'original_name': original_name
            }
            
            # Update task state with detailed error
            self.update_state(
                state='FAILURE',
                meta=error_response
            )
            
            return error_response
    
    except Exception as e:
        logger.error(f"Task {self.request.id} failed with exception: {str(e)}")
        
        # Update task state to failure
        self.update_state(
            state='FAILURE',
            meta={
                'status': 'error',
                'error': str(e),
                'original_name': original_name
            }
        )
        
        # Re-raise the exception for Celery to handle
        raise
    
    finally:
        # Don't clean up input file immediately - keep it for 3D viewer comparison
        # It will be cleaned up when the user downloads or the task is manually cleaned up
        logger.info(f"Task completed, keeping original file for comparison: {input_path}")