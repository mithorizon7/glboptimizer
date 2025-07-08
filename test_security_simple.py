#!/usr/bin/env python3
"""
Simple Security Test for GLB Optimizer
Tests security improvements without external dependencies
"""

import os
import tempfile
import shutil
from optimizer import GLBOptimizer

def test_path_traversal_prevention():
    """Test prevention of path traversal attacks"""
    optimizer = GLBOptimizer('high')
    
    # Test 1: Basic path traversal attempt
    try:
        optimizer._validate_path("../../../etc/passwd")
        print("✗ FAIL: Path traversal not blocked")
        return False
    except ValueError as e:
        if "Path outside allowed directories" in str(e):
            print("✓ PASS: Path traversal blocked")
        else:
            print(f"✗ FAIL: Wrong error: {e}")
            return False
    
    # Test 2: Dangerous characters
    try:
        optimizer._validate_path("uploads/test;rm -rf /.glb")
        print("✗ FAIL: Dangerous characters not blocked")
        return False
    except ValueError as e:
        if "dangerous characters" in str(e):
            print("✓ PASS: Dangerous characters blocked")
        else:
            print(f"✗ FAIL: Wrong error: {e}")
            return False
    
    # Test 3: File extension validation
    try:
        optimizer._validate_path("uploads/test.exe")
        print("✗ FAIL: Invalid extension not blocked")
        return False
    except ValueError as e:
        if "must be a .glb file" in str(e):
            print("✓ PASS: Invalid extension blocked")
        else:
            print(f"✗ FAIL: Wrong error: {e}")
            return False
    
    return True

def test_environment_sanitization():
    """Test environment variable sanitization"""
    optimizer = GLBOptimizer('high')
    
    # Test that initialization creates secure environment
    assert hasattr(optimizer, '_temp_files')
    assert hasattr(optimizer, '_file_locks')
    assert hasattr(optimizer, '_path_cache')
    
    print("✓ PASS: Security environment initialized")
    return True

def test_temp_file_validation():
    """Test temporary file validation"""
    optimizer = GLBOptimizer('high')
    
    # Create a temp file
    with tempfile.NamedTemporaryFile(suffix='.glb', delete=False) as f:
        temp_path = f.name
        f.write(b"test content")
    
    try:
        # Should validate successfully with allow_temp=True
        result = optimizer._validate_path(temp_path, allow_temp=True)
        print("✓ PASS: Temp file validation works")
        return True
    except Exception as e:
        print(f"✗ FAIL: Temp file validation failed: {e}")
        return False
    finally:
        os.unlink(temp_path)

def test_comprehensive_security():
    """Run all security tests"""
    print("Testing GLB Optimizer Security Enhancements")
    print("=" * 50)
    
    tests = [
        test_path_traversal_prevention,
        test_environment_sanitization,
        test_temp_file_validation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ FAIL: {test.__name__} threw exception: {e}")
    
    print("=" * 50)
    print(f"Security Tests: {passed}/{total} passed")
    
    if passed == total:
        print("✓ ALL SECURITY TESTS PASSED!")
        return True
    else:
        print("✗ SOME SECURITY TESTS FAILED!")
        return False

if __name__ == "__main__":
    test_comprehensive_security()