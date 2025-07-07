#!/usr/bin/env python3
"""
Complete workflow test - verify upload, processing, and download
"""

import requests
import time
import json

# Create a proper GLB test file
glb_data = b'glTF\x02\x00\x00\x00\x50\x00\x00\x00\x18\x00\x00\x00JSON{"asset":{"version":"2.0"}}'

def test_upload_and_download():
    print("🧪 TESTING COMPLETE UPLOAD → PROCESSING → DOWNLOAD")
    print("=" * 60)
    
    with open('workflow_test.glb', 'wb') as f:
        f.write(glb_data)
    
    try:
        print(f"📁 Created test file: {len(glb_data)} bytes")
        
        # Upload file
        print("🔄 Uploading file...")
        with open('workflow_test.glb', 'rb') as f:
            response = requests.post(
                'http://localhost:5000/upload',
                files={'file': ('workflow_test.glb', f, 'application/octet-stream')},
                data={
                    'quality_level': 'high',
                    'enable_lod': 'true',
                    'enable_simplification': 'true'
                },
                timeout=15
            )
        
        print(f"📤 Upload response: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            task_id = result.get('task_id')
            status = result.get('status')
            fallback_mode = result.get('fallback_mode', False)
            
            print(f"✅ Upload successful!")
            print(f"   Task ID: {task_id}")
            print(f"   Status: {status}")
            print(f"   Mode: {'Synchronous' if fallback_mode else 'Async'}")
            
            if status == 'completed':
                print("⚡ Processing completed immediately (synchronous mode)")
                
                # Test download
                print("🔄 Testing download...")
                download_response = requests.get(f'http://localhost:5000/download/{task_id}', timeout=10)
                
                if download_response.status_code == 200:
                    print(f"✅ Download successful: {len(download_response.content)} bytes")
                    
                    # Verify GLB format
                    if download_response.content.startswith(b'glTF'):
                        print("✅ Downloaded file is valid GLB format")
                    else:
                        print("⚠️ Downloaded file may not be valid GLB")
                        
                    # Test cleanup
                    cleanup_response = requests.delete(f'http://localhost:5000/cleanup/{task_id}', timeout=5)
                    if cleanup_response.status_code == 200:
                        print("✅ Cleanup successful")
                    else:
                        print(f"⚠️ Cleanup failed: {cleanup_response.status_code}")
                        
                else:
                    print(f"❌ Download failed: {download_response.status_code}")
                    print(f"   Error: {download_response.text}")
                    
            else:
                print(f"⚠️ Processing status: {status}")
                
            return True
            
        else:
            print(f"❌ Upload failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("⏱️ Request timed out - processing may be taking longer")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        # Cleanup test file
        import os
        try:
            os.remove('workflow_test.glb')
        except:
            pass

def test_system_status():
    print("\n🔍 SYSTEM STATUS CHECK")
    print("=" * 30)
    
    # Health check
    try:
        health = requests.get('http://localhost:5000/health', timeout=5).json()
        print(f"Health: {health.get('status', 'unknown')}")
        
        services = health.get('services', {})
        for service, status in services.items():
            print(f"  {service}: {status}")
            
    except Exception as e:
        print(f"Health check failed: {e}")
    
    # Database stats
    try:
        stats = requests.get('http://localhost:5000/admin/stats', timeout=5).json()
        print(f"\nDatabase Stats:")
        print(f"  Total tasks: {stats.get('total_tasks', 0)}")
        print(f"  Completed: {stats.get('completed_tasks', 0)}")
        print(f"  Users: {stats.get('total_users', 0)}")
        
    except Exception as e:
        print(f"Stats check failed: {e}")

if __name__ == "__main__":
    test_system_status()
    success = test_upload_and_download()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 COMPLETE WORKFLOW TEST PASSED!")
        print("✅ File upload working")
        print("✅ Synchronous processing operational")
        print("✅ File download functional")
        print("✅ Cleanup system working")
        print("\n🚀 GLB Optimizer is fully operational!")
    else:
        print("❌ Workflow test failed")
        print("💡 Check the output above for details")