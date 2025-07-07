#!/usr/bin/env python3
"""
Quick test to verify upload functionality
"""

import requests
import json

# Create a simple test file
glb_data = b'glTF\x02\x00\x00\x00\x50\x00\x00\x00\x18\x00\x00\x00JSON{"asset":{"version":"2.0"}}'
with open('quick_test.glb', 'wb') as f:
    f.write(glb_data)

print("Testing file upload...")

try:
    # Test upload with minimal timeout
    with open('quick_test.glb', 'rb') as f:
        response = requests.post(
            'http://localhost:5000/upload',
            files={'file': ('test.glb', f, 'application/octet-stream')},
            data={
                'quality_level': 'high',
                'enable_lod': 'true', 
                'enable_simplification': 'true'
            },
            timeout=5  # Very short timeout to see immediate response
        )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
except requests.exceptions.Timeout:
    print("Request timed out - this suggests processing is happening")
except Exception as e:
    print(f"Error: {e}")
    
# Cleanup
import os
try:
    os.remove('quick_test.glb')
except:
    pass