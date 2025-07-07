#!/usr/bin/env python3
"""
Automated file cleanup scheduler for GLB Optimizer
Removes old files from uploads and output directories
"""

import os
import time
import logging
from datetime import datetime, timedelta
from celery_app import celery
from celery.schedules import crontab

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
OUTPUT_FOLDER = os.environ.get('OUTPUT_FOLDER', 'output')
FILE_RETENTION_HOURS = int(os.environ.get('FILE_RETENTION_HOURS', '24'))

@celery.task(name='cleanup.cleanup_old_files')
def cleanup_old_files():
    """
    Celery task to clean up old files from upload and output directories
    Runs periodically to prevent server storage from filling up
    """
    try:
        cutoff_time = time.time() - (FILE_RETENTION_HOURS * 3600)
        total_deleted = 0
        total_size_freed = 0
        
        # Clean up both directories
        for folder_name, folder_path in [('uploads', UPLOAD_FOLDER), ('output', OUTPUT_FOLDER)]:
            if not os.path.exists(folder_path):
                logger.info(f"Directory {folder_path} does not exist, skipping")
                continue
                
            deleted_count = 0
            size_freed = 0
            
            for filename in os.listdir(folder_path):
                file_path = os.path.join(folder_path, filename)
                
                # Skip directories and hidden files
                if not os.path.isfile(file_path) or filename.startswith('.'):
                    continue
                
                try:
                    # Check file age
                    file_mtime = os.path.getmtime(file_path)
                    if file_mtime < cutoff_time:
                        # Get file size before deletion
                        file_size = os.path.getsize(file_path)
                        
                        # Delete the file
                        os.remove(file_path)
                        
                        deleted_count += 1
                        size_freed += file_size
                        
                        # Log individual file deletion for debugging
                        age_hours = (time.time() - file_mtime) / 3600
                        logger.debug(f"Deleted {file_path} (age: {age_hours:.1f}h, size: {file_size} bytes)")
                        
                except OSError as e:
                    logger.warning(f"Could not delete {file_path}: {e}")
                    continue
            
            total_deleted += deleted_count
            total_size_freed += size_freed
            
            logger.info(f"Cleaned {folder_name}: {deleted_count} files deleted, {size_freed / 1024 / 1024:.2f} MB freed")
        
        # Log summary
        logger.info(f"Cleanup completed: {total_deleted} total files deleted, "
                   f"{total_size_freed / 1024 / 1024:.2f} MB total space freed")
        
        return {
            'success': True,
            'files_deleted': total_deleted,
            'space_freed_mb': round(total_size_freed / 1024 / 1024, 2),
            'retention_hours': FILE_RETENTION_HOURS,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cleanup task failed: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

@celery.task(name='cleanup.cleanup_orphaned_tasks')
def cleanup_orphaned_tasks():
    """
    Clean up Celery task results and Redis data for completed tasks
    """
    try:
        # Get all task IDs from Redis
        redis_client = celery.backend.client
        task_keys = redis_client.keys('celery-task-meta-*')
        
        cleaned_count = 0
        cutoff_time = time.time() - (FILE_RETENTION_HOURS * 3600)
        
        for key in task_keys:
            try:
                # Get task data
                task_data = redis_client.get(key)
                if not task_data:
                    continue
                
                # Check if task is old enough to clean
                task_id = key.decode('utf-8').replace('celery-task-meta-', '')
                result = celery.AsyncResult(task_id)
                
                # Clean up completed or failed tasks older than retention period
                if result.state in ['SUCCESS', 'FAILURE']:
                    # Delete the task result
                    redis_client.delete(key)
                    cleaned_count += 1
                    
            except Exception as e:
                logger.warning(f"Could not process task {key}: {e}")
                continue
        
        logger.info(f"Cleaned up {cleaned_count} orphaned task results")
        
        return {
            'success': True,
            'tasks_cleaned': cleaned_count,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Task cleanup failed: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

def manual_cleanup():
    """
    Manual cleanup function for testing or emergency use
    """
    print("Starting manual cleanup...")
    
    # Run file cleanup
    file_result = cleanup_old_files()
    print(f"File cleanup result: {file_result}")
    
    # Run task cleanup
    task_result = cleanup_orphaned_tasks()
    print(f"Task cleanup result: {task_result}")
    
    return file_result, task_result

if __name__ == "__main__":
    # Allow running cleanup manually for testing
    manual_cleanup()