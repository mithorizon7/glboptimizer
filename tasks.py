import os
import time
import logging
from datetime import datetime, timezone
from celery_app import celery
from optimizer import GLBOptimizer
from database import SessionLocal
from models import OptimizationTask, PerformanceMetric

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        
        # Update database record (simplified to avoid SQLAlchemy type issues)
        try:
            db = SessionLocal()
            try:
                # Use update() method instead of attribute assignment to avoid type issues
                update_data = {
                    'status': 'processing' if progress < 100 else 'completed',
                    'progress': progress,
                    'current_step': step
                }
                if progress == 100:
                    update_data['completed_at'] = datetime.now(timezone.utc)
                
                db.query(OptimizationTask).filter(OptimizationTask.id == self.request.id).update(update_data)
                db.commit()
            finally:
                db.close()
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
            
            # Update database with completion results (simplified)
            try:
                db = SessionLocal()
                try:
                    # Use direct update to avoid SQLAlchemy type issues
                    update_data = {
                        'status': 'completed',
                        'progress': 100,
                        'compressed_size': optimized_size,
                        'compression_ratio': compression_ratio,
                        'processing_time': processing_time,
                        'completed_at': datetime.now(timezone.utc)
                    }
                    
                    db.query(OptimizationTask).filter(OptimizationTask.id == self.request.id).update(update_data)
                    db.commit()
                    logger.info(f"Database updated for completed task {self.request.id}")
                            
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Failed to update database with completion results: {e}")
            
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
                'estimated_memory_savings': result.get('estimated_memory_savings')
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