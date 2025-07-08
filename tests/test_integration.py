"""
Integration tests for GLB Optimizer
Tests complete workflows and component interactions
"""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from optimizer import GLBOptimizer
from config import OptimizationConfig


class TestOptimizationWorkflow:
    """Test complete optimization workflows"""
    
    @pytest.mark.integration
    def test_full_optimization_workflow_mocked(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir):
        """Test complete optimization workflow with mocked external tools"""
        optimizer = optimizer_with_temp_dirs
        output_file = Path(temp_dir) / 'optimized.glb'
        
        # Mock all subprocess calls to succeed
        with patch('optimizer.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='Optimization successful',
                stderr='',
                args=[]
            )
            
            # Mock file operations to simulate optimization steps
            with patch('shutil.copy2') as mock_copy, \
                 patch('optimizer.path_size') as mock_size, \
                 patch('optimizer.path_exists') as mock_exists:
                
                mock_exists.return_value = True
                # Simulate file size reduction through optimization steps
                mock_size.side_effect = lambda x: 5000 if 'optimized' in str(x) else 10000
                
                # Mock progress callback
                progress_calls = []
                def mock_progress(step, progress, message):
                    progress_calls.append((step, progress, message))
                
                result = optimizer.optimize(minimal_glb_file, str(output_file), mock_progress)
                
                assert result['success'] is True
                assert result['output_path'] == str(output_file)
                assert 'compression_ratio' in result
                assert 'processing_time' in result
                
                # Verify progress callbacks were made
                assert len(progress_calls) > 0
                assert any('prune' in call[2].lower() for call in progress_calls)
    
    @pytest.mark.integration
    def test_optimization_with_different_quality_levels(self, uploads_dir, output_dir, minimal_glb_file, temp_dir):
        """Test optimization with different quality levels"""
        quality_levels = ['high', 'balanced', 'maximum_compression']
        
        for quality_level in quality_levels:
            with patch('optimizer.OptimizationConfig.from_env') as mock_config:
                config = MagicMock()
                config.get_quality_settings.return_value = {
                    'description': f'{quality_level} quality',
                    'meshopt_compression': True,
                    'draco_compression': quality_level != 'high',
                    'texture_compression': True,
                    'enable_ktx2': quality_level == 'high'
                }
                config.to_dict.return_value = {'test': 'config'}
                mock_config.return_value = config
                
                with patch('optimizer.GLBOptimizer._get_allowed_directories') as mock_dirs:
                    mock_dirs.return_value = [uploads_dir, output_dir]
                    
                    optimizer = GLBOptimizer(quality_level=quality_level)
                    
                    # Mock subprocess calls
                    with patch('optimizer.subprocess.run') as mock_run:
                        mock_run.return_value = MagicMock(
                            returncode=0,
                            stdout=f'{quality_level} optimization successful',
                            stderr='',
                            args=[]
                        )
                        
                        with patch('shutil.copy2'), \
                             patch('optimizer.path_size', return_value=5000), \
                             patch('optimizer.path_exists', return_value=True):
                            
                            output_file = Path(temp_dir) / f'optimized_{quality_level}.glb'
                            result = optimizer.optimize(minimal_glb_file, str(output_file))
                            
                            assert result['success'] is True
                            assert optimizer.quality_level == quality_level
    
    @pytest.mark.integration
    def test_optimization_error_recovery(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir):
        """Test optimization error recovery and fallback mechanisms"""
        optimizer = optimizer_with_temp_dirs
        output_file = Path(temp_dir) / 'error_recovery.glb'
        
        call_count = 0
        def mock_subprocess_with_failures(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            # First few calls fail, later ones succeed
            if call_count <= 2:
                return MagicMock(
                    returncode=1,
                    stdout='',
                    stderr='Tool failed',
                    args=args[0]
                )
            else:
                return MagicMock(
                    returncode=0,
                    stdout='Success',
                    stderr='',
                    args=args[0]
                )
        
        with patch('optimizer.subprocess.run', side_effect=mock_subprocess_with_failures):
            with patch('shutil.copy2') as mock_copy, \
                 patch('optimizer.path_size', return_value=8000), \
                 patch('optimizer.path_exists', return_value=True):
                
                result = optimizer.optimize(minimal_glb_file, str(output_file))
                
                # Should succeed despite initial failures due to fallback mechanisms
                assert result['success'] is True
                
                # Should have attempted fallback operations
                assert mock_copy.call_count > 0
    
    @pytest.mark.integration  
    def test_optimization_step_isolation(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir):
        """Test that optimization steps are properly isolated"""
        optimizer = optimizer_with_temp_dirs
        output_file = Path(temp_dir) / 'step_isolation.glb'
        
        # Track which steps were called
        steps_called = []
        
        def mock_subprocess_tracker(*args, **kwargs):
            cmd = args[0]
            if 'prune' in cmd:
                steps_called.append('prune')
            elif 'weld' in cmd:
                steps_called.append('weld')
            elif 'gltfpack' in cmd[0]:
                steps_called.append('gltfpack')
            elif 'draco' in cmd:
                steps_called.append('draco')
            elif 'ktx' in cmd or 'webp' in cmd:
                steps_called.append('texture')
            elif 'resample' in cmd:
                steps_called.append('animation')
            
            return MagicMock(
                returncode=0,
                stdout='Step successful',
                stderr='',
                args=cmd
            )
        
        with patch('optimizer.subprocess.run', side_effect=mock_subprocess_tracker):
            with patch('shutil.copy2'), \
                 patch('optimizer.path_size', return_value=6000), \
                 patch('optimizer.path_exists', return_value=True):
                
                result = optimizer.optimize(minimal_glb_file, str(output_file))
                
                assert result['success'] is True
                
                # Verify expected steps were called
                expected_steps = ['prune', 'weld']  # Minimum expected steps
                for step in expected_steps:
                    assert step in steps_called


class TestConfigurationIntegration:
    """Test integration with configuration system"""
    
    @pytest.mark.integration
    def test_config_loading_and_validation(self):
        """Test configuration loading and validation"""
        config = OptimizationConfig.from_env()
        
        # Validate configuration
        issues = config.validate()
        
        # Should have valid configuration
        assert isinstance(config.MAX_FILE_SIZE_MB, (int, float))
        assert config.MAX_FILE_SIZE_MB > 0
        assert config.SUBPROCESS_TIMEOUT > 0
        assert config.MAX_PARALLEL_WORKERS > 0
        
        # Should have no critical validation issues
        critical_issues = [issue for issue in issues if 'CRITICAL' in issue]
        assert len(critical_issues) == 0
    
    @pytest.mark.integration
    def test_quality_settings_integration(self):
        """Test quality settings integration"""
        config = OptimizationConfig.from_env()
        
        quality_levels = ['high', 'balanced', 'maximum_compression']
        
        for level in quality_levels:
            settings = config.get_quality_settings(level)
            
            assert 'description' in settings
            assert 'meshopt_compression' in settings
            assert 'draco_compression' in settings
            assert 'texture_compression' in settings
            
            # Verify settings make sense for quality level
            if level == 'high':
                assert settings['draco_compression'] is True
            elif level == 'maximum_compression':
                assert settings['meshopt_compression'] is True
    
    @pytest.mark.integration
    def test_environment_variable_override(self):
        """Test that environment variables properly override defaults"""
        test_env = {
            'GLB_MAX_FILE_SIZE_MB': '50',
            'GLB_SUBPROCESS_TIMEOUT': '600',
            'GLB_MAX_PARALLEL_WORKERS': '4'
        }
        
        with patch.dict(os.environ, test_env):
            config = OptimizationConfig.from_env()
            
            assert config.MAX_FILE_SIZE_MB == 50
            assert config.SUBPROCESS_TIMEOUT == 600
            assert config.MAX_PARALLEL_WORKERS == 4


class TestResourceManagement:
    """Test resource management and cleanup"""
    
    @pytest.mark.integration
    def test_temp_file_lifecycle(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir):
        """Test temporary file creation and cleanup lifecycle"""
        optimizer = optimizer_with_temp_dirs
        
        initial_temp_dir = optimizer._secure_temp_dir
        assert Path(initial_temp_dir).exists()
        
        # Create some temporary files during optimization
        temp_files_created = []
        
        original_mktemp = tempfile.mktemp
        def track_temp_files(*args, **kwargs):
            temp_file = original_mktemp(*args, **kwargs)
            temp_files_created.append(temp_file)
            return temp_file
        
        with patch('tempfile.mktemp', side_effect=track_temp_files):
            with patch('optimizer.subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout='Success',
                    stderr='',
                    args=[]
                )
                
                with patch('shutil.copy2'), \
                     patch('optimizer.path_size', return_value=5000), \
                     patch('optimizer.path_exists', return_value=True):
                    
                    output_file = Path(temp_dir) / 'lifecycle_test.glb'
                    result = optimizer.optimize(minimal_glb_file, str(output_file))
                    
                    assert result['success'] is True
        
        # After optimization, temporary directory should still exist until context exit
        assert Path(initial_temp_dir).exists()
    
    @pytest.mark.integration
    def test_memory_usage_during_optimization(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir):
        """Test memory usage patterns during optimization"""
        optimizer = optimizer_with_temp_dirs
        output_file = Path(temp_dir) / 'memory_test.glb'
        
        # Mock optimization to track memory-related operations
        file_read_calls = []
        
        def track_file_reads(filepath, mode='rb'):
            file_read_calls.append(filepath)
            if 'rb' in mode:
                # Return minimal content to avoid memory usage
                return open(minimal_glb_file, mode)
            return open(filepath, mode)
        
        with patch('builtins.open', side_effect=track_file_reads):
            with patch('optimizer.subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout='Success',
                    stderr='',
                    args=[]
                )
                
                with patch('shutil.copy2'), \
                     patch('optimizer.path_size', return_value=5000), \
                     patch('optimizer.path_exists', return_value=True):
                    
                    result = optimizer.optimize(minimal_glb_file, str(output_file))
                    
                    assert result['success'] is True
                    
                    # Should not have excessive file reading operations
                    assert len(file_read_calls) < 50  # Reasonable limit


class TestErrorScenarios:
    """Test various error scenarios and edge cases"""
    
    @pytest.mark.integration
    def test_partial_optimization_failure(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir):
        """Test handling when some optimization steps fail"""
        optimizer = optimizer_with_temp_dirs
        output_file = Path(temp_dir) / 'partial_failure.glb'
        
        # Mock some steps to fail, others to succeed
        def selective_subprocess_failure(*args, **kwargs):
            cmd = args[0]
            if 'draco' in cmd:
                # Draco fails
                return MagicMock(
                    returncode=1,
                    stdout='',
                    stderr='Draco compression failed',
                    args=cmd
                )
            else:
                # Other steps succeed
                return MagicMock(
                    returncode=0,
                    stdout='Success',
                    stderr='',
                    args=cmd
                )
        
        with patch('optimizer.subprocess.run', side_effect=selective_subprocess_failure):
            with patch('shutil.copy2') as mock_copy, \
                 patch('optimizer.path_size', return_value=7000), \
                 patch('optimizer.path_exists', return_value=True):
                
                result = optimizer.optimize(minimal_glb_file, str(output_file))
                
                # Should still succeed due to fallback mechanisms
                assert result['success'] is True
                
                # Should have fallback copy operations
                assert mock_copy.call_count > 0
    
    @pytest.mark.integration
    def test_disk_space_error_simulation(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir):
        """Test handling of disk space errors"""
        optimizer = optimizer_with_temp_dirs
        output_file = Path(temp_dir) / 'disk_space_error.glb'
        
        # Mock disk space error
        def disk_space_error(*args, **kwargs):
            raise OSError('No space left on device')
        
        with patch('shutil.copy2', side_effect=disk_space_error):
            with patch('optimizer.subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout='Success',
                    stderr='',
                    args=[]
                )
                
                result = optimizer.optimize(minimal_glb_file, str(output_file))
                
                # Should fail gracefully
                assert result['success'] is False
                assert 'space' in result['error'].lower() or 'disk' in result['error'].lower()
    
    @pytest.mark.integration
    def test_permission_error_handling(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir):
        """Test handling of file permission errors"""
        optimizer = optimizer_with_temp_dirs
        output_file = Path(temp_dir) / 'permission_error.glb'
        
        # Mock permission error
        def permission_error(*args, **kwargs):
            raise PermissionError('Permission denied')
        
        with patch('shutil.copy2', side_effect=permission_error):
            with patch('optimizer.subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout='Success',
                    stderr='',
                    args=[]
                )
                
                result = optimizer.optimize(minimal_glb_file, str(output_file))
                
                # Should fail gracefully
                assert result['success'] is False
                assert 'permission' in result['error'].lower()


class TestPerformanceIntegration:
    """Test performance-related integration scenarios"""
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_large_file_handling_simulation(self, optimizer_with_temp_dirs, uploads_dir, temp_dir):
        """Test handling of large files (simulated)"""
        optimizer = optimizer_with_temp_dirs
        
        # Create a simulated large GLB file (valid header, large content)
        large_file = Path(uploads_dir) / 'large_model.glb'
        json_data = b'{"asset":{"version":"2.0"}}' + b' ' * (5 * 1024 * 1024)  # 5MB
        json_length = len(json_data)
        padding = (4 - (json_length % 4)) % 4
        json_data += b' ' * padding
        json_length = len(json_data)
        total_size = 12 + 8 + json_length
        
        with open(large_file, 'wb') as f:
            f.write(b'glTF')
            f.write((2).to_bytes(4, 'little'))
            f.write(total_size.to_bytes(4, 'little'))
            f.write(json_length.to_bytes(4, 'little'))
            f.write(b'JSON')
            f.write(json_data)
        
        output_file = Path(temp_dir) / 'large_optimized.glb'
        
        # Mock optimization to handle large file
        with patch('optimizer.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='Large file processed',
                stderr='',
                args=[]
            )
            
            with patch('shutil.copy2'), \
                 patch('optimizer.path_size', return_value=1024*1024), \
                 patch('optimizer.path_exists', return_value=True):
                
                result = optimizer.optimize(str(large_file), str(output_file))
                
                assert result['success'] is True
                assert 'compression_ratio' in result
                # Should show significant compression
                assert result['compression_ratio'] > 0.5
    
    @pytest.mark.integration
    def test_concurrent_optimization_simulation(self, uploads_dir, output_dir, minimal_glb_file):
        """Test simulation of concurrent optimization requests"""
        # Simulate multiple optimizers working concurrently
        optimizers = []
        
        for i in range(3):
            with patch('optimizer.OptimizationConfig.from_env') as mock_config:
                config = MagicMock()
                config.get_quality_settings.return_value = {'description': 'test'}
                config.to_dict.return_value = {'test': 'config'}
                mock_config.return_value = config
                
                with patch('optimizer.GLBOptimizer._get_allowed_directories') as mock_dirs:
                    mock_dirs.return_value = [uploads_dir, output_dir]
                    
                    optimizer = GLBOptimizer(quality_level='high')
                    optimizers.append(optimizer)
        
        # Each should have isolated temp directories
        temp_dirs = [opt._secure_temp_dir for opt in optimizers]
        assert len(set(temp_dirs)) == 3  # All different
        
        # Clean up
        for optimizer in optimizers:
            optimizer.cleanup_temp_files()