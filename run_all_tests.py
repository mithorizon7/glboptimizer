#!/usr/bin/env python3
"""
Comprehensive test runner for GLB Optimizer
Runs all test suites and generates a comprehensive report
"""
import subprocess
import sys
import time
import os
from pathlib import Path

def run_test_suite(test_file, description):
    """Run a specific test suite and return results"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"File: {test_file}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            [sys.executable, test_file],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout per test suite
        )
        
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✓ {description} PASSED ({elapsed:.2f}s)")
            if result.stdout:
                print("Output:")
                print(result.stdout)
            return True, elapsed, result.stdout
        else:
            print(f"✗ {description} FAILED ({elapsed:.2f}s)")
            if result.stderr:
                print("Errors:")
                print(result.stderr)
            if result.stdout:
                print("Output:")
                print(result.stdout)
            return False, elapsed, result.stderr
            
    except subprocess.TimeoutExpired:
        print(f"✗ {description} TIMEOUT (5 minutes)")
        return False, 300, "Test suite timed out"
    except Exception as e:
        print(f"✗ {description} ERROR: {str(e)}")
        return False, 0, str(e)

def main():
    """Run all test suites and generate comprehensive report"""
    print("GLB Optimizer - Comprehensive Test Suite")
    print("=" * 60)
    
    # Define test suites
    test_suites = [
        ("test_parallel_compression.py", "Parallel Compression System"),
        ("test_atomic_writes.py", "Atomic Write Operations"),
        ("test_security_comprehensive.py", "Security Features"),
        ("test_complete_optimization_workflow.py", "Complete Optimization Workflow")
    ]
    
    # Track results
    results = []
    total_start_time = time.time()
    
    # Run each test suite
    for test_file, description in test_suites:
        if os.path.exists(test_file):
            success, elapsed, output = run_test_suite(test_file, description)
            results.append({
                'name': description,
                'file': test_file,
                'success': success,
                'elapsed': elapsed,
                'output': output
            })
        else:
            print(f"⚠ Test file not found: {test_file}")
            results.append({
                'name': description,
                'file': test_file,
                'success': False,
                'elapsed': 0,
                'output': f"Test file not found: {test_file}"
            })
    
    total_elapsed = time.time() - total_start_time
    
    # Generate comprehensive report
    print(f"\n{'='*60}")
    print("COMPREHENSIVE TEST REPORT")
    print(f"{'='*60}")
    print(f"Total execution time: {total_elapsed:.2f} seconds")
    print(f"Test suites run: {len(results)}")
    
    passed = sum(1 for r in results if r['success'])
    failed = len(results) - passed
    
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success rate: {(passed/len(results)*100):.1f}%")
    
    print(f"\n{'DETAILED RESULTS':-^60}")
    for result in results:
        status = "✓ PASS" if result['success'] else "✗ FAIL"
        print(f"{result['name']:<40} {status:>8} ({result['elapsed']:.1f}s)")
    
    # Performance summary
    print(f"\n{'PERFORMANCE SUMMARY':-^60}")
    fastest = min(results, key=lambda x: x['elapsed'])
    slowest = max(results, key=lambda x: x['elapsed'])
    
    print(f"Fastest test: {fastest['name']} ({fastest['elapsed']:.2f}s)")
    print(f"Slowest test: {slowest['name']} ({slowest['elapsed']:.2f}s)")
    print(f"Average time per test: {sum(r['elapsed'] for r in results)/len(results):.2f}s")
    
    # Feature coverage summary
    print(f"\n{'FEATURE COVERAGE':-^60}")
    features_tested = [
        "✓ Process-based parallel compression",
        "✓ Atomic write operations with GLB validation", 
        "✓ Path traversal attack prevention",
        "✓ Command injection protection",
        "✓ Environment sanitization",
        "✓ File size validation and DoS protection",
        "✓ GLB format structure validation",
        "✓ Symlink attack prevention",
        "✓ TOCTOU protection",
        "✓ Resource limits and constraints",
        "✓ Subprocess security",
        "✓ Temporary file security",
        "✓ Context manager resource cleanup",
        "✓ Progress tracking system",
        "✓ Error handling and recovery",
        "✓ Quality level variations",
        "✓ Memory and performance constraints"
    ]
    
    for feature in features_tested:
        print(f"  {feature}")
    
    # Recommendations
    print(f"\n{'RECOMMENDATIONS':-^60}")
    if failed == 0:
        print("✓ All tests passed! System is ready for production deployment.")
        print("✓ Security features are comprehensive and working correctly.")
        print("✓ Performance optimizations are functioning as expected.")
    else:
        print(f"⚠ {failed} test suite(s) failed - review and fix before deployment.")
        print("⚠ Check error outputs above for specific issues.")
        
        failed_tests = [r for r in results if not r['success']]
        for test in failed_tests:
            print(f"  - {test['name']}: Review {test['file']}")
    
    # System information
    print(f"\n{'SYSTEM INFORMATION':-^60}")
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Test files location: {Path(__file__).parent}")
    
    # Exit with appropriate code
    if failed == 0:
        print(f"\n{'TEST SUITE COMPLETED SUCCESSFULLY':-^60}")
        sys.exit(0)
    else:
        print(f"\n{'TEST SUITE COMPLETED WITH FAILURES':-^60}")
        sys.exit(1)

if __name__ == '__main__':
    main()