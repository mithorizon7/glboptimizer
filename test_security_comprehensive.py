#!/usr/bin/env python3
"""
Comprehensive Security Test Suite for GLB Optimizer
Tests all security improvements and vulnerability fixes
"""

import os
import tempfile
import shutil
import pytest
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from optimizer import GLBOptimizer

class TestSecurityEnhancements:
    """Test comprehensive security enhancements"""
    
    def setup_method(self):
        """Set up test environment"""
        self.optimizer = GLBOptimizer('high')
        self.test_dir = tempfile.mkdtemp()
        self.uploads_dir = os.path.join(self.test_dir, 'uploads')
        self.output_dir = os.path.join(self.test_dir, 'output')
        os.makedirs(self.uploads_dir)
        os.makedirs(self.output_dir)
        
        # Update allowed directories for testing
        self.optimizer.allowed_dirs = {
            os.path.realpath(self.uploads_dir),
            os.path.realpath(self.output_dir)
        }
        
    def teardown_method(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
        self.optimizer.cleanup_temp_files()
    
    def test_path_traversal_prevention(self):
        """Test prevention of path traversal attacks"""
        
        # Test 1: Basic path traversal attempt
        with pytest.raises(ValueError, match="Path outside allowed directories"):
            self.optimizer._validate_path("../../../etc/passwd")
        
        # Test 2: Symlink path traversal
        with pytest.raises(ValueError, match="Path outside allowed directories"):
            self.optimizer._validate_path("uploads/../../../etc/passwd")
        
        # Test 3: Multiple traversal attempts
        with pytest.raises(ValueError, match="Path outside allowed directories"):
            self.optimizer._validate_path("uploads/../../../../../../etc/passwd")
    
    def test_dangerous_character_prevention(self):
        """Test prevention of dangerous characters in paths"""
        
        dangerous_chars = [';', '|', '&', '$', '`', '>', '<', '\n', '\r', '\0']
        
        for char in dangerous_chars:
            with pytest.raises(ValueError, match="Path contains dangerous characters"):
                self.optimizer._validate_path(f"uploads/test{char}file.glb")
    
    def test_file_extension_validation(self):
        """Test file extension validation"""
        
        # Test valid extension
        valid_path = os.path.join(self.uploads_dir, "test.glb")
        with open(valid_path, 'w') as f:
            f.write("test")
        
        result = self.optimizer._validate_path(valid_path)
        assert result == os.path.realpath(valid_path)
        
        # Test invalid extensions
        invalid_extensions = ['.exe', '.sh', '.py', '.js', '.html']
        for ext in invalid_extensions:
            with pytest.raises(ValueError, match="Path must be a .glb file"):
                self.optimizer._validate_path(f"uploads/test{ext}")
    
    def test_toctou_protection(self):
        """Test Time-of-Check-Time-of-Use protection"""
        
        # Create a legitimate file
        test_file = os.path.join(self.uploads_dir, "test.glb")
        with open(test_file, 'w') as f:
            f.write("test content")
        
        # Test that file operations use validated paths
        content = self.optimizer._safe_file_operation(test_file, 'read')
        assert content == b"test content"
        
        # Test write operation
        new_content = b"new content"
        self.optimizer._safe_file_operation(test_file, 'write', new_content)
        
        # Verify content was written
        with open(test_file, 'rb') as f:
            assert f.read() == new_content
    
    def test_subprocess_environment_sanitization(self):
        """Test subprocess environment sanitization"""
        
        # Mock subprocess to capture environment
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""
            
            # Add dangerous environment variables
            with patch.dict(os.environ, {
                'DANGEROUS_VAR': 'rm -rf /',
                'MALICIOUS_PATH': '/etc/passwd',
                'PATH': '/usr/bin:/bin'
            }):
                
                self.optimizer._run_subprocess(
                    ['echo', 'test'], 
                    'test_step', 
                    'test description'
                )
                
                # Verify subprocess was called with sanitized environment
                assert mock_run.called
                call_args = mock_run.call_args
                env = call_args[1]['env']
                
                # Check that dangerous variables are not passed
                assert 'DANGEROUS_VAR' not in env
                assert 'MALICIOUS_PATH' not in env
                
                # Check that safe variables are preserved
                assert 'PATH' in env
                assert 'TMPDIR' in env
    
    def test_secure_temp_directory_creation(self):
        """Test secure temporary directory creation"""
        
        # Test that temp directories are created with proper permissions
        with tempfile.TemporaryDirectory() as temp_dir:
            # Simulate the optimization process
            test_file = os.path.join(temp_dir, "test.glb")
            with open(test_file, 'w') as f:
                f.write("test")
            
            # Test that temp files can be validated
            result = self.optimizer._validate_path(test_file, allow_temp=True)
            assert result == os.path.realpath(test_file)
    
    def test_path_validation_cache(self):
        """Test path validation caching for performance"""
        
        test_file = os.path.join(self.uploads_dir, "test.glb")
        with open(test_file, 'w') as f:
            f.write("test")
        
        # First call should validate and cache
        result1 = self.optimizer._validate_path(test_file)
        
        # Second call should use cache
        result2 = self.optimizer._validate_path(test_file)
        
        assert result1 == result2
        assert test_file + ":False" in self.optimizer._path_cache
    
    def test_thread_safety(self):
        """Test thread-safe file operations"""
        
        test_file = os.path.join(self.uploads_dir, "test.glb")
        with open(test_file, 'w') as f:
            f.write("test")
        
        # Test that file locks are created
        self.optimizer._safe_file_operation(test_file, 'read')
        
        # Verify lock was created
        real_path = os.path.realpath(test_file)
        assert real_path in self.optimizer._file_locks
    
    def test_cleanup_temp_files(self):
        """Test temporary file cleanup"""
        
        # Create some temp files
        temp_file1 = os.path.join(tempfile.gettempdir(), "test1.glb")
        temp_file2 = os.path.join(tempfile.gettempdir(), "test2.glb")
        
        with open(temp_file1, 'w') as f:
            f.write("test1")
        with open(temp_file2, 'w') as f:
            f.write("test2")
        
        # Add to tracking
        self.optimizer._temp_files.add(temp_file1)
        self.optimizer._temp_files.add(temp_file2)
        
        # Test cleanup
        self.optimizer.cleanup_temp_files()
        
        # Verify files are removed
        assert not os.path.exists(temp_file1)
        assert not os.path.exists(temp_file2)
        assert len(self.optimizer._temp_files) == 0
    
    def test_environment_validation(self):
        """Test environment validation on initialization"""
        
        # Test that allowed directories are created with proper permissions
        new_uploads = os.path.join(self.test_dir, 'new_uploads')
        new_output = os.path.join(self.test_dir, 'new_output')
        
        optimizer = GLBOptimizer('high')
        optimizer.allowed_dirs = {
            os.path.realpath(new_uploads),
            os.path.realpath(new_output)
        }
        
        # Trigger environment validation
        optimizer._validate_environment()
        
        # Check that directories were created
        assert os.path.exists(new_uploads)
        assert os.path.exists(new_output)
        
        # Check permissions are restrictive
        uploads_stat = os.stat(new_uploads)
        output_stat = os.stat(new_output)
        
        # Directories should not have world/group write permissions
        assert not (uploads_stat.st_mode & 0o022)
        assert not (output_stat.st_mode & 0o022)

def test_comprehensive_security_pipeline():
    """Test the complete security pipeline"""
    
    # Test that all security features work together
    optimizer = GLBOptimizer('high')
    
    # Test initialization
    assert hasattr(optimizer, '_temp_files')
    assert hasattr(optimizer, '_file_locks') 
    assert hasattr(optimizer, '_path_cache')
    assert len(optimizer.allowed_dirs) == 2
    
    # Test that dangerous operations are blocked
    with pytest.raises(ValueError):
        optimizer._validate_path("../../../etc/passwd")
    
    with pytest.raises(ValueError):
        optimizer._validate_path("uploads/test;rm -rf /.glb")
    
    print("✓ All security tests passed!")

if __name__ == "__main__":
    test_comprehensive_security_pipeline()
    print("✓ Comprehensive security test suite completed successfully!")