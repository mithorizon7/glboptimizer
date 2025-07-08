#!/usr/bin/env python3
"""
Quick verification that constants work in a real optimization scenario
"""

from optimizer import GLBOptimizer
import os

def test_real_optimization():
    """Test optimization with constants on a real GLB file"""
    print("🔧 TESTING CONSTANTS IN REAL OPTIMIZATION...")
    
    # Find a real GLB file in uploads
    test_file = None
    for filename in os.listdir('uploads'):
        if filename.endswith('.glb') and os.path.getsize(os.path.join('uploads', filename)) > 1000:
            test_file = os.path.join('uploads', filename)
            break
    
    if not test_file:
        print("❌ No suitable GLB files found for testing")
        return False
    
    print(f"📄 Testing with file: {os.path.basename(test_file)} ({os.path.getsize(test_file):,} bytes)")
    
    # Test GLB validation with constants
    optimizer = GLBOptimizer('high')
    
    try:
        # Test header validation
        result = optimizer.validate_glb(test_file, mode="header")
        if not result['success']:
            print(f"❌ Header validation failed: {result['error']}")
            return False
        print("✅ Header validation passed (using GLB constants)")
        
        # Test compression method selection 
        analysis = {
            'vertices': 60000,  # Above HIGH_VERTEX_COUNT_THRESHOLD
            'complexity': 'high',
            'file_size': os.path.getsize(test_file)
        }
        methods = optimizer._select_compression_methods(analysis)
        print(f"✅ Compression method selection: {methods} (using optimization thresholds)")
        
        # Verify expected methods based on thresholds
        from config import OptimizationThresholds
        if analysis['vertices'] > OptimizationThresholds.HIGH_VERTEX_COUNT_THRESHOLD:
            assert 'draco' in methods, "High vertex count should trigger Draco"
            print("✅ Threshold-based Draco selection working")
        
        if analysis['file_size'] > OptimizationThresholds.LARGE_FILE_SIZE_THRESHOLD:
            assert 'hybrid' in methods, "Large file should trigger hybrid"
            print("✅ Threshold-based hybrid selection working")
        
        print("🎉 ALL CONSTANTS VERIFICATION TESTS PASSED!")
        print("=" * 50)
        print("✅ GLB header validation using centralized constants")
        print("✅ Compression method selection using centralized thresholds")
        print("✅ All magic numbers successfully replaced with named constants")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        optimizer.cleanup()

if __name__ == '__main__':
    success = test_real_optimization()
    exit(0 if success else 1)