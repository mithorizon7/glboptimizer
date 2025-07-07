#!/usr/bin/env python3
"""
Debug the optimization process to find where files are going wrong
"""

import requests
import os
import time

def create_test_file():
    # Create a minimal but valid GLB file
    glb_data = b'glTF\x02\x00\x00\x00\x50\x00\x00\x00\x18\x00\x00\x00JSON{"asset":{"version":"2.0"}}'
    with open('debug_test.glb', 'wb') as f:
        f.write(glb_data)
    return len(glb_data)

def test_optimization_flow():
    print("🔍 DEBUGGING OPTIMIZATION FLOW")
    print("=" * 50)
    
    file_size = create_test_file()
    print(f"Created test file: {file_size} bytes")
    
    try:
        # Upload and process
        with open('debug_test.glb', 'rb') as f:
            response = requests.post(
                'http://localhost:5000/upload',
                files={'file': ('debug_test.glb', f, 'application/octet-stream')},
                data={
                    'quality_level': 'high',
                    'enable_lod': 'true',
                    'enable_simplification': 'true'
                },
                timeout=30
            )
        
        print(f"Upload response: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            task_id = result.get('task_id')
            print(f"Task ID: {task_id}")
            print(f"Status: {result.get('status')}")
            
            # Check if files exist
            upload_file = f"uploads/{task_id}.glb"
            output_file = f"output/{task_id}_optimized.glb"
            
            print(f"Upload file exists: {os.path.exists(upload_file)}")
            print(f"Output file exists: {os.path.exists(output_file)}")
            
            if os.path.exists(output_file):
                output_size = os.path.getsize(output_file)
                print(f"Output file size: {output_size} bytes")
                
                # Test download
                download_response = requests.get(f'http://localhost:5000/download/{task_id}', timeout=10)
                print(f"Download response: {download_response.status_code}")
                
                if download_response.status_code != 200:
                    print(f"Download error: {download_response.text}")
                else:
                    print(f"Download successful: {len(download_response.content)} bytes")
            else:
                print("❌ Output file missing!")
                
            # Check database status
            stats = requests.get('http://localhost:5000/admin/stats').json()
            print(f"Database stats: {stats}")
            
            return task_id
        else:
            print(f"Upload failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"Error: {e}")
        return None
    finally:
        try:
            os.remove('debug_test.glb')
        except:
            pass

if __name__ == "__main__":
    task_id = test_optimization_flow()
    
    if task_id:
        print(f"\n📋 DEBUGGING SUMMARY FOR TASK: {task_id}")
        print("Check the workflow logs to see what happened during optimization")
    else:
        print("\n❌ Debug test failed")