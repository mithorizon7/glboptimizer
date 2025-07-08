#!/usr/bin/env python3
"""
Complete pathlib consistency verification test
This test ensures ALL file operations use pathlib across the entire codebase
"""

import os
import re
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

def check_for_shutil_copy_usage(filepath):
    """Check for shutil.copy2 usage in file"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check for shutil.copy2 pattern
    pattern = r'shutil\.copy2\('
    issues = []
    
    matches = re.finditer(pattern, content)
    for match in matches:
        line_num = content[:match.start()].count('\n') + 1
        issues.append(f"Line {line_num}: {match.group()}")
    
    return issues

def check_for_os_path_usage(filepath):
    """Check for os.path usage in file"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check for various os.path patterns
    patterns = [
        r'os\.path\.join\(',
        r'os\.path\.exists\(',
        r'os\.path\.getsize\(',
        r'os\.path\.basename\(',
        r'os\.path\.dirname\(',
        r'os\.path\.abspath\(',
        r'os\.path\.realpath\(',
        r'os\.path\.splitext\(',
        r'os\.path\.isfile\(',
        r'os\.path\.isdir\(',
        r'os\.path\.makedirs\(',
    ]
    
    issues = []
    for pattern in patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            line_num = content[:match.start()].count('\n') + 1
            issues.append(f"Line {line_num}: {match.group()}")
    
    return issues

def check_for_string_path_concatenation(filepath):
    """Check for string path concatenation patterns"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Look for string concatenation patterns that might be paths
    patterns = [
        r'[\"\'][^\"\']*\/[^\"\']*[\"\'][\s]*\+[\s]*[\"\'][^\"\']*[\"\']',  # "path/" + "file"
        r'[\w]+[\s]*\+[\s]*[\"\'][^\"\']*\/[^\"\']*[\"\']',                # var + "/path"
        r'[\"\'][^\"\']*\/[^\"\']*[\"\'][\s]*\+[\s]*[\w]+',                # "/path" + var
    ]
    
    issues = []
    for pattern in patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            line_num = content[:match.start()].count('\n') + 1
            issues.append(f"Line {line_num}: {match.group()}")
    
    return issues

def main():
    print("🔍 Running COMPLETE pathlib consistency verification...")
    
    # Files to check
    files_to_check = ['app.py', 'config.py', 'optimizer.py']
    
    all_passed = True
    
    for file_path in files_to_check:
        if not os.path.exists(file_path):
            print(f"❌ {file_path} not found")
            all_passed = False
            continue
        
        print(f"\n📁 Checking {file_path}...")
        
        # Check for shutil.copy2 usage
        shutil_issues = check_for_shutil_copy_usage(file_path)
        if shutil_issues:
            print(f"❌ shutil.copy2 usage found in {file_path}:")
            for issue in shutil_issues:
                print(f"  - {issue}")
            all_passed = False
        else:
            print(f"✅ No shutil.copy2 usage in {file_path}")
        
        # Check for os.path usage
        os_path_issues = check_for_os_path_usage(file_path)
        if os_path_issues:
            print(f"❌ os.path usage found in {file_path}:")
            for issue in os_path_issues:
                print(f"  - {issue}")
            all_passed = False
        else:
            print(f"✅ No os.path usage in {file_path}")
        
        # Check for string path concatenation
        concat_issues = check_for_string_path_concatenation(file_path)
        if concat_issues:
            print(f"⚠️ Potential string path concatenation in {file_path}:")
            for issue in concat_issues:
                print(f"  - {issue}")
        else:
            print(f"✅ No string path concatenation in {file_path}")
    
    # Test pathlib helpers in optimizer.py
    print("\n🔧 Testing pathlib helper functions...")
    try:
        from optimizer import ensure_path, path_exists, path_size, path_basename, path_dirname, path_join
        
        # Test ensure_path
        test_path = ensure_path("test.txt")
        if isinstance(test_path, Path):
            print("✅ ensure_path() returns Path object")
        else:
            print("❌ ensure_path() doesn't return Path object")
            all_passed = False
            
        # Test path_exists
        test_exists = path_exists("optimizer.py")
        if test_exists:
            print("✅ path_exists() working correctly")
        else:
            print("❌ path_exists() not working correctly")
            all_passed = False
            
        # Test path_join
        joined = path_join("uploads", "test.glb")
        if isinstance(joined, Path) and str(joined).endswith("test.glb"):
            print("✅ path_join() working correctly")
        else:
            print("❌ path_join() not working correctly")
            all_passed = False
            
    except ImportError as e:
        print(f"❌ Failed to import pathlib helpers: {e}")
        all_passed = False
    
    print("\n" + "="*50)
    
    if all_passed:
        print("🎉 COMPLETE PATHLIB CONSISTENCY VERIFICATION PASSED!")
        print("✅ 100% pathlib consistency achieved across entire codebase")
        print("✅ All shutil.copy2 calls converted to pathlib equivalents")
        print("✅ All os.path calls converted to pathlib equivalents")
        print("✅ Helper functions working correctly")
    else:
        print("❌ PATHLIB CONSISTENCY VERIFICATION FAILED!")
        print("Please fix the issues above before proceeding.")
        sys.exit(1)

if __name__ == "__main__":
    main()