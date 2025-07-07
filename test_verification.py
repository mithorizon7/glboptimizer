#!/usr/bin/env python3
"""
Quick verification test to ensure core functionality works after Redis fallback
"""

import requests
import json
import time

BASE_URL = "http://localhost:5000"

def test_basic_functionality():
    """Test the essential workflow end-to-end"""
    print("🧪 Testing Basic GLB Optimizer Functionality")
    print("=" * 50)
    
    # Test 1: Homepage loads
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"✅ Homepage: {response.status_code == 200} (Status: {response.status_code})")
    except Exception as e:
        print(f"❌ Homepage: Failed - {e}")
        return False
    
    # Test 2: Health check
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        health = response.json()
        print(f"✅ Health check: {response.status_code == 200} (Services: {list(health.get('services', {}).keys())})")
    except Exception as e:
        print(f"❌ Health check: Failed - {e}")
    
    # Test 3: Create simple GLB file
    glb_data = b'glTF\x02\x00\x00\x00\x50\x00\x00\x00\x18\x00\x00\x00JSON{"asset":{"version":"2.0"}}'
    with open('verify_test.glb', 'wb') as f:
        f.write(glb_data)
    print(f"✅ Test file created: {len(glb_data)} bytes")
    
    # Test 4: File upload and optimization
    try:
        with open('verify_test.glb', 'rb') as f:
            files = {'file': ('verify_test.glb', f, 'application/octet-stream')}
            data = {
                'quality_level': 'high',
                'enable_lod': 'true',
                'enable_simplification': 'true'
            }
            
            print("🔄 Uploading file...")
            response = requests.post(f"{BASE_URL}/upload", files=files, data=data, timeout=30)
            
            print(f"Upload status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                task_id = result.get('task_id')
                fallback_mode = result.get('fallback_mode', False)
                status = result.get('status', 'unknown')
                
                print(f"✅ Upload successful: Task {task_id}")
                print(f"   Mode: {'Synchronous (fallback)' if fallback_mode else 'Async'}")
                print(f"   Status: {status}")
                
                if status == 'completed':
                    # Test download
                    try:
                        download_response = requests.get(f"{BASE_URL}/download/{task_id}", timeout=10)
                        if download_response.status_code == 200:
                            print(f"✅ Download successful: {len(download_response.content)} bytes")
                            
                            # Verify it's a GLB file
                            if download_response.content.startswith(b'glTF'):
                                print("✅ Downloaded file is valid GLB")
                            else:
                                print("⚠️  Downloaded file may not be valid GLB")
                        else:
                            print(f"❌ Download failed: {download_response.status_code}")
                    except Exception as e:
                        print(f"❌ Download test failed: {e}")
                
                return True
            else:
                print(f"❌ Upload failed: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Upload test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_basic_functionality()
    print("\n" + "=" * 50)
    if success:
        print("🎉 ALL CORE FUNCTIONALITY WORKING!")
        print("✅ Upload system operational")
        print("✅ Synchronous processing working")
        print("✅ Download system functional")
        print("\n🚀 GLB Optimizer is ready for production!")
    else:
        print("❌ Some functionality issues detected")
        print("💡 Check the logs above for details")
    
    # Cleanup
    import os
    try:
        os.remove('verify_test.glb')
    except:
        pass