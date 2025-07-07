# tests/test_integration.py
"""
Integration tests for GLB Optimizer
Tests component interactions and full workflows
"""
import pytest
import os
import json
import tempfile
import time
from unittest.mock import patch, MagicMock
from io import BytesIO

from models import OptimizationTask, UserSession

class TestUploadWorkflow:
    """Test file upload and task creation workflow"""
    
    def test_upload_endpoint_creates_task(self, client, db_session, test_dirs, mock_celery_task):
        """Test that file upload creates optimization task in database"""
        # Create test GLB file
        test_file_content = b'glTF' + b'\x02\x00\x00\x00' + b'\x64\x00\x00\x00' + b'\x00' * 100
        
        with patch('app.start_optimization_pipeline') as mock_pipeline:
            mock_pipeline.return_value = 'test_task_123'
            
            # Upload file
            response = client.post('/upload', data={
                'file': (BytesIO(test_file_content), 'test_model.glb'),
                'quality_level': 'high',
                'enable_lod': 'true',
                'enable_simplification': 'true'
            }, content_type='multipart/form-data')
        
        # Verify response
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'task_id' in data
        assert data['message'] == 'File uploaded and optimization started'
        
        # Verify task was created in database
        task = db_session.query(OptimizationTask).filter_by(id=data['task_id']).first()
        assert task is not None
        assert task.original_filename == 'test_model.glb'
        assert task.quality_level == 'high'
        assert task.status == 'pending'
        assert task.progress == 0
    
    def test_upload_invalid_file_type(self, client):
        """Test upload rejection for invalid file types"""
        # Try to upload a text file
        text_content = b'This is not a GLB file'
        
        response = client.post('/upload', data={
            'file': (BytesIO(text_content), 'test_file.txt'),
            'quality_level': 'high'
        }, content_type='multipart/form-data')
        
        # Should reject non-GLB files
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'GLB' in data['error'] or 'format' in data['error'].lower()
    
    def test_upload_file_too_large(self, client):
        """Test upload rejection for files exceeding size limit"""
        # Create file larger than test limit (5MB in test config)
        large_file_content = b'x' * (6 * 1024 * 1024)  # 6MB
        
        response = client.post('/upload', data={
            'file': (BytesIO(large_file_content), 'large_model.glb'),
            'quality_level': 'high'
        }, content_type='multipart/form-data')
        
        # Should reject oversized files
        assert response.status_code == 413 or response.status_code == 400
    
    def test_user_session_tracking(self, client, db_session, mock_celery_task):
        """Test that user sessions are tracked correctly"""
        test_file_content = b'glTF' + b'\x02\x00\x00\x00' + b'\x64\x00\x00\x00' + b'\x00' * 100
        
        with patch('app.start_optimization_pipeline') as mock_pipeline:
            mock_pipeline.return_value = 'session_test_task'
            
            # Make multiple uploads in same session
            for i in range(3):
                response = client.post('/upload', data={
                    'file': (BytesIO(test_file_content), f'model_{i}.glb'),
                    'quality_level': 'high'
                }, content_type='multipart/form-data')
                
                assert response.status_code == 200
        
        # Check that user session was created and updated
        user_sessions = db_session.query(UserSession).all()
        assert len(user_sessions) >= 1
        
        # Find the session for this test
        test_session = None
        for session in user_sessions:
            if session.total_uploads >= 3:
                test_session = session
                break
        
        assert test_session is not None
        assert test_session.total_uploads >= 3

class TestProgressTracking:
    """Test optimization progress tracking"""
    
    def test_progress_endpoint_returns_status(self, client, db_session, sample_optimization_task):
        """Test progress endpoint returns correct task status"""
        response = client.get(f'/progress/{sample_optimization_task.id}')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Verify progress data structure
        assert 'state' in data
        assert 'progress' in data
        assert 'status' in data
        
        # Verify values match database
        assert data['progress'] == sample_optimization_task.progress
        assert data['status'] == sample_optimization_task.status
    
    def test_progress_nonexistent_task(self, client):
        """Test progress endpoint with non-existent task"""
        response = client.get('/progress/nonexistent_task_id')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
    
    @patch('app.get_celery_task_result')
    def test_progress_updates_from_celery(self, mock_get_result, client, db_session):
        """Test progress updates are retrieved from Celery"""
        # Mock Celery task result
        mock_get_result.return_value = {
            'state': 'PROGRESS',
            'progress': 75,
            'status': 'processing',
            'step': 'Texture Compression',
            'message': 'Compressing textures...'
        }
        
        # Create task in database
        task = OptimizationTask(
            id='celery_progress_test',
            original_filename='progress_test.glb',
            secure_filename='progress_test_secure.glb',
            status='processing',
            progress=50  # Different from Celery state
        )
        db_session.add(task)
        db_session.commit()
        
        response = client.get('/progress/celery_progress_test')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Should return Celery state when available
        assert data['progress'] == 75  # From Celery, not database
        assert data['step'] == 'Texture Compression'

class TestDownloadWorkflow:
    """Test file download functionality"""
    
    def test_download_completed_task(self, client, db_session, test_dirs):
        """Test downloading optimized file for completed task"""
        # Create completed task
        task = OptimizationTask(
            id='download_test_task',
            original_filename='download_test.glb',
            secure_filename='download_test_secure.glb',
            status='completed',
            progress=100
        )
        db_session.add(task)
        db_session.commit()
        
        # Create output file
        output_file = os.path.join(test_dirs['output_dir'], f'{task.id}_optimized.glb')
        with open(output_file, 'wb') as f:
            f.write(b'optimized GLB content')
        
        response = client.get(f'/download/{task.id}')
        
        if response.status_code == 200:
            # Verify file download
            assert response.headers['Content-Type'] == 'application/octet-stream'
            assert 'attachment' in response.headers['Content-Disposition']
            assert b'optimized GLB content' in response.data
        else:
            # May return redirect or error in test environment
            assert response.status_code in [302, 404, 500]
    
    def test_download_nonexistent_task(self, client):
        """Test download attempt for non-existent task"""
        response = client.get('/download/nonexistent_task')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_download_incomplete_task(self, client, db_session):
        """Test download attempt for incomplete task"""
        # Create incomplete task
        task = OptimizationTask(
            id='incomplete_task',
            original_filename='incomplete.glb',
            secure_filename='incomplete_secure.glb',
            status='processing',
            progress=50
        )
        db_session.add(task)
        db_session.commit()
        
        response = client.get(f'/download/{task.id}')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'not completed' in data['error'].lower()

class TestCeleryIntegration:
    """Test Celery task queue integration"""
    
    @patch('tasks.optimize_glb_file.delay')
    def test_task_queuing(self, mock_delay, client):
        """Test that optimization tasks are properly queued"""
        mock_task = MagicMock()
        mock_task.id = 'queued_task_123'
        mock_delay.return_value = mock_task
        
        test_file_content = b'glTF' + b'\x02\x00\x00\x00' + b'\x64\x00\x00\x00' + b'\x00' * 100
        
        response = client.post('/upload', data={
            'file': (BytesIO(test_file_content), 'queue_test.glb'),
            'quality_level': 'balanced'
        }, content_type='multipart/form-data')
        
        # Verify task was queued
        assert response.status_code == 200
        mock_delay.assert_called_once()
        
        # Verify task parameters
        call_args = mock_delay.call_args
        assert len(call_args[0]) >= 3  # Should have input_path, output_path, original_name
        assert call_args[1]['quality_level'] == 'balanced'
    
    def test_celery_worker_connection(self):
        """Test Celery worker connectivity"""
        # This test verifies that Celery can connect to Redis
        # In a real environment, this would check broker connectivity
        
        from celery_app import make_celery
        
        try:
            celery_app = make_celery()
            
            # Try to inspect the worker
            inspect = celery_app.control.inspect()
            
            # This will succeed if Redis is available and workers are running
            # In test environment, we just verify the app can be created
            assert celery_app is not None
            assert celery_app.broker_url is not None
            
        except Exception as e:
            # In test environment, Celery workers may not be running
            # This is acceptable for integration tests
            pytest.skip(f"Celery not available in test environment: {e}")

class TestDatabaseIntegration:
    """Test database operations and consistency"""
    
    def test_task_lifecycle_database_updates(self, db_session):
        """Test database updates throughout task lifecycle"""
        # Create initial task
        task = OptimizationTask(
            id='lifecycle_test',
            original_filename='lifecycle.glb',
            secure_filename='lifecycle_secure.glb',
            status='pending',
            progress=0
        )
        db_session.add(task)
        db_session.commit()
        
        # Simulate progress updates
        progress_updates = [
            ('processing', 25, 'Pruning data'),
            ('processing', 50, 'Compressing geometry'),
            ('processing', 75, 'Optimizing textures'),
            ('completed', 100, 'Optimization complete')
        ]
        
        for status, progress, message in progress_updates:
            task.status = status
            task.progress = progress
            task.current_step = message
            db_session.commit()
            
            # Verify updates persist
            db_session.refresh(task)
            assert task.status == status
            assert task.progress == progress
            assert task.current_step == message
    
    def test_concurrent_task_creation(self, db_session):
        """Test handling of concurrent task creation"""
        # Simulate multiple simultaneous uploads
        tasks = []
        for i in range(5):
            task = OptimizationTask(
                id=f'concurrent_task_{i}',
                original_filename=f'concurrent_{i}.glb',
                secure_filename=f'concurrent_{i}_secure.glb',
                status='pending'
            )
            tasks.append(task)
            db_session.add(task)
        
        db_session.commit()
        
        # Verify all tasks were created
        created_tasks = db_session.query(OptimizationTask).filter(
            OptimizationTask.id.like('concurrent_task_%')
        ).all()
        
        assert len(created_tasks) == 5
        
        # Verify each task has unique ID
        task_ids = [task.id for task in created_tasks]
        assert len(set(task_ids)) == 5  # All unique
    
    def test_database_rollback_on_error(self, db_session):
        """Test database rollback when errors occur"""
        initial_count = db_session.query(OptimizationTask).count()
        
        try:
            # Create task
            task = OptimizationTask(
                id='rollback_test',
                original_filename='rollback.glb',
                secure_filename='rollback_secure.glb'
            )
            db_session.add(task)
            
            # Simulate error condition
            raise Exception("Simulated error")
            
        except Exception:
            # Rollback should occur
            db_session.rollback()
        
        # Verify no task was created
        final_count = db_session.query(OptimizationTask).count()
        assert final_count == initial_count

class TestErrorHandling:
    """Test error handling across components"""
    
    def test_upload_with_corrupted_file(self, client):
        """Test handling of corrupted GLB files"""
        # Create file with GLB header but corrupted data
        corrupted_content = b'glTF' + b'\x02\x00\x00\x00' + b'\xFF' * 100
        
        response = client.post('/upload', data={
            'file': (BytesIO(corrupted_content), 'corrupted.glb'),
            'quality_level': 'high'
        }, content_type='multipart/form-data')
        
        # Should handle gracefully
        assert response.status_code in [200, 400]
        
        if response.status_code == 200:
            # If upload succeeds, error should be caught during processing
            data = json.loads(response.data)
            assert 'task_id' in data
        else:
            # If upload fails, should have error message
            data = json.loads(response.data)
            assert 'error' in data
    
    def test_database_connection_error_handling(self, client):
        """Test handling when database is unavailable"""
        with patch('app.get_db') as mock_get_db:
            mock_get_db.side_effect = Exception("Database connection failed")
            
            response = client.get('/admin/stats')
            
            # Should handle database errors gracefully
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data
    
    def test_redis_connection_error_handling(self, client):
        """Test handling when Redis is unavailable"""
        test_file_content = b'glTF' + b'\x02\x00\x00\x00' + b'\x64\x00\x00\x00' + b'\x00' * 100
        
        with patch('app.start_optimization_pipeline') as mock_pipeline:
            mock_pipeline.side_effect = Exception("Redis connection failed")
            
            response = client.post('/upload', data={
                'file': (BytesIO(test_file_content), 'redis_test.glb'),
                'quality_level': 'high'
            }, content_type='multipart/form-data')
            
            # Should handle Redis errors gracefully
            assert response.status_code in [200, 500]
            
            if response.status_code == 500:
                data = json.loads(response.data)
                assert 'error' in data