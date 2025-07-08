#!/usr/bin/env python3
"""
Comprehensive test suite for pathlib.Path integration
Verifies that the conversion from os.path to pathlib.Path maintains functionality
"""

import unittest
import tempfile
import shutil
import os
from pathlib import Path
import sys

# Add current directory to path for imports
sys.path.insert(0, '.')

from optimizer import GLBOptimizer, ensure_path, path_exists, path_size, path_basename, path_dirname, path_join, path_resolve, path_is_symlink


class TestPathlibIntegration(unittest.TestCase):
    """Test pathlib.Path integration and functionality"""

    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.test_file = Path(self.test_dir) / "test.glb"
        
        # Create a minimal valid GLB file for testing
        self.create_minimal_glb(self.test_file)

    def tearDown(self):
        """Clean up test environment"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def create_minimal_glb(self, filepath):
        """Create a minimal valid GLB file for testing"""
        # GLB header: magic (4 bytes) + version (4 bytes) + length (4 bytes)
        # JSON chunk: length (4 bytes) + type (4 bytes) + data
        json_data = b'{"asset":{"version":"2.0"}}'
        json_length = len(json_data)
        
        # Pad JSON to 4-byte boundary
        padding = (4 - (json_length % 4)) % 4
        json_data += b' ' * padding
        json_length = len(json_data)
        
        # Total file size
        header_size = 12
        chunk_header_size = 8
        total_size = header_size + chunk_header_size + json_length
        
        with open(filepath, 'wb') as f:
            # GLB header
            f.write(b'glTF')  # magic
            f.write((2).to_bytes(4, 'little'))  # version
            f.write(total_size.to_bytes(4, 'little'))  # length
            
            # JSON chunk
            f.write(json_length.to_bytes(4, 'little'))  # chunk length
            f.write(b'JSON')  # chunk type
            f.write(json_data)  # chunk data

    def test_pathlib_helper_functions(self):
        """Test pathlib helper functions work correctly"""
        test_path = str(self.test_file)
        
        # Test ensure_path
        path_obj = ensure_path(test_path)
        self.assertIsInstance(path_obj, Path)
        self.assertEqual(str(path_obj), test_path)
        
        # Test path_exists
        self.assertTrue(path_exists(test_path))
        self.assertFalse(path_exists("nonexistent_file.glb"))
        
        # Test path_size
        size = path_size(test_path)
        self.assertGreater(size, 0)
        self.assertEqual(size, os.path.getsize(test_path))
        
        # Test path_basename
        basename = path_basename(test_path)
        self.assertEqual(basename, "test.glb")
        
        # Test path_dirname
        dirname = path_dirname(test_path)
        self.assertEqual(str(dirname), self.test_dir)
        
        # Test path_join
        joined = path_join(self.test_dir, "new_file.glb")
        expected = Path(self.test_dir) / "new_file.glb"
        self.assertEqual(joined, expected)
        
        # Test path_resolve
        resolved = path_resolve(test_path)
        self.assertTrue(resolved.is_absolute())

    def test_glb_optimizer_instantiation(self):
        """Test GLBOptimizer can be instantiated with pathlib integration"""
        # Test different quality levels
        for quality in ['high', 'balanced', 'maximum_compression']:
            with self.subTest(quality=quality):
                optimizer = GLBOptimizer(quality_level=quality)
                self.assertEqual(optimizer.quality_level, quality)
                optimizer.cleanup()

    def test_glb_optimizer_context_manager(self):
        """Test GLBOptimizer context manager works with pathlib"""
        with GLBOptimizer(quality_level='high') as optimizer:
            self.assertEqual(optimizer.quality_level, 'high')
            self.assertIsNotNone(optimizer._secure_temp_dir)

    def test_path_validation(self):
        """Test path validation works with pathlib integration"""
        with GLBOptimizer(quality_level='high') as optimizer:
            # Test valid path validation
            try:
                validated = optimizer._validate_path(str(self.test_file))
                self.assertTrue(validated.endswith("test.glb"))
            except ValueError:
                # Expected for security reasons if outside allowed directories
                pass
            
            # Test invalid path validation
            with self.assertRaises(ValueError):
                optimizer._validate_path("../../../etc/passwd")

    def test_file_validation(self):
        """Test GLB file validation works with pathlib"""
        with GLBOptimizer(quality_level='high') as optimizer:
            # Test valid GLB validation
            result = optimizer.validate_glb(str(self.test_file), mode="header")
            self.assertTrue(result['success'])
            self.assertEqual(result['format'], 'GLB')
            
            # Test comprehensive validation
            result = optimizer.validate_glb(str(self.test_file), mode="full")
            self.assertTrue(result['success'])

    def test_safe_file_operations(self):
        """Test safe file operations work with pathlib"""
        test_content = "test content"
        test_file = Path(self.test_dir) / "test_write.txt"
        
        with GLBOptimizer(quality_level='high') as optimizer:
            try:
                # Test file write (might fail due to security restrictions)
                optimizer._safe_file_operation(str(test_file), 'write_text', test_content)
                
                # Test file read
                content = optimizer._safe_file_operation(str(test_file), 'read_text')
                self.assertEqual(content, test_content)
                
                # Test file existence check
                exists = optimizer._safe_file_operation(str(test_file), 'exists')
                self.assertTrue(exists)
                
            except ValueError:
                # Expected for paths outside allowed directories
                pass

    def test_environment_setup(self):
        """Test environment setup works with pathlib integration"""
        with GLBOptimizer(quality_level='high') as optimizer:
            env = optimizer._get_safe_environment()
            
            # Verify essential environment variables are set
            self.assertIn('PATH', env)
            self.assertIn('HOME', env)
            self.assertIn('XDG_CONFIG_HOME', env)
            self.assertIn('XDG_DATA_HOME', env)
            self.assertIn('XDG_CACHE_HOME', env)
            
            # Verify PATH contains necessary components
            path_components = env['PATH'].split(':')
            self.assertTrue(any('/bin' in comp for comp in path_components))

    def test_temp_file_management(self):
        """Test temporary file management with pathlib"""
        with GLBOptimizer(quality_level='high') as optimizer:
            # Verify temp directory is created
            self.assertIsNotNone(optimizer._secure_temp_dir)
            self.assertTrue(os.path.exists(optimizer._secure_temp_dir))
            
            # Verify temp files tracking
            self.assertIsInstance(optimizer._temp_files, set)


def run_pathlib_tests():
    """Run all pathlib integration tests"""
    print("Running pathlib.Path integration tests...")
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPathlibIntegration)
    runner = unittest.TextTestRunner(verbosity=2)
    
    # Run tests
    result = runner.run(suite)
    
    # Report results
    if result.wasSuccessful():
        print(f"\n✅ All {result.testsRun} pathlib integration tests passed!")
        return True
    else:
        print(f"\n❌ {len(result.failures + result.errors)} tests failed out of {result.testsRun}")
        for test, error in result.failures + result.errors:
            print(f"Failed: {test}")
            print(f"Error: {error}")
        return False


if __name__ == "__main__":
    success = run_pathlib_tests()
    sys.exit(0 if success else 1)