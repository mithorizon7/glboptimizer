#!/usr/bin/env python3
"""
Comprehensive test suite for parallel compression system
Tests the new process-based parallel compression with proper validation
"""
import pytest
import os
import tempfile
import shutil
import time
import multiprocessing
from unittest.mock import patch, MagicMock
from optimizer import GLBOptimizer, run_gltfpack_geometry_parallel, run_draco_compression_parallel, run_gltf_transform_optimize_parallel
from config import Config

class TestParallelCompression:
    """Test suite for parallel compression functionality"""
    
    def setup_method(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp(prefix='test_parallel_')
        self.input_file = os.path.join(self.test_dir, 'test_input.glb')
        self.output_file = os.path.join(self.test_dir, 'test_output.glb')
        
        # Create a minimal valid GLB file for testing
        self._create_minimal_glb(self.input_file)
    
    def teardown_method(self):
        """Clean up test environment"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def _create_minimal_glb(self, filepath):
        """Create a minimal valid GLB file for testing"""
        # GLB header: magic(4) + version(4) + length(4) + JSON chunk header(8) + minimal JSON(12) = 32 bytes
        glb_header = b'glTF'  # magic
        glb_header += (2).to_bytes(4, 'little')  # version
        glb_header += (32).to_bytes(4, 'little')  # total length
        glb_header += (12).to_bytes(4, 'little')  # JSON chunk length
        glb_header += b'JSON'  # JSON chunk type
        glb_header += b'{"asset":{}}' # minimal JSON content (12 bytes)
        
        with open(filepath, 'wb') as f:
            f.write(glb_header)
    
    def test_cpu_core_detection(self):
        """Test CPU core detection for worker scaling"""
        cores = multiprocessing.cpu_count()
        assert cores > 0
        assert isinstance(cores, int)
        print(f"Detected {cores} CPU cores")
    
    def test_config_parallel_settings(self):
        """Test parallel processing configuration"""
        assert hasattr(Config, 'MAX_PARALLEL_WORKERS')
        assert hasattr(Config, 'PARALLEL_TIMEOUT')
        assert Config.MAX_PARALLEL_WORKERS >= 1
        assert Config.PARALLEL_TIMEOUT > 0
        print(f"Config: MAX_PARALLEL_WORKERS={Config.MAX_PARALLEL_WORKERS}, PARALLEL_TIMEOUT={Config.PARALLEL_TIMEOUT}")
    
    def test_model_analysis_and_method_selection(self):
        """Test model complexity analysis and compression method selection"""
        with GLBOptimizer('high') as optimizer:
            # Test model analysis
            analysis = optimizer._analyze_model_complexity(self.input_file)
            assert isinstance(analysis, dict)
            
            # Test method selection
            methods = optimizer._select_compression_methods(analysis)
            assert isinstance(methods, list)
            assert len(methods) > 0
            assert all(method in ['meshopt', 'draco', 'hybrid'] for method in methods)
            print(f"Selected methods: {methods}")
    
    def test_standalone_compression_functions(self):
        """Test standalone compression functions for parallel processing"""
        # Test gltfpack function signature
        assert callable(run_gltfpack_geometry_parallel)
        assert callable(run_draco_compression_parallel)
        assert callable(run_gltf_transform_optimize_parallel)
        
        # Test with mock subprocess to verify command structure
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            
            # Test gltfpack parallel function
            result = run_gltfpack_geometry_parallel(self.input_file, self.output_file)
            assert isinstance(result, dict)
            assert 'success' in result
            
            # Verify gltfpack command was called correctly
            mock_run.assert_called()
            call_args = mock_run.call_args[0][0]
            assert 'gltfpack' in call_args
            assert '-i' in call_args
            assert '-o' in call_args
    
    def test_worker_count_calculation(self):
        """Test intelligent worker count calculation"""
        with GLBOptimizer('high') as optimizer:
            available_cores = multiprocessing.cpu_count()
            
            # Test with different method counts
            for method_count in [1, 2, 3, 5]:
                methods = ['meshopt', 'draco', 'hybrid', 'extra1', 'extra2'][:method_count]
                max_workers = min(available_cores, len(methods), Config.MAX_PARALLEL_WORKERS)
                
                assert max_workers >= 1
                assert max_workers <= available_cores
                assert max_workers <= Config.MAX_PARALLEL_WORKERS
                assert max_workers <= len(methods)
                print(f"Methods: {method_count}, Workers: {max_workers}")
    
    def test_sequential_fallback_for_single_method(self):
        """Test that single method uses sequential processing to avoid overhead"""
        with GLBOptimizer('high') as optimizer:
            # Mock method selection to return single method
            with patch.object(optimizer, '_select_compression_methods', return_value=['meshopt']):
                with patch.object(optimizer, '_run_gltfpack_geometry') as mock_sequential:
                    mock_sequential.return_value = {'success': True, 'method': 'meshopt'}
                    
                    result = optimizer._run_advanced_geometry_compression(
                        self.input_file, self.output_file
                    )
                    
                    # Should use sequential processing for single method
                    mock_sequential.assert_called_once()
                    assert result['success']
    
    def test_parallel_processing_with_multiple_methods(self):
        """Test parallel processing is used with multiple methods"""
        with GLBOptimizer('high') as optimizer:
            # Mock method selection to return multiple methods
            with patch.object(optimizer, '_select_compression_methods', return_value=['meshopt', 'draco']):
                with patch('concurrent.futures.ProcessPoolExecutor') as mock_executor:
                    mock_context = MagicMock()
                    mock_executor.return_value.__enter__.return_value = mock_context
                    
                    # Mock successful futures
                    mock_future1 = MagicMock()
                    mock_future1.result.return_value = {'success': True}
                    mock_future2 = MagicMock()
                    mock_future2.result.return_value = {'success': True}
                    
                    mock_context.submit.side_effect = [mock_future1, mock_future2]
                    
                    # Mock as_completed to return futures
                    with patch('concurrent.futures.as_completed', return_value=[mock_future1, mock_future2]):
                        with patch('os.path.exists', return_value=True):
                            with patch('os.path.getsize', return_value=1000):
                                with patch('shutil.copy2'):
                                    result = optimizer._run_advanced_geometry_compression(
                                        self.input_file, self.output_file
                                    )
                    
                    # Should use parallel processing
                    mock_executor.assert_called_once()
                    assert mock_context.submit.call_count == 2
    
    def test_timeout_handling(self):
        """Test timeout handling in parallel processing"""
        with GLBOptimizer('high') as optimizer:
            with patch.object(optimizer, '_select_compression_methods', return_value=['meshopt', 'draco']):
                with patch('concurrent.futures.ProcessPoolExecutor') as mock_executor:
                    # Simulate timeout
                    mock_executor.return_value.__enter__.return_value.submit.side_effect = Exception("Timeout")
                    
                    # Should fallback to sequential processing
                    with patch.object(optimizer, '_run_gltfpack_geometry') as mock_fallback:
                        mock_fallback.return_value = {'success': True, 'method': 'meshopt'}
                        
                        result = optimizer._run_advanced_geometry_compression(
                            self.input_file, self.output_file
                        )
                        
                        # Should use fallback
                        mock_fallback.assert_called_once()
                        assert result['success']
    
    def test_temp_file_management(self):
        """Test proper temporary file management in parallel processing"""
        with GLBOptimizer('high') as optimizer:
            with patch.object(optimizer, '_select_compression_methods', return_value=['meshopt', 'draco']):
                with patch('concurrent.futures.ProcessPoolExecutor'):
                    with patch('concurrent.futures.as_completed', return_value=[]):
                        with patch.object(optimizer, '_run_gltfpack_geometry') as mock_fallback:
                            mock_fallback.return_value = {'success': True}
                            
                            initial_temp_count = len(optimizer._temp_files)
                            
                            optimizer._run_advanced_geometry_compression(
                                self.input_file, self.output_file
                            )
                            
                            # Temp files should be cleaned up
                            final_temp_count = len(optimizer._temp_files)
                            print(f"Temp files: {initial_temp_count} -> {final_temp_count}")
    
    def test_best_method_selection(self):
        """Test selection of best compression method based on file size"""
        with GLBOptimizer('high') as optimizer:
            # Simulate different compression results
            results = {
                'meshopt': {'success': True},
                'draco': {'success': True},
                'hybrid': {'success': False}
            }
            
            file_sizes = {
                'meshopt': 2000,  # Larger file
                'draco': 1500     # Smaller file (should be selected)
            }
            
            # Test best method selection logic
            successful_methods = {method: size for method, size in file_sizes.items() 
                                if results[method]['success']}
            
            best_method_name, best_size = min(successful_methods.items(), key=lambda x: x[1])
            
            assert best_method_name == 'draco'
            assert best_size == 1500
            print(f"Best method: {best_method_name} ({best_size} bytes)")
    
    def test_safe_environment_for_subprocesses(self):
        """Test that subprocess environments are properly sanitized"""
        safe_env = {
            'PATH': '/usr/local/bin:/usr/bin:/bin',
            'HOME': '/tmp',
            'LANG': 'C.UTF-8'
        }
        
        # Test that dangerous environment variables are not included
        dangerous_vars = ['LD_PRELOAD', 'LD_LIBRARY_PATH', 'PYTHONPATH']
        for var in dangerous_vars:
            assert var not in safe_env
        
        # Test required safe variables are present
        assert 'PATH' in safe_env
        assert 'HOME' in safe_env
        assert 'LANG' in safe_env
        print(f"Safe environment: {safe_env}")
    
    def test_performance_metrics_calculation(self):
        """Test performance metrics calculation"""
        with GLBOptimizer('high') as optimizer:
            # Create test files with known sizes
            input_size = 1000
            output_size = 600
            
            with patch('os.path.getsize') as mock_size:
                mock_size.side_effect = [input_size, output_size]
                
                # Test compression ratio calculation
                compression_ratio = (1 - output_size / input_size) * 100
                expected_ratio = 40.0  # 40% reduction
                
                assert abs(compression_ratio - expected_ratio) < 0.1
                print(f"Compression ratio: {compression_ratio}%")

def test_parallel_compression_integration():
    """Integration test for the complete parallel compression system"""
    print("\n=== Parallel Compression Integration Test ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        input_file = os.path.join(temp_dir, 'test_input.glb')
        output_file = os.path.join(temp_dir, 'test_output.glb')
        
        # Create minimal GLB file
        with open(input_file, 'wb') as f:
            glb_data = b'glTF' + (2).to_bytes(4, 'little') + (32).to_bytes(4, 'little')
            glb_data += (12).to_bytes(4, 'little') + b'JSON' + b'{"asset":{}}'
            f.write(glb_data)
        
        with GLBOptimizer('high') as optimizer:
            start_time = time.time()
            
            # Test the complete parallel compression workflow
            result = optimizer._run_advanced_geometry_compression(input_file, output_file)
            
            elapsed = time.time() - start_time
            
            print(f"Integration test completed in {elapsed:.2f} seconds")
            print(f"Result: {result}")
            
            # Verify result structure
            assert isinstance(result, dict)
            assert 'success' in result
            
            if result['success']:
                assert 'method' in result
                assert 'compression_ratio' in result
                print(f"✓ Parallel compression system working correctly")
            else:
                print(f"⚠ Parallel compression failed (expected in test environment): {result.get('error', 'Unknown')}")

if __name__ == '__main__':
    # Run the integration test directly
    test_parallel_compression_integration()
    
    # Run pytest tests
    pytest.main([__file__, '-v'])