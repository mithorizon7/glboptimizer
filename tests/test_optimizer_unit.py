"""
Unit tests for GLB Optimizer core functionality
Tests individual methods and components in isolation
"""
import pytest
import tempfile
import struct
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from optimizer import GLBOptimizer, ensure_path, path_exists, path_size, path_basename


class TestPathlibHelpers:
    """Test pathlib helper functions"""
    
    @pytest.mark.unit
    def test_ensure_path(self, temp_dir):
        """Test ensure_path function with various inputs"""
        # Test with string
        result = ensure_path('/test/path')
        assert isinstance(result, Path)
        assert str(result) == '/test/path'
        
        # Test with Path object
        path_obj = Path('/test/path')
        result = ensure_path(path_obj)
        assert isinstance(result, Path)
        assert result == path_obj
        
        # Test with relative path
        result = ensure_path('relative/path')
        assert isinstance(result, Path)
        assert result.name == 'path'
    
    @pytest.mark.unit
    def test_path_exists(self, temp_dir):
        """Test path_exists function"""
        # Test with existing file
        test_file = Path(temp_dir) / 'test.txt'
        test_file.write_text('test')
        
        assert path_exists(str(test_file)) is True
        assert path_exists(test_file) is True
        
        # Test with non-existent file
        non_existent = Path(temp_dir) / 'nonexistent.txt'
        assert path_exists(str(non_existent)) is False
        assert path_exists(non_existent) is False
    
    @pytest.mark.unit
    def test_path_size(self, temp_dir):
        """Test path_size function"""
        test_file = Path(temp_dir) / 'test.txt'
        test_content = 'test content'
        test_file.write_text(test_content)
        
        size = path_size(str(test_file))
        assert size == len(test_content.encode())
        
        size = path_size(test_file)
        assert size == len(test_content.encode())
    
    @pytest.mark.unit
    def test_path_basename(self):
        """Test path_basename function"""
        assert path_basename('/path/to/file.txt') == 'file.txt'
        assert path_basename('file.txt') == 'file.txt'
        assert path_basename(Path('/path/to/file.txt')) == 'file.txt'


class TestGLBOptimizerInitialization:
    """Test GLBOptimizer initialization and configuration"""
    
    @pytest.mark.unit
    def test_optimizer_initialization(self, mock_environment_variables):
        """Test GLBOptimizer initialization with different quality levels"""
        with patch('optimizer.OptimizationConfig.from_env') as mock_config:
            config = MagicMock()
            config.get_quality_settings.return_value = {'description': 'test'}
            config.to_dict.return_value = {'test': 'config'}
            mock_config.return_value = config
            
            optimizer = GLBOptimizer(quality_level='high')
            assert optimizer.quality_level == 'high'
            
            optimizer = GLBOptimizer(quality_level='balanced')
            assert optimizer.quality_level == 'balanced'
            
            optimizer = GLBOptimizer(quality_level='maximum_compression')
            assert optimizer.quality_level == 'maximum_compression'
    
    @pytest.mark.unit
    def test_context_manager(self, mock_environment_variables):
        """Test GLBOptimizer context manager functionality"""
        with patch('optimizer.OptimizationConfig.from_env') as mock_config:
            config = MagicMock()
            config.get_quality_settings.return_value = {'description': 'test'}
            config.to_dict.return_value = {'test': 'config'}
            mock_config.return_value = config
            
            with GLBOptimizer() as optimizer:
                assert optimizer._secure_temp_dir is not None
                assert Path(optimizer._secure_temp_dir).exists()
                temp_dir = optimizer._secure_temp_dir
            
            # After context exit, cleanup should have occurred
            # Note: Directory might still exist but should be cleaned
    
    @pytest.mark.unit
    def test_environment_validation(self, mock_environment_variables):
        """Test environment validation during initialization"""
        with patch('optimizer.OptimizationConfig.from_env') as mock_config:
            config = MagicMock()
            config.get_quality_settings.return_value = {'description': 'test'}
            config.to_dict.return_value = {'test': 'config'}
            mock_config.return_value = config
            
            # Should not raise exception with valid environment
            optimizer = GLBOptimizer()
            assert optimizer is not None


class TestGLBValidation:
    """Test GLB file validation methods"""
    
    @pytest.mark.unit
    def test_glb_header_validation_valid(self, optimizer_with_temp_dirs, minimal_glb_file):
        """Test GLB header validation with valid file"""
        optimizer = optimizer_with_temp_dirs
        
        # Mock file size validation to allow the test file
        with patch.object(optimizer, '_validate_file_size') as mock_size_check:
            mock_size_check.return_value = {'success': True}
            
            result = optimizer.validate_glb(minimal_glb_file, mode='header')
            assert result['success'] is True
            assert 'version' in result
            assert result['version'] == 2
    
    @pytest.mark.unit
    def test_glb_header_validation_invalid_magic(self, optimizer_with_temp_dirs, temp_dir):
        """Test GLB header validation with invalid magic number"""
        optimizer = optimizer_with_temp_dirs
        
        invalid_file = Path(temp_dir) / 'invalid.glb'
        with open(invalid_file, 'wb') as f:
            f.write(b'BLTF')  # Wrong magic
            f.write((2).to_bytes(4, 'little'))
            f.write((100).to_bytes(4, 'little'))
        
        with patch.object(optimizer, '_validate_file_size') as mock_size_check:
            mock_size_check.return_value = {'success': True}
            
            result = optimizer.validate_glb(str(invalid_file), mode='header')
            assert result['success'] is False
            assert 'magic number' in result['error'].lower()
    
    @pytest.mark.unit
    def test_glb_header_validation_wrong_version(self, optimizer_with_temp_dirs, temp_dir):
        """Test GLB header validation with wrong version"""
        optimizer = optimizer_with_temp_dirs
        
        invalid_file = Path(temp_dir) / 'wrong_version.glb'
        with open(invalid_file, 'wb') as f:
            f.write(b'glTF')
            f.write((99).to_bytes(4, 'little'))  # Wrong version
            f.write((100).to_bytes(4, 'little'))
        
        with patch.object(optimizer, '_validate_file_size') as mock_size_check:
            mock_size_check.return_value = {'success': True}
            
            result = optimizer.validate_glb(str(invalid_file), mode='header')
            assert result['success'] is False
            assert 'version' in result['error'].lower()
    
    @pytest.mark.unit
    def test_glb_header_validation_truncated(self, optimizer_with_temp_dirs, temp_dir):
        """Test GLB header validation with truncated file"""
        optimizer = optimizer_with_temp_dirs
        
        truncated_file = Path(temp_dir) / 'truncated.glb'
        with open(truncated_file, 'wb') as f:
            f.write(b'glTF')
            # File ends here (truncated)
        
        with patch.object(optimizer, '_validate_file_size') as mock_size_check:
            mock_size_check.return_value = {'success': True}
            
            result = optimizer.validate_glb(str(truncated_file), mode='header')
            assert result['success'] is False
            assert 'truncated' in result['error'].lower() or 'corrupted' in result['error'].lower()
    
    @pytest.mark.unit
    def test_file_size_validation(self, optimizer_with_temp_dirs, large_glb_file):
        """Test file size validation"""
        optimizer = optimizer_with_temp_dirs
        
        result = optimizer._validate_file_size(large_glb_file)
        # Should fail due to large size
        assert result['success'] is False
        assert 'too large' in result['error'].lower()
    
    @pytest.mark.unit
    def test_file_size_validation_empty(self, optimizer_with_temp_dirs, temp_dir):
        """Test file size validation with empty file"""
        optimizer = optimizer_with_temp_dirs
        
        empty_file = Path(temp_dir) / 'empty.glb'
        empty_file.touch()
        
        result = optimizer._validate_file_size(str(empty_file))
        assert result['success'] is False
        assert 'too small' in result['error'].lower()


class TestSubprocessExecution:
    """Test subprocess execution methods"""
    
    @pytest.mark.unit
    def test_run_subprocess_success(self, optimizer_with_temp_dirs, mock_subprocess):
        """Test successful subprocess execution"""
        optimizer = optimizer_with_temp_dirs
        
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = 'success output'
        mock_subprocess.return_value.stderr = ''
        
        result = optimizer._run_subprocess(['echo', 'test'], 'test_step', 'test description')
        
        assert result['success'] is True
        assert result['stdout'] == 'success output'
        assert result['step_name'] == 'test_step'
    
    @pytest.mark.unit
    def test_run_subprocess_failure(self, optimizer_with_temp_dirs, mock_subprocess):
        """Test failed subprocess execution"""
        optimizer = optimizer_with_temp_dirs
        
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stdout = ''
        mock_subprocess.return_value.stderr = 'error occurred'
        
        result = optimizer._run_subprocess(['false'], 'test_step', 'test description')
        
        assert result['success'] is False
        assert 'error occurred' in result['stderr']
    
    @pytest.mark.unit
    def test_run_subprocess_timeout(self, optimizer_with_temp_dirs):
        """Test subprocess timeout handling"""
        optimizer = optimizer_with_temp_dirs
        
        with patch('optimizer.subprocess.run') as mock_run:
            import subprocess
            mock_run.side_effect = subprocess.TimeoutExpired(['sleep', '10'], 1)
            
            result = optimizer._run_subprocess(['sleep', '10'], 'test_step', 'test description', timeout=1)
            
            assert result['success'] is False
            assert 'timeout' in result['error'].lower()
    
    @pytest.mark.unit
    def test_get_safe_environment(self, optimizer_with_temp_dirs):
        """Test safe environment generation"""
        optimizer = optimizer_with_temp_dirs
        
        env = optimizer._get_safe_environment()
        
        # Should have basic required variables
        assert 'PATH' in env
        assert 'HOME' in env
        
        # Should not have dangerous variables
        dangerous_vars = ['LD_PRELOAD', 'PYTHONPATH', 'LD_LIBRARY_PATH']
        for var in dangerous_vars:
            assert var not in env


class TestErrorAnalysis:
    """Test error analysis and reporting methods"""
    
    @pytest.mark.unit
    def test_analyze_error_timeout(self, optimizer_with_temp_dirs):
        """Test error analysis for timeout errors"""
        optimizer = optimizer_with_temp_dirs
        
        stderr = 'Process terminated due to timeout'
        stdout = ''
        
        analysis = optimizer._analyze_error(stderr, stdout, 'test_step')
        
        assert 'timeout' in analysis['category'].lower()
        assert 'explanation' in analysis
    
    @pytest.mark.unit
    def test_analyze_error_memory(self, optimizer_with_temp_dirs):
        """Test error analysis for memory errors"""
        optimizer = optimizer_with_temp_dirs
        
        stderr = 'out of memory error occurred'
        stdout = ''
        
        analysis = optimizer._analyze_error(stderr, stdout, 'test_step')
        
        assert 'memory' in analysis['category'].lower()
    
    @pytest.mark.unit
    def test_analyze_error_file_not_found(self, optimizer_with_temp_dirs):
        """Test error analysis for file not found errors"""
        optimizer = optimizer_with_temp_dirs
        
        stderr = 'No such file or directory'
        stdout = ''
        
        analysis = optimizer._analyze_error(stderr, stdout, 'test_step')
        
        assert 'file' in analysis['category'].lower()
    
    @pytest.mark.unit
    def test_get_detailed_logs(self, optimizer_with_temp_dirs):
        """Test detailed log generation"""
        optimizer = optimizer_with_temp_dirs
        
        # Add some log entries
        optimizer.detailed_logs.extend([
            {'step': 'test1', 'success': True, 'message': 'success'},
            {'step': 'test2', 'success': False, 'error': 'failure'}
        ])
        
        logs = optimizer.get_detailed_logs()
        
        assert 'test1' in logs
        assert 'test2' in logs
        assert 'success' in logs
        assert 'failure' in logs
    
    @pytest.mark.unit
    def test_get_detailed_logs_json(self, optimizer_with_temp_dirs):
        """Test detailed log JSON generation"""
        optimizer = optimizer_with_temp_dirs
        
        optimizer.detailed_logs.extend([
            {'step': 'test1', 'success': True, 'message': 'success'},
            {'step': 'test2', 'success': False, 'error': 'failure'}
        ])
        
        logs_json = optimizer.get_detailed_logs_json()
        
        assert isinstance(logs_json, dict)
        assert 'logs' in logs_json
        assert 'summary' in logs_json
        assert len(logs_json['logs']) == 2


class TestAtomicOperations:
    """Test atomic file operations"""
    
    @pytest.mark.unit
    def test_atomic_write_success(self, optimizer_with_temp_dirs, temp_dir):
        """Test successful atomic write operation"""
        optimizer = optimizer_with_temp_dirs
        
        temp_file = Path(temp_dir) / 'temp.glb'
        final_file = Path(temp_dir) / 'final.glb'
        
        # Create valid GLB content
        json_data = b'{"asset":{"version":"2.0"}}'
        json_length = len(json_data)
        padding = (4 - (json_length % 4)) % 4
        json_data += b' ' * padding
        json_length = len(json_data)
        total_size = 12 + 8 + json_length
        
        with open(temp_file, 'wb') as f:
            f.write(b'glTF')
            f.write((2).to_bytes(4, 'little'))
            f.write(total_size.to_bytes(4, 'little'))
            f.write(json_length.to_bytes(4, 'little'))
            f.write(b'JSON')
            f.write(json_data)
        
        result = optimizer._atomic_write(str(temp_file), str(final_file))
        
        assert result['success'] is True
        assert final_file.exists()
        assert not temp_file.exists()
    
    @pytest.mark.unit
    def test_atomic_write_invalid_glb(self, optimizer_with_temp_dirs, temp_dir):
        """Test atomic write with invalid GLB file"""
        optimizer = optimizer_with_temp_dirs
        
        temp_file = Path(temp_dir) / 'temp.glb'
        final_file = Path(temp_dir) / 'final.glb'
        
        # Create invalid GLB content
        temp_file.write_text('invalid glb content')
        
        result = optimizer._atomic_write(str(temp_file), str(final_file))
        
        assert result['success'] is False
        assert not final_file.exists()


class TestPerformanceMetrics:
    """Test performance metrics generation"""
    
    @pytest.mark.unit
    def test_gpu_memory_estimation(self, optimizer_with_temp_dirs):
        """Test GPU memory savings estimation"""
        optimizer = optimizer_with_temp_dirs
        
        original_size = 10 * 1024 * 1024  # 10MB
        compressed_size = 2 * 1024 * 1024  # 2MB
        
        savings = optimizer._estimate_gpu_memory_savings(original_size, compressed_size)
        
        assert savings > 0
        assert savings < 100  # Should be a percentage
    
    @pytest.mark.unit
    def test_performance_report_generation(self, optimizer_with_temp_dirs, minimal_glb_file, temp_dir):
        """Test performance report generation"""
        optimizer = optimizer_with_temp_dirs
        
        output_file = Path(temp_dir) / 'output.glb'
        output_file.write_bytes(b'small content')  # Smaller than input
        
        report = optimizer._generate_performance_report(
            minimal_glb_file, str(output_file), processing_time=5.0
        )
        
        assert 'original_size' in report
        assert 'compressed_size' in report
        assert 'compression_ratio' in report
        assert 'processing_time' in report
        assert 'gpu_memory_savings' in report
    
    @pytest.mark.unit
    def test_optimization_methods_tracking(self, optimizer_with_temp_dirs):
        """Test optimization methods tracking"""
        optimizer = optimizer_with_temp_dirs
        
        methods = optimizer._get_optimization_methods_used()
        
        assert isinstance(methods, list)
        # Should include expected methods based on quality level
        assert len(methods) > 0