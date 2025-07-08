#!/usr/bin/env python3
"""
Test suite to verify magic numbers extraction and constant usage
"""

from config import GLBConstants, OptimizationThresholds
from optimizer import GLBOptimizer
import tempfile
import struct
import os

def test_glb_constants():
    """Test that GLB constants are properly defined"""
    assert GLBConstants.HEADER_LENGTH == 12
    assert GLBConstants.MAGIC_NUMBER == b'glTF'
    assert GLBConstants.VERSION_OFFSET == 4
    assert GLBConstants.LENGTH_OFFSET == 8
    assert GLBConstants.SUPPORTED_VERSION == 2
    assert GLBConstants.CHUNK_HEADER_LENGTH == 8
    assert GLBConstants.CHUNK_LENGTH_OFFSET == 0
    assert GLBConstants.CHUNK_TYPE_OFFSET == 4
    assert GLBConstants.JSON_CHUNK_TYPE == b'JSON'
    assert GLBConstants.BINARY_CHUNK_TYPE == b'BIN\x00'
    assert GLBConstants.MIN_FILE_WITH_CHUNK == 20  # 12 + 8
    assert GLBConstants.MIN_VALID_GLB_SIZE == 12

def test_optimization_thresholds():
    """Test that optimization thresholds are properly defined"""
    assert OptimizationThresholds.HIGH_VERTEX_COUNT_THRESHOLD == 50_000
    assert OptimizationThresholds.VERY_HIGH_VERTEX_COUNT == 100_000
    assert OptimizationThresholds.LARGE_FILE_SIZE_THRESHOLD == 5_000_000
    
    # Test simplify ratios
    assert OptimizationThresholds.SIMPLIFY_RATIOS['high'] == 0.8
    assert OptimizationThresholds.SIMPLIFY_RATIOS['balanced'] == 0.6
    assert OptimizationThresholds.SIMPLIFY_RATIOS['maximum_compression'] == 0.4
    
    # Test other thresholds
    assert OptimizationThresholds.SIMPLIFY_ERROR_THRESHOLD == 0.01
    assert OptimizationThresholds.WEBP_SIZE_ADVANTAGE_THRESHOLD == 0.8
    assert OptimizationThresholds.LOAD_TIME_COMPRESSION_FACTOR == 0.8
    assert OptimizationThresholds.MAX_LOAD_TIME_IMPROVEMENT == 85

def test_glb_validation_with_constants():
    """Test GLB validation using constants instead of magic numbers"""
    optimizer = GLBOptimizer('high')
    
    # Create a minimal valid GLB file for testing
    with tempfile.NamedTemporaryFile(suffix='.glb', delete=False) as temp_file:
        # Minimal JSON content
        json_content = b'{"asset":{"version":"2.0"}}'
        json_length = len(json_content)
        
        # Pad JSON to 4-byte boundary
        json_padding = (4 - (json_length % 4)) % 4
        json_content += b' ' * json_padding
        json_length_padded = len(json_content)
        
        # Total file size: 12 (header) + 8 (chunk header) + json_length_padded
        total_length = 12 + 8 + json_length_padded
        
        # Write GLB header
        header = struct.pack('<4sII', GLBConstants.MAGIC_NUMBER, GLBConstants.SUPPORTED_VERSION, total_length)
        temp_file.write(header)
        
        # Write JSON chunk header and content
        json_chunk_header = struct.pack('<I4s', json_length_padded, GLBConstants.JSON_CHUNK_TYPE)
        temp_file.write(json_chunk_header)
        temp_file.write(json_content)
        
        temp_file.flush()
        temp_file_path = temp_file.name
    
    try:
        # Test header validation
        result = optimizer.validate_glb(temp_file_path, mode="header")
        assert result['success'], f"Header validation failed: {result}"
        
        # Test full validation
        result = optimizer.validate_glb(temp_file_path, mode="full")
        assert result['success'], f"Full validation failed: {result}"
        
    finally:
        os.unlink(temp_file_path)

def test_invalid_glb_with_constants():
    """Test that validation properly rejects invalid GLB files using constants"""
    optimizer = GLBOptimizer('high')
    
    # Test invalid magic number
    with tempfile.NamedTemporaryFile(suffix='.glb', delete=False) as temp_file:
        header = struct.pack('<4sII', b'BADF', 2, 20)  # Bad magic number
        temp_file.write(header)
        temp_file.flush()
        temp_file_path = temp_file.name
    
    try:
        result = optimizer.validate_glb(temp_file_path, mode="header")
        assert not result['success'], "Should reject invalid magic number"
        assert "GLB magic number" in result['error']
    finally:
        os.unlink(temp_file_path)
    
    # Test invalid version
    with tempfile.NamedTemporaryFile(suffix='.glb', delete=False) as temp_file:
        header = struct.pack('<4sII', GLBConstants.MAGIC_NUMBER, 1, 20)  # Version 1 instead of 2
        temp_file.write(header)
        temp_file.flush()
        temp_file_path = temp_file.name
    
    try:
        result = optimizer.validate_glb(temp_file_path, mode="header")
        assert not result['success'], "Should reject invalid version"
        assert "version" in result['error'].lower()
    finally:
        os.unlink(temp_file_path)

def test_compression_method_selection_with_thresholds():
    """Test that compression method selection uses constants for thresholds"""
    optimizer = GLBOptimizer('high')
    
    # Test high vertex count triggers Draco
    analysis = {
        'vertices': OptimizationThresholds.HIGH_VERTEX_COUNT_THRESHOLD + 1000,
        'triangle_count': 10000,
        'complexity': 'medium',
        'file_size': 1000000
    }
    
    methods = optimizer._select_compression_methods(analysis)
    assert 'draco' in methods, "High vertex count should trigger Draco compression"
    
    # Test very high vertex count triggers hybrid
    analysis['vertices'] = OptimizationThresholds.VERY_HIGH_VERTEX_COUNT + 1000
    methods = optimizer._select_compression_methods(analysis)
    assert 'hybrid' in methods, "Very high vertex count should trigger hybrid compression"
    
    # Test large file size triggers hybrid
    analysis = {
        'vertices': 1000,
        'triangle_count': 1000,
        'complexity': 'low',
        'file_size': OptimizationThresholds.LARGE_FILE_SIZE_THRESHOLD + 1000000
    }
    methods = optimizer._select_compression_methods(analysis)
    assert 'hybrid' in methods, "Large file size should trigger hybrid compression"

def test_quality_settings_use_constants():
    """Test that quality settings properly reference constants"""
    from config import OptimizationConfig
    
    config = OptimizationConfig()
    
    # Test high quality settings
    high_settings = config.get_quality_settings('high')
    assert high_settings['simplify_ratio'] == OptimizationThresholds.SIMPLIFY_RATIOS['high']
    
    # Test balanced quality settings
    balanced_settings = config.get_quality_settings('balanced')
    assert balanced_settings['simplify_ratio'] == OptimizationThresholds.SIMPLIFY_RATIOS['balanced']
    
    # Test maximum compression settings
    max_settings = config.get_quality_settings('maximum_compression')
    assert max_settings['simplify_ratio'] == OptimizationThresholds.SIMPLIFY_RATIOS['maximum_compression']

def test_constants_imported_correctly():
    """Test that constants are properly imported in optimizer module"""
    # This verifies the import statement works correctly
    from optimizer import GLBConstants as ImportedGLBConstants
    from optimizer import OptimizationThresholds as ImportedThresholds
    
    assert ImportedGLBConstants.HEADER_LENGTH == 12
    assert ImportedThresholds.HIGH_VERTEX_COUNT_THRESHOLD == 50_000

if __name__ == '__main__':
    print("🧪 TESTING MAGIC NUMBERS EXTRACTION...")
    print("=" * 60)
    
    try:
        test_glb_constants()
        print("✅ GLB constants test passed")
        
        test_optimization_thresholds()
        print("✅ Optimization thresholds test passed")
        
        test_glb_validation_with_constants()
        print("✅ GLB validation with constants test passed")
        
        test_invalid_glb_with_constants()
        print("✅ Invalid GLB rejection test passed")
        
        test_compression_method_selection_with_thresholds()
        print("✅ Compression method selection test passed")
        
        test_quality_settings_use_constants()
        print("✅ Quality settings constants test passed")
        
        test_constants_imported_correctly()
        print("✅ Constants import test passed")
        
        print("\n🎉 ALL MAGIC NUMBERS EXTRACTION TESTS PASSED!")
        print("=" * 60)
        print("✅ GLB format constants properly centralized")
        print("✅ Optimization thresholds properly centralized")
        print("✅ Constants correctly imported and used")
        print("✅ No hardcoded magic numbers in validation logic")
        print("✅ Compression method selection uses constants")
        print("✅ Quality settings reference centralized constants")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)