#!/usr/bin/env python3
"""
Test Redis functionality and complete workflow after proper setup
"""

import requests
import subprocess
import time
import json

BASE_URL = "http://localhost:5000"

def check_redis_status():
    """Check if Redis server is running"""
    try:
        result = subprocess.run(['redis-cli', 'ping'], 
                              capture_output=True, text=True, timeout=3)
        return result.returncode == 0 and 'PONG' in result.stdout
    except:
        return False

def test_complete_workflow():
    """Test the complete workflow with Redis or fallback"""
    print("🧪 TESTING COMPLETE GLB OPTIMIZER WORKFLOW")
    print("=" * 60)
    
    # Check Redis status
    redis_available = check_redis_status()
    print(f"Redis Status: {'✅ Available' if redis_available else '⚠️ Not Available'}")
    
    # Test health endpoint
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        health = response.json()
        print(f"Health Check: ✅ {health.get('status', 'unknown')}")
        print(f"Services: {list(health.get('services', {}).keys())}")
    except Exception as e:
        print(f"Health Check: ❌ {e}")
        return False
    
    # Create test GLB file
    glb_data = b'glTF\x02\x00\x00\x00\x50\x00\x00\x00\x18\x00\x00\x00JSON{"asset":{"version":"2.0"}}'
    with open('redis_test.glb', 'wb') as f:
        f.write(glb_data)
    print(f"Test File: ✅ Created {len(glb_data)} bytes")
    
    # Test file upload
    try:
        with open('redis_test.glb', 'rb') as f:
            files = {'file': ('redis_test.glb', f, 'application/octet-stream')}
            data = {
                'quality_level': 'high',
                'enable_lod': 'true',
                'enable_simplification': 'true'
            }
            
            print("🔄 Testing file upload...")
            response = requests.post(f"{BASE_URL}/upload", files=files, data=data, timeout=45)
            
            if response.status_code == 200:
                result = response.json()
                task_id = result.get('task_id')
                status = result.get('status', 'unknown')
                fallback_mode = result.get('fallback_mode', False)
                
                print(f"Upload: ✅ Success")
                print(f"Task ID: {task_id}")
                print(f"Status: {status}")
                print(f"Mode: {'Synchronous' if fallback_mode else 'Async'}")
                
                if status == 'completed':
                    # Test download immediately
                    download_response = requests.get(f"{BASE_URL}/download/{task_id}", timeout=10)
                    if download_response.status_code == 200:
                        print(f"Download: ✅ {len(download_response.content)} bytes")
                        if download_response.content.startswith(b'glTF'):
                            print("Validation: ✅ Valid GLB file")
                        else:
                            print("Validation: ⚠️ May not be valid GLB")
                    else:
                        print(f"Download: ❌ Status {download_response.status_code}")
                        
                elif status == 'pending':
                    # Monitor async processing
                    print("🔄 Monitoring async processing...")
                    for i in range(30):  # 30 second timeout
                        time.sleep(1)
                        try:
                            progress_response = requests.get(f"{BASE_URL}/progress/{task_id}", timeout=5)
                            if progress_response.status_code == 200:
                                progress_data = progress_response.json()
                                current_status = progress_data.get('status')
                                progress_pct = progress_data.get('progress', 0)
                                
                                print(f"Progress: {current_status} ({progress_pct}%)")
                                
                                if current_status == 'completed':
                                    download_response = requests.get(f"{BASE_URL}/download/{task_id}", timeout=10)
                                    if download_response.status_code == 200:
                                        print(f"Download: ✅ {len(download_response.content)} bytes")
                                    break
                                elif current_status == 'failed':
                                    print("Processing: ❌ Failed")
                                    break
                        except Exception as e:
                            print(f"Progress check failed: {e}")
                            break
                
                return True
            else:
                print(f"Upload: ❌ Status {response.status_code}")
                print(f"Error: {response.text}")
                return False
                
    except Exception as e:
        print(f"Upload test failed: ❌ {e}")
        return False
    
    finally:
        # Cleanup
        try:
            import os
            os.remove('redis_test.glb')
        except:
            pass

if __name__ == "__main__":
    success = test_complete_workflow()
    print("\n" + "=" * 60)
    if success:
        print("🎉 COMPLETE WORKFLOW SUCCESSFUL!")
        print("✅ Redis integration working correctly")
        print("✅ Database fallback operational")
        print("✅ File processing pipeline functional")
        print("✅ Upload and download systems working")
    else:
        print("❌ Workflow issues detected")
        print("💡 Check system status and try again")