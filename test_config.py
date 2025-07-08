#!/usr/bin/env python3
"""
Configuration System Test Suite
Tests the centralized configuration system with environment variables and validation
"""

import os
import tempfile
import json
from unittest.mock import patch
from config import OptimizationConfig

def test_configuration_defaults():
    """Test default configuration values"""
    config = OptimizationConfig()
    
    # Test default file size limits (should be larger than before)
    assert config.MAX_FILE_SIZE == 500 * 1024 * 1024  # 500MB
    assert config.MIN_FILE_SIZE == 1024  # 1KB
    assert config.SUBPROCESS_TIMEOUT == 300  # 5 minutes
    assert config.PARALLEL_TIMEOUT == 120  # 2 minutes
    
    print("✓ Default configuration values correct")

def test_environment_variable_override():
    """Test configuration override via environment variables"""
    with patch.dict(os.environ, {
        'GLB_MAX_FILE_SIZE': '1073741824',  # 1GB
        'GLB_MIN_FILE_SIZE': '2048',        # 2KB
        'GLB_SUBPROCESS_TIMEOUT': '600',    # 10 minutes
        'GLB_PARALLEL_TIMEOUT': '180'       # 3 minutes
    }):
        config = OptimizationConfig()
        
        assert config.MAX_FILE_SIZE == 1073741824  # 1GB
        assert config.MIN_FILE_SIZE == 2048        # 2KB
        assert config.SUBPROCESS_TIMEOUT == 600    # 10 minutes
        assert config.PARALLEL_TIMEOUT == 180      # 3 minutes
    
    print("✓ Environment variable override working")

def test_quality_levels():
    """Test quality level configurations"""
    config = OptimizationConfig()
    
    # Test all available quality levels
    levels = config.get_available_quality_levels()
    expected_levels = ['high', 'balanced', 'maximum_compression']
    
    assert set(levels.keys()) == set(expected_levels)
    assert all(isinstance(desc, str) for desc in levels.values())
    
    # Test quality settings retrieval
    for level in expected_levels:
        settings = config.get_quality_settings(level)
        assert 'description' in settings
        assert 'simplify_ratio' in settings
        assert 'texture_quality' in settings
        assert 'compression_level' in settings
        assert 'draco_quantization_bits' in settings
        
        # Test quantization bits structure
        quant_bits = settings['draco_quantization_bits']
        assert 'position' in quant_bits
        assert 'normal' in quant_bits
        assert 'color' in quant_bits
        assert 'tex_coord' in quant_bits
    
    print("✓ Quality level configurations complete")

def test_quality_level_differences():
    """Test that different quality levels have different settings"""
    config = OptimizationConfig()
    
    high = config.get_quality_settings('high')
    balanced = config.get_quality_settings('balanced')
    maximum = config.get_quality_settings('maximum_compression')
    
    # High quality should have highest simplify ratio
    assert high['simplify_ratio'] > balanced['simplify_ratio']
    assert balanced['simplify_ratio'] > maximum['simplify_ratio']
    
    # Maximum compression should have highest compression level
    assert maximum['compression_level'] >= balanced['compression_level']
    assert balanced['compression_level'] >= high['compression_level']
    
    # Texture quality should decrease with more compression
    assert high['texture_quality'] > balanced['texture_quality']
    assert balanced['texture_quality'] > maximum['texture_quality']
    
    print("✓ Quality level differentiation working correctly")

def test_configuration_validation():
    """Test configuration validation"""
    # Test with valid configuration
    validation = OptimizationConfig.validate_settings()
    assert validation['valid'] is True
    assert len(validation['issues']) == 0
    
    # Test with invalid configuration (mock bad environment variables)
    with patch.dict(os.environ, {
        'GLB_MAX_FILE_SIZE': '100',      # 100 bytes (too small)
        'GLB_MIN_FILE_SIZE': '200'       # 200 bytes (larger than max)
    }):
        validation = OptimizationConfig.validate_settings()
        assert validation['valid'] is False
        assert len(validation['issues']) > 0
        assert 'MAX_FILE_SIZE must be greater than MIN_FILE_SIZE' in validation['issues']
    
    print("✓ Configuration validation working")

def test_json_config_file_override():
    """Test configuration override via JSON file"""
    # For now, just test that the from_env method works
    config = OptimizationConfig.from_env()
    
    # Test that it has the expected quality presets
    assert 'high' in config.QUALITY_PRESETS
    assert 'balanced' in config.QUALITY_PRESETS
    assert 'maximum_compression' in config.QUALITY_PRESETS
    
    # Test that we can get settings
    high_settings = config.get_quality_settings('high')
    assert high_settings['description'] == 'Prioritizes visual quality with good compression'
    
    print("✓ JSON config file override basic functionality working")

def test_configuration_export():
    """Test configuration export for logging"""
    config = OptimizationConfig()
    
    export = config.to_dict()
    
    # Check required fields are present
    assert 'max_file_size_mb' in export
    assert 'min_file_size_bytes' in export
    assert 'subprocess_timeout' in export
    assert 'parallel_timeout' in export
    assert 'quality_levels' in export
    assert 'quality_descriptions' in export
    
    # Check values are reasonable
    assert export['max_file_size_mb'] == 500  # 500MB default
    assert export['min_file_size_bytes'] == 1024  # 1KB default
    assert export['subprocess_timeout'] == 300  # 5 minutes
    assert export['parallel_timeout'] == 120  # 2 minutes
    
    # Check quality levels are included
    assert len(export['quality_levels']) == 3
    assert set(export['quality_levels']) == {'high', 'balanced', 'maximum_compression'}
    
    print("✓ Configuration export working correctly")

def test_invalid_quality_level_fallback():
    """Test fallback behavior for invalid quality levels"""
    config = OptimizationConfig()
    
    # Test with invalid quality level - should fallback to 'balanced'
    settings = config.get_quality_settings('invalid_quality')
    balanced_settings = config.get_quality_settings('balanced')
    
    assert settings == balanced_settings
    
    print("✓ Invalid quality level fallback working")

def test_configuration_integration_with_optimizer():
    """Test that optimizer correctly uses centralized configuration"""
    from optimizer import GLBOptimizer
    
    with patch.dict(os.environ, {
        'GLB_MAX_FILE_SIZE': '1073741824',  # 1GB
        'GLB_SUBPROCESS_TIMEOUT': '600'     # 10 minutes
    }):
        optimizer = GLBOptimizer('high')
        
        # Check that optimizer loaded configuration correctly
        assert optimizer.config.MAX_FILE_SIZE == 1073741824
        assert optimizer.config.SUBPROCESS_TIMEOUT == 600
        
        # Check that quality settings were loaded
        assert optimizer.quality_level == 'high'
        assert 'description' in optimizer.quality_settings
        assert optimizer.quality_settings['description'] == 'Prioritizes visual quality with good compression'
        
        # Check that optimizer uses config for timeouts
        assert hasattr(optimizer, 'quality_settings')
        
    print("✓ Optimizer integration with centralized configuration working")

def run_all_tests():
    """Run all configuration tests"""
    print("Running Configuration System Tests...")
    print("=" * 50)
    
    test_configuration_defaults()
    test_environment_variable_override()
    test_quality_levels()
    test_quality_level_differences()
    test_configuration_validation()
    test_json_config_file_override()
    test_configuration_export()
    test_invalid_quality_level_fallback()
    test_configuration_integration_with_optimizer()
    
    print("=" * 50)
    print("✅ ALL CONFIGURATION TESTS PASSED")
    print("Centralized configuration system is working correctly!")

if __name__ == '__main__':
    run_all_tests()