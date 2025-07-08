#!/usr/bin/env python3
"""
Test suite for pathlib integration throughout the optimizer
"""

import os
import tempfile
from pathlib import Path
import pytest
from optimizer import GLBOptimizer, ensure_path, path_exists, path_size, path_basename, path_dirname, path_join, path_resolve, path_is_symlink


class TestPathlibHelpers:
    """Test all pathlib helper functions"""
    
    def test_ensure_path(self):
        """Test ensure_path converts strings and Path objects correctly"""
        # Test with string
        test_str = "/tmp/test.glb"
        result = ensure_path(test_str)
        assert isinstance(result, Path)
        assert str(result) == test_str
        
        # Test with Path object
        test_path = Path("/tmp/test.glb")
        result = ensure_path(test_path)
        assert isinstance(result, Path)
        assert result == test_path
    
    def test_path_exists(self):
        """Test path_exists works with both strings and Path objects"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Existing path
            assert path_exists(temp_dir) == True
            assert path_exists(Path(temp_dir)) == True
            
            # Non-existing path
            fake_path = Path(temp_dir) / "nonexistent"
            assert path_exists(fake_path) == False
            assert path_exists(str(fake_path)) == False
    
    def test_path_size(self):
        """Test path_size returns correct file sizes"""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file.flush()
            
            # Test with string path
            size = path_size(temp_file.name)
            assert size == 12  # "test content" is 12 bytes
            
            # Test with Path object
            size = path_size(Path(temp_file.name))
            assert size == 12
            
            # Cleanup
            os.unlink(temp_file.name)
    
    def test_path_basename(self):
        """Test path_basename extracts filename correctly"""
        test_path = "/tmp/folder/test.glb"
        assert path_basename(test_path) == "test.glb"
        assert path_basename(Path(test_path)) == "test.glb"
    
    def test_path_dirname(self):
        """Test path_dirname extracts directory correctly"""
        test_path = "/tmp/folder/test.glb"
        dirname = path_dirname(test_path)
        assert isinstance(dirname, Path)
        assert str(dirname) == "/tmp/folder"
        
        # Test with Path object
        dirname = path_dirname(Path(test_path))
        assert isinstance(dirname, Path)
        assert str(dirname) == "/tmp/folder"
    
    def test_path_join(self):
        """Test path_join creates correct paths"""
        result = path_join("tmp", "folder", "test.glb")
        assert isinstance(result, Path)
        # Check that it ends with the correct path (handles different OS separators)
        assert str(result).endswith("tmp/folder/test.glb") or str(result).endswith("tmp\\folder\\test.glb")
        
        # Test with mixed Path and string inputs
        result = path_join(Path("tmp"), "folder", "test.glb")
        assert isinstance(result, Path)
    
    def test_path_resolve(self):
        """Test path_resolve returns absolute paths"""
        with tempfile.TemporaryDirectory() as temp_dir:
            relative_path = os.path.relpath(temp_dir)
            resolved = path_resolve(relative_path)
            assert isinstance(resolved, Path)
            assert resolved.is_absolute()
            assert str(resolved) == os.path.abspath(temp_dir)
    
    def test_path_is_symlink(self):
        """Test path_is_symlink detects symlinks correctly"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a regular file
            regular_file = Path(temp_dir) / "regular.txt"
            regular_file.write_text("test")
            
            # Test regular file
            assert path_is_symlink(regular_file) == False
            assert path_is_symlink(str(regular_file)) == False
            
            # Create a symlink if the system supports it
            try:
                symlink_file = Path(temp_dir) / "symlink.txt"
                symlink_file.symlink_to(regular_file)
                
                # Test symlink
                assert path_is_symlink(symlink_file) == True
                assert path_is_symlink(str(symlink_file)) == True
            except OSError:
                # Skip symlink test if not supported on this system
                pass


class TestGLBOptimizerPathlibIntegration:
    """Test GLBOptimizer uses pathlib correctly throughout"""
    
    def test_context_manager_pathlib(self):
        """Test GLBOptimizer context manager with pathlib"""
        with GLBOptimizer() as optimizer:
            assert optimizer is not None
            # Test that secure temp directory is created as Path
            assert hasattr(optimizer, '_secure_temp_dir')
    
    def test_safe_file_operation_pathlib(self):
        """Test _safe_file_operation works with pathlib"""
        with tempfile.TemporaryDirectory() as temp_dir:
            optimizer = GLBOptimizer()
            
            # Test with string path
            test_file = str(Path(temp_dir) / "test.glb")
            exists = optimizer._safe_file_operation(test_file, 'exists')
            assert exists == False
            
            # Test with Path object
            exists = optimizer._safe_file_operation(Path(test_file), 'exists')
            assert exists == False
    
    def test_validate_path_pathlib(self):
        """Test path validation works with pathlib"""
        with tempfile.TemporaryDirectory() as temp_dir:
            optimizer = GLBOptimizer()
            
            # Test valid GLB file path
            test_file = str(Path(temp_dir) / "test.glb")
            validated = optimizer._validate_path(test_file, allow_temp=True)
            assert validated is not None
            assert isinstance(validated, str)  # Should return string for compatibility
            
            # Test that pathlib Path objects are handled
            validated = optimizer._validate_path(Path(test_file), allow_temp=True)
            assert validated is not None
    
    def test_immediate_path_validation_pathlib(self):
        """Test immediate path validation with pathlib"""
        with tempfile.TemporaryDirectory() as temp_dir:
            optimizer = GLBOptimizer()
            
            # Test with valid path
            test_file = str(Path(temp_dir) / "test.glb")
            validated = optimizer._immediate_path_validation(test_file, allow_temp=True)
            assert validated is not None
            
            # Test security - should block path traversal
            with pytest.raises(ValueError, match="Path traversal"):
                optimizer._immediate_path_validation("../../../etc/passwd", allow_temp=True)
    
    def test_cleanup_temp_files_pathlib(self):
        """Test cleanup works with pathlib"""
        with tempfile.TemporaryDirectory() as temp_dir:
            optimizer = GLBOptimizer()
            
            # Create a test file
            test_file = Path(temp_dir) / "temp_test.glb"
            test_file.write_text("test content")
            
            # Add to temp files tracking
            optimizer._temp_files.add(str(test_file))
            
            # Test cleanup
            optimizer.cleanup_temp_files()
            
            # File should be cleaned up
            assert not test_file.exists()


class TestPathlibSecurityFeatures:
    """Test that pathlib integration maintains security features"""
    
    def test_path_traversal_protection(self):
        """Test path traversal protection still works with pathlib"""
        optimizer = GLBOptimizer()
        
        # These should all be blocked
        dangerous_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/passwd",
            "C:\\Windows\\System32\\config\\sam"
        ]
        
        for dangerous_path in dangerous_paths:
            with pytest.raises(ValueError):
                optimizer._validate_path(dangerous_path)
    
    def test_symlink_protection(self):
        """Test symlink protection works with pathlib"""
        with tempfile.TemporaryDirectory() as temp_dir:
            optimizer = GLBOptimizer()
            
            # Create a file outside safe directory
            outside_file = Path(temp_dir) / "outside.txt"
            outside_file.write_text("sensitive data")
            
            # Try to create a symlink in uploads directory
            try:
                uploads_dir = Path("uploads")
                uploads_dir.mkdir(exist_ok=True)
                
                symlink_path = uploads_dir / "malicious.glb"
                if symlink_path.exists():
                    symlink_path.unlink()
                
                # Create symlink pointing to outside file
                symlink_path.symlink_to(outside_file)
                
                # This should be blocked by validation
                with pytest.raises(ValueError):
                    optimizer._validate_path(str(symlink_path))
                
                # Cleanup
                if symlink_path.exists():
                    symlink_path.unlink()
                    
            except OSError:
                # Skip symlink test if not supported on this system
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])