import os
import time
import logging
from celery import current_task
from celery_app import celery
from optimizer import GLBOptimizer

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
        current_task.update_state(
            state='PROGRESS',
            meta={
                'step': step,
                'progress': progress,
                'message': message,
                'status': 'processing'
            }
        )
        logger.info(f"Task {current_task.request.id}: {step} - {progress}% - {message}")
    
    try:
        logger.info(f"Starting optimization task {current_task.request.id} for file: {original_name}")
        
        # Update initial state
        current_task.update_state(
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
            
            logger.info(f"Optimization completed for task {current_task.request.id}")
            
            return {
                'status': 'completed',
                'success': True,
                'original_size': original_size,
                'optimized_size': optimized_size,
                'compression_ratio': compression_ratio,
                'processing_time': processing_time,
                'output_file': os.path.basename(output_path),
                'original_name': original_name
            }
        else:
            logger.error(f"Optimization failed for task {current_task.request.id}: {result.get('error')}")
            return {
                'status': 'error',
                'success': False,
                'error': result.get('error', 'Unknown error occurred'),
                'original_name': original_name
            }
    
    except Exception as e:
        logger.error(f"Task {current_task.request.id} failed with exception: {str(e)}")
        
        # Update task state to failure
        current_task.update_state(
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
        # Clean up input file
        try:
            if os.path.exists(input_path):
                os.remove(input_path)
                logger.info(f"Cleaned up input file: {input_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up input file {input_path}: {str(e)}")