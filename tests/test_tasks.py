# tests/test_tasks.py
"""
Unit tests for Celery tasks
Tests background task execution in isolation
"""
import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from tasks import optimize_glb_file
from models import OptimizationTask

class TestOptimizeGLBFileTask:
    """Test suite for the optimize_glb_file Celery task"""
    
    @patch('tasks.GLBOptimizer')
    @patch('tasks.SessionLocal')
    def test_optimize_glb_file_success(self, mock_session, mock_optimizer_class, sample_glb_file):
        """Test successful GLB file optimization"""
        # Setup mocks
        mock_optimizer = MagicMock()
        mock_optimizer_class.return_value = mock_optimizer
        mock_optimizer.optimize.return_value = {
            'success': True,
            'original_size': 1000,
            'optimized_size': 400,
            'compression_ratio': 0.6,
            'processing_time': 15.5,
            'performance_metrics': {
                'gpu_memory_savings': 0.7,
                'load_time_improvement': 0.6
            }
        }
        
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        # Mock task record
        mock_task_record = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_task_record
        
        # Create mock task context
        mock_task = MagicMock()
        mock_task.request.id = 'test_task_123'
        
        with tempfile.NamedTemporaryFile(suffix='.glb') as output_file:
            # Write some data to output file to simulate optimization
            output_file.write(b'x' * 400)
            output_file.flush()
            
            # Execute task
            result = optimize_glb_file.__wrapped__(
                mock_task,
                sample_glb_file,
                output_file.name,
                'test_model',
                quality_level='high',
                enable_lod=True,
                enable_simplification=True
            )
        
        # Verify success result
        assert result['success'] is True
        assert result['status'] == 'completed'
        assert 'original_size' in result
        assert 'optimized_size' in result
        assert 'compression_ratio' in result
        
        # Verify optimizer was called correctly
        mock_optimizer.optimize.assert_called_once()
        
        # Verify database was updated
        assert mock_task_record.status == 'completed'
        assert mock_task_record.progress == 100
        assert mock_task_record.compressed_size == 400
    
    @patch('tasks.GLBOptimizer')
    @patch('tasks.SessionLocal')
    def test_optimize_glb_file_optimizer_failure(self, mock_session, mock_optimizer_class):
        """Test GLB file optimization when optimizer fails"""
        # Setup optimizer to fail
        mock_optimizer = MagicMock()
        mock_optimizer_class.return_value = mock_optimizer
        mock_optimizer.optimize.return_value = {
            'success': False,
            'error': 'Invalid GLB format'
        }
        
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        # Mock task record
        mock_task_record = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_task_record
        
        # Create mock task context
        mock_task = MagicMock()
        mock_task.request.id = 'test_task_456'
        
        with tempfile.NamedTemporaryFile(suffix='.glb') as input_file, \
             tempfile.NamedTemporaryFile(suffix='.glb') as output_file:
            
            input_file.write(b'invalid glb data')
            input_file.flush()
            
            # Execute task
            result = optimize_glb_file.__wrapped__(
                mock_task,
                input_file.name,
                output_file.name,
                'invalid_model',
                quality_level='high'
            )
        
        # Verify failure result
        assert result['success'] is False
        assert result['status'] == 'error'
        assert 'Invalid GLB format' in result['error']
        
        # Verify database was updated with error
        assert mock_task_record.status == 'failed'
        assert mock_task_record.error_message == 'Invalid GLB format'
    
    @patch('tasks.GLBOptimizer')
    @patch('tasks.SessionLocal')
    def test_optimize_glb_file_exception_handling(self, mock_session, mock_optimizer_class):
        """Test task handles unexpected exceptions"""
        # Setup optimizer to raise exception
        mock_optimizer = MagicMock()
        mock_optimizer_class.return_value = mock_optimizer
        mock_optimizer.optimize.side_effect = Exception("Unexpected error occurred")
        
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        # Mock task record
        mock_task_record = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_task_record
        
        # Create mock task context
        mock_task = MagicMock()
        mock_task.request.id = 'test_task_789'
        
        with tempfile.NamedTemporaryFile(suffix='.glb') as input_file, \
             tempfile.NamedTemporaryFile(suffix='.glb') as output_file:
            
            input_file.write(b'test data')
            input_file.flush()
            
            # Execute task and expect exception
            with pytest.raises(Exception, match="Unexpected error occurred"):
                optimize_glb_file.__wrapped__(
                    mock_task,
                    input_file.name,
                    output_file.name,
                    'test_model'
                )
        
        # Verify database was updated with error
        assert mock_task_record.status == 'failed'
        assert 'Unexpected error occurred' in mock_task_record.error_message
    
    @patch('tasks.SessionLocal')
    def test_progress_callback_database_update(self, mock_session):
        """Test progress callback updates database correctly"""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        # Create mock task context
        mock_task = MagicMock()
        mock_task.request.id = 'test_progress_task'
        mock_task.update_state = MagicMock()
        
        # Create a real progress callback function
        def progress_callback(step, progress, message):
            mock_task.update_state(
                state='PROGRESS',
                meta={
                    'step': step,
                    'progress': progress,
                    'message': message,
                    'status': 'processing'
                }
            )
        
        # Test progress updates
        test_updates = [
            ('Initialization', 10, 'Starting optimization'),
            ('Pruning', 30, 'Removing unused data'),
            ('Compression', 70, 'Applying geometry compression'),
            ('Finalization', 100, 'Optimization complete')
        ]
        
        for step, progress, message in test_updates:
            progress_callback(step, progress, message)
        
        # Verify all progress updates were called
        assert mock_task.update_state.call_count == len(test_updates)
        
        # Verify final call had correct data
        final_call = mock_task.update_state.call_args_list[-1]
        assert final_call[1]['meta']['progress'] == 100
        assert final_call[1]['meta']['step'] == 'Finalization'
    
    @patch('tasks.os.path.getsize')
    def test_file_size_calculations(self, mock_getsize):
        """Test file size calculations in task"""
        # Mock file sizes
        mock_getsize.side_effect = [1000000, 400000]  # original, compressed
        
        # Mock other dependencies
        with patch('tasks.GLBOptimizer') as mock_optimizer_class, \
             patch('tasks.SessionLocal') as mock_session:
            
            mock_optimizer = MagicMock()
            mock_optimizer_class.return_value = mock_optimizer
            mock_optimizer.optimize.return_value = {'success': True}
            
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_task_record = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_task_record
            
            mock_task = MagicMock()
            mock_task.request.id = 'size_test_task'
            
            with tempfile.NamedTemporaryFile() as input_file, \
                 tempfile.NamedTemporaryFile() as output_file:
                
                result = optimize_glb_file.__wrapped__(
                    mock_task,
                    input_file.name,
                    output_file.name,
                    'size_test_model'
                )
        
        # Verify file size calculations
        expected_ratio = (1000000 - 400000) / 1000000  # 60% compression
        assert abs(mock_task_record.compression_ratio - expected_ratio) < 0.01
        assert mock_task_record.compressed_size == 400000
    
    def test_task_registration(self):
        """Test that task is properly registered with Celery"""
        # Verify task is callable
        assert callable(optimize_glb_file)
        
        # Verify task has expected attributes
        assert hasattr(optimize_glb_file, 'delay')
        assert hasattr(optimize_glb_file, 'apply_async')
        
        # Verify task name
        assert optimize_glb_file.name == 'tasks.optimize_glb_file'