#!/usr/bin/env python3
"""
Comprehensive test suite for atomic write system
Tests GLB validation, atomic operations, and failure recovery
"""
import pytest
import os
import tempfile
import shutil
import struct
from unittest.mock import patch, MagicMock
from optimizer import GLBOptimizer

class TestAtomicWrites:
    """Test suite for atomic write functionality"""
    
    def setup_method(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp(prefix='test_atomic_')
        self.temp_file = os.path.join(self.test_dir, 'temp.glb')
        self.final_file = os.path.join(self.test_dir, 'final.glb')
    
    def teardown_method(self):
        """Clean up test environment"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def _create_valid_glb(self, filepath, json_content='{"asset":{"version":"2.0"}}'):
        """Create a valid GLB file for testing"""
        json_bytes = json_content.encode('utf-8')
        json_length = len(json_bytes)
        
        # Pad JSON to 4-byte boundary
        while json_length % 4 != 0:
            json_bytes += b' '
            json_length = len(json_bytes)
        
        total_length = 12 + 8 + json_length  # header + chunk header + json
        
        with open(filepath, 'wb') as f:
            # GLB header
            f.write(b'glTF')  # magic
            f.write(struct.pack('<I', 2))  # version
            f.write(struct.pack('<I', total_length))  # length
            
            # JSON chunk
            f.write(struct.pack('<I', json_length))  # chunk length
            f.write(b'JSON')  # chunk type
            f.write(json_bytes)  # chunk data
    
    def _create_invalid_glb(self, filepath, corruption_type='magic'):
        """Create an invalid GLB file for testing"""
        if corruption_type == 'magic':
            # Wrong magic number
            with open(filepath, 'wb') as f:
                f.write(b'FAKE' + b'\x00' * 28)
        elif corruption_type == 'version':
            # Invalid version
            with open(filepath, 'wb') as f:
                f.write(b'glTF')
                f.write(struct.pack('<I', 999))  # invalid version
                f.write(b'\x00' * 24)
        elif corruption_type == 'truncated':
            # Truncated file
            with open(filepath, 'wb') as f:
                f.write(b'glTF\x02\x00\x00\x00')  # Only 8 bytes
    
    def test_glb_validation_valid_file(self):
        """Test GLB validation with valid files"""
        self._create_valid_glb(self.temp_file)
        
        with GLBOptimizer() as optimizer:
            result = optimizer._validate_glb_file(self.temp_file)
            
            assert result['success'] is True
            assert result['version'] == 2
            assert result['file_size'] > 0
            assert result['chunk_length'] > 0
            print(f"Valid GLB: version={result['version']}, size={result['file_size']}")
    
    def test_glb_validation_invalid_magic(self):
        """Test GLB validation with invalid magic number"""
        self._create_invalid_glb(self.temp_file, 'magic')
        
        with GLBOptimizer() as optimizer:
            result = optimizer._validate_glb_file(self.temp_file)
            
            assert result['success'] is False
            assert 'magic number' in result['error'].lower()
            assert 'user_message' in result
            print(f"Invalid magic detected: {result['error']}")
    
    def test_glb_validation_invalid_version(self):
        """Test GLB validation with invalid version"""
        self._create_invalid_glb(self.temp_file, 'version')
        
        with GLBOptimizer() as optimizer:
            result = optimizer._validate_glb_file(self.temp_file)
            
            assert result['success'] is False
            assert 'version' in result['error'].lower()
            print(f"Invalid version detected: {result['error']}")
    
    def test_glb_validation_truncated_file(self):
        """Test GLB validation with truncated file"""
        self._create_invalid_glb(self.temp_file, 'truncated')
        
        with GLBOptimizer() as optimizer:
            result = optimizer._validate_glb_file(self.temp_file)
            
            assert result['success'] is False
            assert 'truncated' in result['error'].lower() or 'header' in result['error'].lower()
            print(f"Truncated file detected: {result['error']}")
    
    def test_atomic_write_success(self):
        """Test successful atomic write operation"""
        self._create_valid_glb(self.temp_file)
        
        with GLBOptimizer() as optimizer:
            result = optimizer._atomic_write(self.temp_file, self.final_file)
            
            assert result['success'] is True
            assert os.path.exists(self.final_file)
            assert result['file_size'] > 0
            
            # Verify final file is valid GLB
            validation = optimizer._validate_glb_file(self.final_file)
            assert validation['success'] is True
            print(f"Atomic write successful: {result['file_size']} bytes")
    
    def test_atomic_write_invalid_source(self):
        """Test atomic write with invalid source file"""
        self._create_invalid_glb(self.temp_file, 'magic')
        
        with GLBOptimizer() as optimizer:
            result = optimizer._atomic_write(self.temp_file, self.final_file)
            
            assert result['success'] is False
            assert not os.path.exists(self.final_file)
            assert 'magic number' in result['error'].lower()
            print(f"Invalid source rejected: {result['error']}")
    
    def test_atomic_write_cross_platform_compatibility(self):
        """Test atomic write cross-platform compatibility"""
        self._create_valid_glb(self.temp_file)
        
        with GLBOptimizer() as optimizer:
            # Test POSIX path (os.replace)
            with patch('os.replace') as mock_replace:
                mock_replace.side_effect = None  # Success
                
                result = optimizer._atomic_write(self.temp_file, self.final_file)
                
                if hasattr(os, 'replace'):
                    mock_replace.assert_called_once_with(self.temp_file, self.final_file)
                    print("✓ POSIX atomic move tested")
            
            # Test Windows fallback (remove + rename)
            with patch('os.replace', side_effect=AttributeError):
                with patch('os.remove') as mock_remove:
                    with patch('os.rename') as mock_rename:
                        optimizer._atomic_write(self.temp_file, self.final_file)
                        print("✓ Windows fallback tested")
    
    def test_atomic_write_failure_recovery(self):
        """Test atomic write failure recovery"""
        self._create_valid_glb(self.temp_file)
        
        with GLBOptimizer() as optimizer:
            # Simulate write failure
            with patch('os.replace', side_effect=OSError("Disk full")):
                with patch('os.remove'):
                    with patch('os.rename', side_effect=OSError("Disk full")):
                        result = optimizer._atomic_write(self.temp_file, self.final_file)
                        
                        assert result['success'] is False
                        assert 'disk full' in result['error'].lower()
                        assert not os.path.exists(self.final_file)
                        print(f"Write failure handled: {result['error']}")
    
    def test_atomic_write_validation_after_move(self):
        """Test that files are validated after atomic move"""
        self._create_valid_glb(self.temp_file)
        
        with GLBOptimizer() as optimizer:
            # Mock validation to fail after move
            original_validate = optimizer._validate_glb_file
            
            def mock_validate(filepath):
                if filepath == self.final_file:
                    return {'success': False, 'error': 'Corrupted during move'}
                return original_validate(filepath)
            
            with patch.object(optimizer, '_validate_glb_file', side_effect=mock_validate):
                result = optimizer._atomic_write(self.temp_file, self.final_file)
                
                assert result['success'] is False
                assert 'corrupted during move' in result['error'].lower()
                print("✓ Post-move validation tested")
    
    def test_comprehensive_glb_structure_validation(self):
        """Test comprehensive GLB structure validation"""
        # Test various GLB structures
        test_cases = [
            ('valid_minimal', '{"asset":{"version":"2.0"}}'),
            ('valid_complex', '{"asset":{"version":"2.0"},"scene":0,"scenes":[{"nodes":[0]}]}'),
            ('invalid_json', '{"asset":{"version":"2.0"'),  # Malformed JSON
        ]
        
        for test_name, json_content in test_cases:
            test_file = os.path.join(self.test_dir, f'{test_name}.glb')
            
            if test_name.startswith('invalid'):
                # Create file with invalid JSON (won't be valid GLB)
                with open(test_file, 'wb') as f:
                    f.write(b'glTF' + b'\x00' * 28)
                expected_success = False
            else:
                self._create_valid_glb(test_file, json_content)
                expected_success = True
            
            with GLBOptimizer() as optimizer:
                result = optimizer._validate_glb_file(test_file)
                
                if expected_success:
                    assert result['success'] is True, f"Expected {test_name} to be valid"
                    print(f"✓ {test_name}: valid GLB structure")
                else:
                    assert result['success'] is False, f"Expected {test_name} to be invalid"
                    print(f"✓ {test_name}: invalid GLB structure detected")
    
    def test_temp_file_cleanup_in_atomic_write(self):
        """Test that temporary files are properly cleaned up"""
        self._create_valid_glb(self.temp_file)
        
        with GLBOptimizer() as optimizer:
            initial_temp_count = len(optimizer._temp_files)
            
            # Add temp file to tracking
            optimizer._temp_files.add(self.temp_file)
            
            result = optimizer._atomic_write(self.temp_file, self.final_file)
            
            # Temp file should be removed from tracking
            assert self.temp_file not in optimizer._temp_files
            print(f"✓ Temp file cleanup: {initial_temp_count} files tracked")
    
    def test_file_size_reporting_accuracy(self):
        """Test accurate file size reporting in atomic writes"""
        json_content = '{"asset":{"version":"2.0"}}'
        self._create_valid_glb(self.temp_file, json_content)
        
        expected_size = os.path.getsize(self.temp_file)
        
        with GLBOptimizer() as optimizer:
            result = optimizer._atomic_write(self.temp_file, self.final_file)
            
            assert result['success'] is True
            assert result['file_size'] == expected_size
            
            # Verify final file has same size
            final_size = os.path.getsize(self.final_file)
            assert final_size == expected_size
            print(f"✓ File size accuracy: {expected_size} bytes")

def test_atomic_write_integration():
    """Integration test for atomic write system"""
    print("\n=== Atomic Write Integration Test ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file = os.path.join(temp_dir, 'temp.glb')
        final_file = os.path.join(temp_dir, 'final.glb')
        
        # Create a comprehensive GLB file
        json_content = '{"asset":{"version":"2.0","generator":"Test"},"scene":0,"scenes":[{"nodes":[0]}],"nodes":[{"mesh":0}]}'
        
        with open(temp_file, 'wb') as f:
            json_bytes = json_content.encode('utf-8')
            while len(json_bytes) % 4 != 0:
                json_bytes += b' '
            
            total_length = 12 + 8 + len(json_bytes)
            
            f.write(b'glTF')
            f.write(struct.pack('<I', 2))
            f.write(struct.pack('<I', total_length))
            f.write(struct.pack('<I', len(json_bytes)))
            f.write(b'JSON')
            f.write(json_bytes)
        
        with GLBOptimizer() as optimizer:
            # Test complete atomic write workflow
            print(f"Source file size: {os.path.getsize(temp_file)} bytes")
            
            result = optimizer._atomic_write(temp_file, final_file)
            
            print(f"Atomic write result: {result}")
            
            if result['success']:
                print(f"✓ Final file size: {result['file_size']} bytes")
                print(f"✓ File exists: {os.path.exists(final_file)}")
                
                # Verify final file is valid
                validation = optimizer._validate_glb_file(final_file)
                print(f"✓ Final file validation: {validation['success']}")
                
                if validation['success']:
                    print(f"  - GLB version: {validation['version']}")
                    print(f"  - Chunk length: {validation['chunk_length']}")
            
            print("✓ Atomic write integration test completed")

if __name__ == '__main__':
    # Run the integration test directly
    test_atomic_write_integration()
    
    # Run pytest tests
    pytest.main([__file__, '-v'])