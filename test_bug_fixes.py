#!/usr/bin/env python3
"""
Test script to verify the bug fixes for production optimization errors
"""
import os
import tempfile
import shutil
from pathlib import Path

# Add the project root to the path
import sys
sys.path.insert(0, '.')

from optimizer import GLBOptimizer

def test_null_pointer_fix():
    """Test that the null pointer error in _atomic_write is fixed"""
    print("Testing null pointer fix...")
    
    # Create a temporary GLB file with proper header
    with tempfile.NamedTemporaryFile(suffix='.glb', delete=False) as temp_file:
        # Write a minimal GLB header
        temp_file.write(b'glTF')  # magic
        temp_file.write((2).to_bytes(4, byteorder='little'))  # version
        temp_file.write((12).to_bytes(4, byteorder='little'))  # length
        temp_file.flush()
        
        temp_path = temp_file.name
    
    try:
        with GLBOptimizer(quality_level='high') as optimizer:
            # Test validation that previously returned None
            result = optimizer._validate_glb_file(temp_path)
            print(f"Validation result: {result}")
            
            # Ensure it returns a dictionary, not None
            assert isinstance(result, dict), f"Expected dict, got {type(result)}"
            assert 'success' in result, "Result should have 'success' key"
            
            print("✓ Null pointer fix working correctly")
            return True
            
    except Exception as e:
        print(f"✗ Error in null pointer test: {e}")
        return False
    finally:
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def test_missing_tools_handling():
    """Test that missing tools are handled gracefully"""
    print("Testing missing tools handling...")
    
    try:
        with GLBOptimizer(quality_level='high') as optimizer:
            # Check that tools_status is set after initialization
            assert hasattr(optimizer, 'tools_status'), "tools_status should be set"
            print(f"Tool status: {optimizer.tools_status}")
            
            # Test that missing tool errors are handled gracefully
            result = optimizer._run_subprocess(['nonexistent_tool', '--version'], 
                                             "Test Missing Tool", 
                                             "Testing missing tool handling")
            
            print(f"Missing tool result: {result}")
            assert not result['success'], "Missing tool should return failure"
            assert 'not available' in result['error'], "Should mention tool not available"
            
            print("✓ Missing tools handling working correctly")
            return True
            
    except Exception as e:
        print(f"✗ Error in missing tools test: {e}")
        return False

def test_path_validation_for_temp_files():
    """Test that gltfpack temporary files are properly validated"""
    print("Testing path validation for temp files...")
    
    try:
        with GLBOptimizer(quality_level='high') as optimizer:
            # Test that gltfpack temp files are allowed
            test_paths = [
                "uploads/test.glb.tmp.1234",
                "output/model.tmp.5678",
                "output/test.glb.tmp.9999"
            ]
            
            for test_path in test_paths:
                try:
                    validated = optimizer._validate_path(test_path, allow_temp=True)
                    print(f"✓ Path validated: {test_path} -> {validated}")
                except ValueError as e:
                    print(f"✗ Path validation failed for {test_path}: {e}")
                    return False
            
            print("✓ Path validation for temp files working correctly")
            return True
            
    except Exception as e:
        print(f"✗ Error in path validation test: {e}")
        return False

def main():
    """Run all bug fix tests"""
    print("Running bug fix verification tests...")
    print("=" * 50)
    
    tests = [
        test_null_pointer_fix,
        test_missing_tools_handling,
        test_path_validation_for_temp_files
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            failed += 1
        print()
    
    print("=" * 50)
    print(f"Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All bug fixes are working correctly!")
    else:
        print(f"⚠️  {failed} tests failed - some issues may remain")
    
    return failed == 0

if __name__ == "__main__":
    main()