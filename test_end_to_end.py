#!/usr/bin/env python3
"""
Complete End-to-End Test Suite for GLB Optimizer
Tests all functionality after Redis connectivity resolution
"""

import os
import sys
import time
import requests
import json
import subprocess
from pathlib import Path

# Test configuration
BASE_URL = "http://localhost:5000"
TEST_FILE_SIZE = 1024  # Small test GLB file

def create_test_glb_file():
    """Create a minimal valid GLB file for testing"""
    # GLB header: magic "glTF" + version + length + JSON chunk header
    glb_header = b'glTF'  # Magic
    glb_header += b'\x02\x00\x00\x00'  # Version 2.0
    glb_header += b'\x50\x00\x00\x00'  # Total length (80 bytes)
    
    # JSON chunk
    json_data = b'{"asset":{"version":"2.0"}}'
    json_length = len(json_data)
    json_padding = (4 - (json_length % 4)) % 4
    json_data += b' ' * json_padding
    
    glb_data = glb_header
    glb_data += json_length.to_bytes(4, 'little')  # JSON chunk length
    glb_data += b'JSON'  # JSON chunk type
    glb_data += json_data
    
    return glb_data

class GLBOptimizerTester:
    def __init__(self):
        self.results = {"passed": 0, "failed": 0, "tests": []}
        self.test_file_path = "test_model.glb"
        
    def log_test(self, name, passed, details=""):
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {name}")
        if details:
            print(f"      {details}")
        
        self.results["tests"].append({
            "name": name,
            "passed": passed,
            "details": details
        })
        
        if passed:
            self.results["passed"] += 1
        else:
            self.results["failed"] += 1

    def setup_test_environment(self):
        """Setup test files and environment"""
        print("=== SETTING UP TEST ENVIRONMENT ===")
        
        # Create test GLB file
        try:
            glb_data = create_test_glb_file()
            with open(self.test_file_path, 'wb') as f:
                f.write(glb_data)
            self.log_test("Create test GLB file", True, f"Created {len(glb_data)} byte test file")
        except Exception as e:
            self.log_test("Create test GLB file", False, str(e))
            return False
        
        # Verify server is running
        try:
            response = requests.get(f"{BASE_URL}/", timeout=5)
            self.log_test("Server connectivity", response.status_code == 200, 
                         f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Server connectivity", False, str(e))
            return False
            
        return True

    def test_homepage_load(self):
        """Test homepage loads with all elements"""
        print("\n=== TESTING HOMEPAGE ===")
        
        try:
            response = requests.get(f"{BASE_URL}/", timeout=10)
            content = response.text
            
            # Check for key UI elements
            checks = [
                ("Page loads", response.status_code == 200),
                ("Title present", "GLB Optimizer" in content),
                ("Upload zone", "drop-zone" in content),
                ("Quality settings", "quality_level" in content),
                ("Bootstrap CSS", "bootstrap" in content),
                ("Three.js viewer", "three.min.js" in content),
                ("Help tooltips", "tooltip" in content),
            ]
            
            for check_name, passed in checks:
                self.log_test(f"Homepage: {check_name}", passed)
                
        except Exception as e:
            self.log_test("Homepage load", False, str(e))

    def test_health_endpoints(self):
        """Test health and monitoring endpoints"""
        print("\n=== TESTING HEALTH ENDPOINTS ===")
        
        endpoints = [
            ("/health", "Health check"),
            ("/admin/stats", "Database stats"),
            ("/admin/analytics", "Analytics dashboard")
        ]
        
        for endpoint, name in endpoints:
            try:
                response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
                data = response.json()
                
                self.log_test(f"{name} endpoint", response.status_code == 200,
                             f"Response: {str(data)[:100]}...")
                             
            except Exception as e:
                self.log_test(f"{name} endpoint", False, str(e))

    def test_file_upload_and_optimization(self):
        """Test complete file upload and optimization workflow"""
        print("\n=== TESTING FILE UPLOAD & OPTIMIZATION ===")
        
        try:
            # Test file upload
            with open(self.test_file_path, 'rb') as f:
                files = {'file': ('test_model.glb', f, 'application/octet-stream')}
                data = {
                    'quality_level': 'high',
                    'enable_lod': 'true',
                    'enable_simplification': 'true'
                }
                
                response = requests.post(f"{BASE_URL}/upload", files=files, data=data, timeout=30)
                
            self.log_test("File upload request", response.status_code == 200,
                         f"Status: {response.status_code}")
            
            if response.status_code != 200:
                self.log_test("Upload workflow", False, f"Upload failed: {response.text}")
                return
                
            # Parse response
            try:
                result = response.json()
                task_id = result.get('task_id')
                
                self.log_test("Upload response parsing", task_id is not None,
                             f"Task ID: {task_id}")
                
                if not task_id:
                    return
                    
                # Check if using fallback mode (synchronous processing)
                if result.get('fallback_mode') or result.get('status') == 'completed':
                    self.log_test("Synchronous processing mode", True,
                                 "Using fallback mode - immediate results")
                    self.test_download_file(task_id)
                else:
                    # Test progress polling for async mode
                    self.test_progress_polling(task_id)
                    
            except Exception as e:
                self.log_test("Upload response parsing", False, str(e))
                
        except Exception as e:
            self.log_test("File upload", False, str(e))

    def test_progress_polling(self, task_id):
        """Test progress polling for async tasks"""
        print(f"\n=== TESTING PROGRESS POLLING for {task_id} ===")
        
        max_attempts = 30  # 30 seconds max
        for attempt in range(max_attempts):
            try:
                response = requests.get(f"{BASE_URL}/progress/{task_id}", timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get('status', 'unknown')
                    progress = data.get('progress', 0)
                    
                    self.log_test(f"Progress check #{attempt+1}", True,
                                 f"Status: {status}, Progress: {progress}%")
                    
                    if status == 'completed':
                        self.test_download_file(task_id)
                        break
                    elif status == 'failed':
                        self.log_test("Task completion", False, "Task failed")
                        break
                else:
                    self.log_test(f"Progress request #{attempt+1}", False,
                                 f"Status: {response.status_code}")
                    
                time.sleep(1)
                
            except Exception as e:
                self.log_test(f"Progress polling #{attempt+1}", False, str(e))
                break

    def test_download_file(self, task_id):
        """Test file download functionality"""
        print(f"\n=== TESTING FILE DOWNLOAD for {task_id} ===")
        
        try:
            response = requests.get(f"{BASE_URL}/download/{task_id}", timeout=10)
            
            self.log_test("Download request", response.status_code == 200,
                         f"Status: {response.status_code}, Size: {len(response.content)} bytes")
            
            if response.status_code == 200:
                # Save downloaded file for verification
                download_path = f"downloaded_{task_id}.glb"
                with open(download_path, 'wb') as f:
                    f.write(response.content)
                    
                self.log_test("Download file save", True,
                             f"Saved to {download_path}")
                
                # Verify it's a valid GLB file
                if response.content.startswith(b'glTF'):
                    self.log_test("Downloaded file validation", True,
                                 "Valid GLB header detected")
                else:
                    self.log_test("Downloaded file validation", False,
                                 "Invalid GLB header")
                    
        except Exception as e:
            self.log_test("File download", False, str(e))

    def test_3d_viewer_resources(self):
        """Test 3D viewer and comparison functionality"""
        print("\n=== TESTING 3D VIEWER RESOURCES ===")
        
        # Test static file serving
        static_files = [
            "/static/three.min.js",
            "/static/GLTFLoader.js", 
            "/static/OrbitControls.js",
            "/static/style.css",
            "/static/script.js"
        ]
        
        for file_path in static_files:
            try:
                response = requests.get(f"{BASE_URL}{file_path}", timeout=5)
                self.log_test(f"Static file: {file_path}", 
                             response.status_code == 200,
                             f"Status: {response.status_code}")
            except Exception as e:
                self.log_test(f"Static file: {file_path}", False, str(e))

    def test_database_functionality(self):
        """Test database operations and analytics"""
        print("\n=== TESTING DATABASE FUNCTIONALITY ===")
        
        try:
            # Test database stats
            response = requests.get(f"{BASE_URL}/admin/stats", timeout=5)
            if response.status_code == 200:
                stats = response.json()
                self.log_test("Database stats", True,
                             f"Total tasks: {stats.get('total_tasks', 'unknown')}")
            else:
                self.log_test("Database stats", False, f"Status: {response.status_code}")
                
            # Test analytics
            response = requests.get(f"{BASE_URL}/admin/analytics", timeout=5)
            if response.status_code == 200:
                analytics = response.json()
                self.log_test("Analytics dashboard", True,
                             f"Summary available: {'summary_stats' in analytics}")
            else:
                self.log_test("Analytics dashboard", False, f"Status: {response.status_code}")
                
        except Exception as e:
            self.log_test("Database functionality", False, str(e))

    def test_error_handling(self):
        """Test error handling for invalid inputs"""
        print("\n=== TESTING ERROR HANDLING ===")
        
        # Test invalid file upload
        try:
            files = {'file': ('test.txt', b'not a glb file', 'text/plain')}
            response = requests.post(f"{BASE_URL}/upload", files=files, timeout=10)
            
            is_error = response.status_code >= 400
            self.log_test("Invalid file rejection", is_error,
                         f"Status: {response.status_code}")
                         
        except Exception as e:
            self.log_test("Invalid file test", False, str(e))
            
        # Test non-existent task
        try:
            response = requests.get(f"{BASE_URL}/progress/nonexistent-task", timeout=5)
            is_error = response.status_code >= 400
            self.log_test("Non-existent task handling", is_error,
                         f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Non-existent task test", False, str(e))

    def cleanup(self):
        """Clean up test files"""
        print("\n=== CLEANING UP ===")
        
        files_to_remove = [self.test_file_path]
        files_to_remove.extend([f for f in os.listdir('.') if f.startswith('downloaded_')])
        
        for file_path in files_to_remove:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Removed: {file_path}")
            except Exception as e:
                print(f"Failed to remove {file_path}: {e}")

    def run_all_tests(self):
        """Run complete test suite"""
        print("🚀 STARTING COMPREHENSIVE GLB OPTIMIZER TEST SUITE")
        print("=" * 60)
        
        if not self.setup_test_environment():
            print("❌ Test environment setup failed - aborting")
            return False
            
        # Run all test categories
        self.test_homepage_load()
        self.test_health_endpoints()
        self.test_file_upload_and_optimization()
        self.test_3d_viewer_resources()
        self.test_database_functionality()
        self.test_error_handling()
        
        # Print summary
        print("\n" + "=" * 60)
        print("🏁 TEST SUITE COMPLETE")
        print(f"✅ PASSED: {self.results['passed']}")
        print(f"❌ FAILED: {self.results['failed']}")
        print(f"📊 TOTAL:  {self.results['passed'] + self.results['failed']}")
        
        if self.results['failed'] == 0:
            print("\n🎉 ALL TESTS PASSED - System is fully operational!")
            return True
        else:
            print(f"\n⚠️  {self.results['failed']} tests failed - review issues above")
            return False

if __name__ == "__main__":
    tester = GLBOptimizerTester()
    try:
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)
    finally:
        tester.cleanup()