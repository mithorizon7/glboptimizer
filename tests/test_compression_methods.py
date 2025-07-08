"""
Tests for GLB compression methods with mocked subprocess calls
Tests individual compression steps in isolation
"""
import pytest
import tempfile
import struct
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from optimizer import GLBOptimizer


class TestMeshCompression:
    """Test mesh compression methods with mocked subprocesses"""
    
    @pytest.mark.unit
    def test_gltfpack_geometry_compression(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir, mock_subprocess):
        """Test gltfpack geometry compression with mocked subprocess"""
        optimizer = optimizer_with_temp_dirs
        output_file = Path(temp_dir) / 'compressed.glb'
        
        # Mock successful gltfpack execution
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = 'gltfpack successful'
        mock_subprocess.return_value.stderr = ''
        
        # Mock file copy for fallback
        with patch('shutil.copy2') as mock_copy:
            result = optimizer._run_gltfpack_geometry(minimal_glb_file, str(output_file))
            
            assert result['success'] is True
            mock_subprocess.assert_called_once()
            
            # Verify gltfpack command structure
            call_args = mock_subprocess.call_args[0][0]
            assert 'gltfpack' in call_args[0]
            assert '-cc' in call_args  # Compression flag
            assert '-i' in call_args   # Input flag
            assert '-o' in call_args   # Output flag
    
    @pytest.mark.unit
    def test_draco_compression(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir, mock_subprocess):
        """Test Draco compression with mocked subprocess"""
        optimizer = optimizer_with_temp_dirs
        output_file = Path(temp_dir) / 'draco_compressed.glb'
        
        # Mock successful gltf-transform execution
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = 'draco compression successful'
        mock_subprocess.return_value.stderr = ''
        
        with patch('shutil.copy2') as mock_copy:
            result = optimizer._run_draco_compression(minimal_glb_file, str(output_file))
            
            assert result['success'] is True
            mock_subprocess.assert_called_once()
            
            # Verify draco command structure
            call_args = mock_subprocess.call_args[0][0]
            assert 'gltf-transform' in call_args[0] or 'npx' in call_args[0]
            assert 'draco' in call_args
    
    @pytest.mark.unit
    def test_advanced_geometry_compression_parallel(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir):
        """Test parallel geometry compression method selection"""
        optimizer = optimizer_with_temp_dirs
        output_file = Path(temp_dir) / 'parallel_compressed.glb'
        
        # Mock the individual compression functions
        with patch.object(optimizer, '_run_gltfpack_geometry') as mock_gltfpack, \
             patch.object(optimizer, '_run_draco_compression') as mock_draco, \
             patch.object(optimizer, '_run_gltf_transform_optimize') as mock_optimize:
            
            # Mock different compression results
            mock_gltfpack.return_value = {
                'success': True, 'output_size': 1000, 'compression_ratio': 0.5
            }
            mock_draco.return_value = {
                'success': True, 'output_size': 800, 'compression_ratio': 0.6  # Better compression
            }
            mock_optimize.return_value = {
                'success': True, 'output_size': 1200, 'compression_ratio': 0.4
            }
            
            # Mock file operations
            with patch('shutil.copy2') as mock_copy, \
                 patch('optimizer.path_size') as mock_size, \
                 patch('optimizer.path_exists') as mock_exists:
                
                mock_exists.return_value = True
                mock_size.return_value = 800  # Draco result size
                
                result = optimizer._run_advanced_geometry_compression(
                    minimal_glb_file, str(output_file)
                )
                
                assert result['success'] is True
                # Should have selected Draco (best compression)
                assert 'draco' in result['method_used'].lower()
    
    @pytest.mark.unit
    def test_compression_method_failure_fallback(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir):
        """Test fallback when compression methods fail"""
        optimizer = optimizer_with_temp_dirs
        output_file = Path(temp_dir) / 'fallback_compressed.glb'
        
        # Mock all compression methods to fail
        with patch.object(optimizer, '_run_gltfpack_geometry') as mock_gltfpack, \
             patch.object(optimizer, '_run_draco_compression') as mock_draco, \
             patch.object(optimizer, '_run_gltf_transform_optimize') as mock_optimize:
            
            mock_gltfpack.return_value = {'success': False, 'error': 'gltfpack failed'}
            mock_draco.return_value = {'success': False, 'error': 'draco failed'}
            mock_optimize.return_value = {'success': False, 'error': 'optimize failed'}
            
            # Mock file copy for fallback
            with patch('shutil.copy2') as mock_copy:
                result = optimizer._run_advanced_geometry_compression(
                    minimal_glb_file, str(output_file)
                )
                
                # Should fall back to copying original file
                assert result['success'] is True
                assert 'fallback' in result['method_used'].lower()
                mock_copy.assert_called_once()


class TestTextureCompression:
    """Test texture compression methods"""
    
    @pytest.mark.unit
    def test_ktx2_compression(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir, mock_subprocess):
        """Test KTX2 texture compression with mocked subprocess"""
        optimizer = optimizer_with_temp_dirs
        output_file = Path(temp_dir) / 'ktx2_compressed.glb'
        
        # Mock successful KTX2 compression
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = 'KTX2 compression successful'
        mock_subprocess.return_value.stderr = ''
        
        # Mock KTX tool availability
        with patch('shutil.which', return_value='/usr/bin/ktx'):
            result = optimizer._compress_with_ktx2(minimal_glb_file, str(output_file))
            
            assert result['success'] is True
            mock_subprocess.assert_called()
            
            # Verify KTX2 command structure
            call_args = mock_subprocess.call_args[0][0]
            assert any('gltf-transform' in arg or 'npx' in arg for arg in call_args)
            assert 'ktx' in call_args
    
    @pytest.mark.unit
    def test_webp_compression(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir, mock_subprocess):
        """Test WebP texture compression with mocked subprocess"""
        optimizer = optimizer_with_temp_dirs
        output_file = Path(temp_dir) / 'webp_compressed.glb'
        
        # Mock successful WebP compression
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = 'WebP compression successful'
        mock_subprocess.return_value.stderr = ''
        
        result = optimizer._compress_with_webp(minimal_glb_file, str(output_file))
        
        assert result['success'] is True
        mock_subprocess.assert_called_once()
        
        # Verify WebP command structure
        call_args = mock_subprocess.call_args[0][0]
        assert any('gltf-transform' in arg or 'npx' in arg for arg in call_args)
        assert 'webp' in call_args
    
    @pytest.mark.unit
    def test_texture_compression_method_selection(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir):
        """Test texture compression method selection and fallback"""
        optimizer = optimizer_with_temp_dirs
        output_file = Path(temp_dir) / 'texture_compressed.glb'
        
        # Mock compression methods with different results
        with patch.object(optimizer, '_compress_with_ktx2') as mock_ktx2, \
             patch.object(optimizer, '_compress_with_webp') as mock_webp:
            
            # KTX2 fails, WebP succeeds
            mock_ktx2.return_value = {'success': False, 'error': 'KTX2 not available'}
            mock_webp.return_value = {
                'success': True, 
                'output_size': 1500, 
                'compression_ratio': 0.7,
                'temp_file': str(output_file)
            }
            
            # Mock file operations
            with patch('shutil.copy2') as mock_copy, \
                 patch('optimizer.path_size') as mock_size, \
                 patch('optimizer.path_exists') as mock_exists:
                
                mock_exists.return_value = True
                mock_size.return_value = 1500
                
                result = optimizer._run_gltf_transform_textures(
                    minimal_glb_file, str(output_file)
                )
                
                assert result['success'] is True
                # Should have fallen back to WebP
                mock_ktx2.assert_called_once()
                mock_webp.assert_called_once()
    
    @pytest.mark.unit
    def test_texture_compression_best_result_selection(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir):
        """Test selection of best texture compression result"""
        optimizer = optimizer_with_temp_dirs
        
        # Mock compression results with different sizes
        results = [
            {'success': True, 'output_size': 2000, 'format': 'KTX2', 'temp_file': 'ktx2.glb'},
            {'success': True, 'output_size': 1500, 'format': 'WebP', 'temp_file': 'webp.glb'},  # Better
            {'success': False, 'error': 'Failed', 'temp_file': 'failed.glb'}
        ]
        
        temp_files = ['ktx2.glb', 'webp.glb', 'failed.glb']
        
        best_result = optimizer._select_best_texture_result(results, temp_files)
        
        # Should select WebP (smallest size)
        assert best_result['format'] == 'WebP'
        assert best_result['output_size'] == 1500


class TestAnimationOptimization:
    """Test animation optimization methods"""
    
    @pytest.mark.unit
    def test_animation_optimization(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir, mock_subprocess):
        """Test animation optimization with mocked subprocess"""
        optimizer = optimizer_with_temp_dirs
        output_file = Path(temp_dir) / 'animated.glb'
        
        # Mock successful animation optimization
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = 'Animation optimization successful'
        mock_subprocess.return_value.stderr = ''
        
        with patch('shutil.copy2') as mock_copy:
            result = optimizer._run_gltf_transform_animations(minimal_glb_file, str(output_file))
            
            assert result['success'] is True
            mock_subprocess.assert_called_once()
            
            # Verify animation command structure
            call_args = mock_subprocess.call_args[0][0]
            assert any('gltf-transform' in arg or 'npx' in arg for arg in call_args)
            assert 'resample' in call_args


class TestOptimizationSteps:
    """Test individual optimization steps"""
    
    @pytest.mark.unit
    def test_prune_step(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir, mock_subprocess):
        """Test pruning step with mocked subprocess"""
        optimizer = optimizer_with_temp_dirs
        output_file = Path(temp_dir) / 'pruned.glb'
        
        # Mock successful pruning
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = 'Pruning successful'
        mock_subprocess.return_value.stderr = ''
        
        with patch('shutil.copy2') as mock_copy:
            result = optimizer._run_gltf_transform_prune(minimal_glb_file, str(output_file))
            
            assert result['success'] is True
            mock_subprocess.assert_called_once()
            
            # Verify prune command structure
            call_args = mock_subprocess.call_args[0][0]
            assert any('gltf-transform' in arg or 'npx' in arg for arg in call_args)
            assert 'prune' in call_args
    
    @pytest.mark.unit
    def test_weld_step(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir, mock_subprocess):
        """Test welding step with mocked subprocess"""
        optimizer = optimizer_with_temp_dirs
        output_file = Path(temp_dir) / 'welded.glb'
        
        # Mock successful welding
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = 'Welding successful'
        mock_subprocess.return_value.stderr = ''
        
        with patch('shutil.copy2') as mock_copy:
            result = optimizer._run_gltf_transform_weld(minimal_glb_file, str(output_file))
            
            assert result['success'] is True
            mock_subprocess.assert_called_once()
            
            # Verify weld command structure
            call_args = mock_subprocess.call_args[0][0]
            assert any('gltf-transform' in arg or 'npx' in arg for arg in call_args)
            assert 'weld' in call_args
    
    @pytest.mark.unit
    def test_final_optimization_step(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir, mock_subprocess):
        """Test final optimization step with mocked subprocess"""
        optimizer = optimizer_with_temp_dirs
        output_file = Path(temp_dir) / 'final.glb'
        
        # Mock successful final optimization
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = 'Final optimization successful'
        mock_subprocess.return_value.stderr = ''
        
        with patch('shutil.copy2') as mock_copy:
            result = optimizer._run_gltfpack_final(minimal_glb_file, str(output_file))
            
            assert result['success'] is True
            mock_subprocess.assert_called_once()
            
            # Verify final optimization command structure
            call_args = mock_subprocess.call_args[0][0]
            assert 'gltfpack' in call_args[0]
            assert '-cc' in call_args or '-c' in call_args  # Compression flags


class TestModelAnalysis:
    """Test model complexity analysis"""
    
    @pytest.mark.unit
    def test_model_complexity_analysis(self, optimizer_with_temp_dirs, minimal_glb_file, mock_subprocess):
        """Test model complexity analysis with mocked subprocess"""
        optimizer = optimizer_with_temp_dirs
        
        # Mock gltf-transform inspect output
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = """
        {
            "meshes": 1,
            "primitives": 1,
            "vertices": 1000,
            "indices": 3000,
            "textures": 2,
            "materials": 1,
            "animations": 0
        }
        """
        mock_subprocess.return_value.stderr = ''
        
        analysis = optimizer._analyze_model_complexity(minimal_glb_file)
        
        assert analysis['success'] is True
        assert 'vertices' in analysis
        assert 'textures' in analysis
        assert analysis['vertices'] == 1000
    
    @pytest.mark.unit
    def test_compression_method_selection_based_on_analysis(self, optimizer_with_temp_dirs):
        """Test compression method selection based on model analysis"""
        optimizer = optimizer_with_temp_dirs
        
        # Test with high-complexity model
        high_complexity_analysis = {
            'success': True,
            'vertices': 100000,  # High vertex count
            'primitives': 500,
            'textures': 10,      # Many textures
            'file_size': 50 * 1024 * 1024  # Large file
        }
        
        methods = optimizer._select_compression_methods(high_complexity_analysis)
        
        # Should include all compression methods for complex model
        assert 'meshopt' in methods
        assert 'draco' in methods or 'hybrid' in methods
        
        # Test with simple model
        simple_analysis = {
            'success': True,
            'vertices': 100,     # Low vertex count
            'primitives': 1,
            'textures': 1,       # Few textures
            'file_size': 1024    # Small file
        }
        
        methods = optimizer._select_compression_methods(simple_analysis)
        
        # Should use basic methods for simple model
        assert 'meshopt' in methods


class TestErrorHandling:
    """Test error handling in compression methods"""
    
    @pytest.mark.unit
    def test_compression_timeout_handling(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir):
        """Test handling of compression timeouts"""
        optimizer = optimizer_with_temp_dirs
        output_file = Path(temp_dir) / 'timeout_test.glb'
        
        # Mock timeout exception
        with patch('optimizer.subprocess.run') as mock_run:
            import subprocess
            mock_run.side_effect = subprocess.TimeoutExpired(['gltfpack'], 60)
            
            result = optimizer._run_gltfpack_geometry(minimal_glb_file, str(output_file))
            
            assert result['success'] is False
            assert 'timeout' in result['error'].lower()
    
    @pytest.mark.unit
    def test_compression_tool_not_found(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir):
        """Test handling when compression tools are not found"""
        optimizer = optimizer_with_temp_dirs
        output_file = Path(temp_dir) / 'tool_not_found.glb'
        
        # Mock tool not found
        with patch('optimizer.subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError('gltfpack not found')
            
            result = optimizer._run_gltfpack_geometry(minimal_glb_file, str(output_file))
            
            assert result['success'] is False
            assert 'not found' in result['error'].lower()
    
    @pytest.mark.unit
    def test_invalid_input_file_handling(self, optimizer_with_temp_dirs, invalid_glb_file, temp_dir, mock_subprocess):
        """Test handling of invalid input files in compression"""
        optimizer = optimizer_with_temp_dirs
        output_file = Path(temp_dir) / 'invalid_input.glb'
        
        # Mock compression tool rejecting invalid file
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stdout = ''
        mock_subprocess.return_value.stderr = 'Invalid GLB format'
        
        result = optimizer._run_gltfpack_geometry(invalid_glb_file, str(output_file))
        
        assert result['success'] is False
        assert 'invalid' in result['error'].lower()