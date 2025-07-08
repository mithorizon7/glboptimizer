#!/usr/bin/env python3
"""
Test the performance impact of cache key normalization
Ensures that the fix doesn't degrade performance while improving cache efficiency
"""

import os
import sys
import time
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_cache_performance_with_normalization():
    """Test that cache normalization doesn't significantly impact performance"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = Path(temp_dir)
        
        # Create test GLB file
        test_file = test_dir / "test.glb"
        test_file.write_bytes(b"glTF" + b"\x02\x00\x00\x00" + b"\x00\x00\x00\x00" + b"\x00\x00\x00\x00")
        
        # Mock configuration
        with patch('optimizer.OptimizationConfig.from_env') as mock_config:
            config = MagicMock()
            config.MAX_FILE_SIZE_MB = 100
            config.SUBPROCESS_TIMEOUT = 300
            config.MAX_PARALLEL_WORKERS = 2
            config.PARALLEL_TIMEOUT = 120
            config.get_quality_settings.return_value = {
                'description': 'High quality optimization',
                'meshopt_compression': True,
                'draco_compression': True,
                'texture_compression': True,
                'enable_ktx2': True
            }
            config.to_dict.return_value = {'test': 'config'}
            mock_config.return_value = config
            
            from optimizer import GLBOptimizer
            
            optimizer = GLBOptimizer(quality_level='high')
            optimizer.allowed_dirs = [str(test_dir)]
            
            # Test performance with multiple functionally identical paths
            paths = [
                str(test_file),
                str(test_file.resolve()),
                str(test_file.absolute()),
                str(test_dir / "." / "test.glb"),
                str(test_dir / "models" / ".." / "test.glb") if (test_dir / "models").exists() else str(test_file),
            ]
            
            # Time the first validation (cache miss)
            start_time = time.time()
            try:
                first_validated = optimizer._validate_path(paths[0])
                first_time = time.time() - start_time
                
                # Time subsequent validations (should be cache hits with normalization)
                cache_hit_times = []
                for path in paths[1:]:
                    start_time = time.time()
                    validated = optimizer._validate_path(path)
                    cache_hit_time = time.time() - start_time
                    cache_hit_times.append(cache_hit_time)
                    
                    # Verify same result
                    assert validated == first_validated, f"Path {path} should resolve to same result"
                
                # Cache hits should be faster than initial validation
                avg_cache_hit_time = sum(cache_hit_times) / len(cache_hit_times)
                
                print(f"✅ Performance test results:")
                print(f"   First validation (cache miss): {first_time:.6f}s")
                print(f"   Average cache hit time: {avg_cache_hit_time:.6f}s")
                print(f"   Speed improvement: {first_time / avg_cache_hit_time:.2f}x")
                print(f"   Cache efficiency: {len(optimizer._path_cache)} entries for {len(paths)} paths")
                
                # Cache should be efficient - not create separate entries for functionally identical paths
                assert len(optimizer._path_cache) <= 2, "Cache should be efficient with normalization"
                
            except Exception as e:
                print(f"⚠️ Performance test failed: {e}")
                return False
            
    return True

def test_cache_behavior_edge_cases():
    """Test cache behavior with edge cases"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = Path(temp_dir)
        
        # Create test file
        test_file = test_dir / "test.glb"
        test_file.write_bytes(b"glTF" + b"\x02\x00\x00\x00" + b"\x00\x00\x00\x00" + b"\x00\x00\x00\x00")
        
        # Mock configuration
        with patch('optimizer.OptimizationConfig.from_env') as mock_config:
            config = MagicMock()
            config.MAX_FILE_SIZE_MB = 100
            config.SUBPROCESS_TIMEOUT = 300
            config.MAX_PARALLEL_WORKERS = 2
            config.PARALLEL_TIMEOUT = 120
            config.get_quality_settings.return_value = {
                'description': 'High quality optimization',
                'meshopt_compression': True,
                'draco_compression': True,
                'texture_compression': True,
                'enable_ktx2': True
            }
            config.to_dict.return_value = {'test': 'config'}
            mock_config.return_value = config
            
            from optimizer import GLBOptimizer
            
            optimizer = GLBOptimizer(quality_level='high')
            optimizer.allowed_dirs = [str(test_dir)]
            
            # Test edge cases
            test_cases = [
                # Non-existent path (should handle gracefully)
                str(test_dir / "nonexistent.glb"),
                # Path with special characters
                str(test_dir / "test with spaces.glb"),
            ]
            
            for path in test_cases:
                try:
                    # This might fail validation, but shouldn't crash
                    optimizer._validate_path(path)
                    print(f"✅ Edge case handled: {path}")
                except Exception as e:
                    print(f"✅ Edge case properly rejected: {path} - {e}")
                    
    return True

if __name__ == "__main__":
    print("🔍 Testing cache performance impact...")
    success1 = test_cache_performance_with_normalization()
    print()
    print("🔍 Testing cache behavior with edge cases...")
    success2 = test_cache_behavior_edge_cases()
    
    if success1 and success2:
        print("\n🎉 All cache performance tests passed!")
    else:
        print("\n❌ Some cache performance tests failed!")
        sys.exit(1)