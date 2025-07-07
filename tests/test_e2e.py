# tests/test_e2e.py
"""
End-to-end tests for GLB Optimizer
Simulates complete user journeys using browser automation
"""
import pytest
import os
import tempfile
import time
from pathlib import Path

# Skip E2E tests if Playwright not available
pytest_playwright = pytest.importorskip("pytest_playwright", reason="Playwright not installed")

class TestE2EUserJourneys:
    """End-to-end tests simulating real user interactions"""
    
    @pytest.fixture(autouse=True)
    def setup_test_environment(self, page):
        """Set up test environment for E2E tests"""
        # Ensure test server is running
        self.base_url = "http://localhost:5000"
        
        # Create test GLB file
        self.test_glb_file = self.create_test_glb_file()
        
        # Navigate to application
        page.goto(self.base_url)
        page.wait_for_load_state("networkidle")
    
    def create_test_glb_file(self):
        """Create a test GLB file for uploads"""
        test_file = tempfile.NamedTemporaryFile(suffix='.glb', delete=False)
        
        # Create minimal valid GLB file
        with open(test_file.name, 'wb') as f:
            # GLB header
            f.write(b'glTF')  # Magic
            f.write((2).to_bytes(4, 'little'))  # Version
            f.write((500).to_bytes(4, 'little'))  # Total length
            
            # JSON chunk
            json_data = b'{"scene":0,"scenes":[{"nodes":[0]}],"nodes":[{"mesh":0}],"meshes":[{"primitives":[{"attributes":{"POSITION":0}}]}],"accessors":[{"count":3,"type":"VEC3","componentType":5126}],"bufferViews":[{"buffer":0,"byteLength":36}],"buffers":[{"byteLength":36}]}'
            json_chunk_len = len(json_data)
            f.write(json_chunk_len.to_bytes(4, 'little'))
            f.write(b'JSON')
            f.write(json_data)
            
            # Binary chunk
            binary_data = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x80\x3f\x00\x00\x00\x00\x00\x00\x80\x3f\x00\x00\x80\x3f\x00\x00\x00\x00\x00\x00\x80\x3f\x00\x00\x80\x3f\x00\x00\x80\x3f'
            f.write(len(binary_data).to_bytes(4, 'little'))
            f.write(b'BIN\x00')
            f.write(binary_data)
            
            # Pad to reach declared length
            current_size = f.tell()
            padding_needed = 500 - current_size
            if padding_needed > 0:
                f.write(b'\x00' * padding_needed)
        
        return test_file.name
    
    def teardown_method(self):
        """Clean up test files"""
        if hasattr(self, 'test_glb_file') and os.path.exists(self.test_glb_file):
            os.unlink(self.test_glb_file)
    
    def test_happy_path_optimization_flow(self, page):
        """Test complete successful optimization workflow"""
        # Verify homepage loads
        assert page.title() == "GLB Optimizer - Optimize 3D Models for Web"
        
        # Verify main sections are visible
        page.wait_for_selector("#upload-section")
        page.wait_for_selector("#optimization-settings")
        
        # Upload GLB file
        file_input = page.locator('input[type="file"]')
        file_input.set_input_files(self.test_glb_file)
        
        # Verify file is selected
        page.wait_for_selector('.file-selected', timeout=5000)
        
        # Select optimization settings
        quality_select = page.locator('select[name="quality_level"]')
        quality_select.select_option("high")
        
        # Enable optimization options
        page.locator('input[name="enable_lod"]').check()
        page.locator('input[name="enable_simplification"]').check()
        
        # Start optimization
        start_button = page.locator('button:has-text("Start Optimization")')
        start_button.click()
        
        # Wait for progress section to appear
        page.wait_for_selector("#progress-section", state="visible", timeout=10000)
        
        # Verify progress elements are present
        assert page.locator(".progress-bar").is_visible()
        assert page.locator("#progress-percentage").is_visible()
        assert page.locator("#current-step").is_visible()
        
        # Wait for optimization to complete (with timeout)
        try:
            page.wait_for_selector("#results-section", state="visible", timeout=30000)
        except:
            # If optimization doesn't complete, check for error section
            if page.locator("#error-section").is_visible():
                error_message = page.locator("#error-message").inner_text()
                pytest.fail(f"Optimization failed with error: {error_message}")
            else:
                pytest.fail("Optimization did not complete within timeout")
        
        # Verify results are displayed
        assert page.locator("#compression-stats").is_visible()
        assert page.locator("#original-size").is_visible()
        assert page.locator("#optimized-size").is_visible()
        assert page.locator("#compression-ratio").is_visible()
        
        # Verify download button is available
        download_button = page.locator('button:has-text("Download Optimized GLB")')
        assert download_button.is_visible()
        
        # Test download functionality
        with page.expect_download() as download_info:
            download_button.click()
        
        download = download_info.value
        assert download.suggested_filename.endswith('.glb')
        
        # Verify file was downloaded
        download_path = Path(tempfile.gettempdir()) / download.suggested_filename
        download.save_as(download_path)
        assert download_path.exists()
        assert download_path.stat().st_size > 0
        
        # Clean up downloaded file
        download_path.unlink()
    
    def test_file_validation_errors(self, page):
        """Test file validation and error handling"""
        # Create invalid file (not GLB)
        invalid_file = tempfile.NamedTemporaryFile(suffix='.txt', delete=False)
        with open(invalid_file.name, 'w') as f:
            f.write("This is not a GLB file")
        
        try:
            # Attempt to upload invalid file
            file_input = page.locator('input[type="file"]')
            file_input.set_input_files(invalid_file.name)
            
            # Start optimization
            start_button = page.locator('button:has-text("Start Optimization")')
            start_button.click()
            
            # Should show error message
            page.wait_for_selector("#error-section", state="visible", timeout=10000)
            error_message = page.locator("#error-message").inner_text()
            
            # Verify error message mentions file format
            assert "GLB" in error_message or "format" in error_message.lower()
            
        finally:
            os.unlink(invalid_file.name)
    
    def test_large_file_handling(self, page):
        """Test handling of large files"""
        # Create file larger than limit
        large_file = tempfile.NamedTemporaryFile(suffix='.glb', delete=False)
        with open(large_file.name, 'wb') as f:
            # Write 10MB of data (larger than test limit)
            f.write(b'x' * (10 * 1024 * 1024))
        
        try:
            # Attempt to upload large file
            file_input = page.locator('input[type="file"]')
            file_input.set_input_files(large_file.name)
            
            # Start optimization
            start_button = page.locator('button:has-text("Start Optimization")')
            start_button.click()
            
            # Should show error for file size
            page.wait_for_selector("#error-section", state="visible", timeout=10000)
            error_message = page.locator("#error-message").inner_text()
            
            # Verify error message mentions file size
            assert "size" in error_message.lower() or "large" in error_message.lower()
            
        finally:
            os.unlink(large_file.name)
    
    def test_optimization_failure_path(self, page):
        """Test user experience when optimization fails"""
        # This test requires mocking the backend to simulate failure
        # In a real E2E environment, you might use a specially crafted file
        # that causes optimization to fail
        
        # Upload file
        file_input = page.locator('input[type="file"]')
        file_input.set_input_files(self.test_glb_file)
        
        # Select settings that might cause failure
        quality_select = page.locator('select[name="quality_level"]')
        quality_select.select_option("maximum_compression")
        
        # Start optimization
        start_button = page.locator('button:has-text("Start Optimization")')
        start_button.click()
        
        # Wait for either results or error
        page.wait_for_function("""
            () => {
                const results = document.querySelector('#results-section');
                const error = document.querySelector('#error-section');
                return (results && results.style.display !== 'none') || 
                       (error && error.style.display !== 'none');
            }
        """, timeout=60000)
        
        # If error occurred, verify error handling
        if page.locator("#error-section").is_visible():
            # Verify error message is user-friendly
            error_message = page.locator("#error-message").inner_text()
            assert len(error_message) > 0
            assert error_message != "undefined" and error_message != "null"
            
            # Verify error log download is available
            if page.locator('button:has-text("Download Error Log")').is_visible():
                with page.expect_download() as download_info:
                    page.locator('button:has-text("Download Error Log")').click()
                
                download = download_info.value
                assert download.suggested_filename.endswith('.log') or download.suggested_filename.endswith('.txt')
    
    def test_progress_updates(self, page):
        """Test that progress updates are displayed correctly"""
        # Upload file
        file_input = page.locator('input[type="file"]')
        file_input.set_input_files(self.test_glb_file)
        
        # Start optimization
        start_button = page.locator('button:has-text("Start Optimization")')
        start_button.click()
        
        # Wait for progress section
        page.wait_for_selector("#progress-section", state="visible", timeout=10000)
        
        # Monitor progress updates
        progress_values = []
        step_messages = []
        
        # Collect progress updates for a few seconds
        for _ in range(10):
            try:
                progress_text = page.locator("#progress-percentage").inner_text()
                step_text = page.locator("#current-step").inner_text()
                
                if progress_text and progress_text != "0%":
                    progress_values.append(progress_text)
                
                if step_text and step_text not in step_messages:
                    step_messages.append(step_text)
                
                time.sleep(1)
                
                # Break if optimization completed
                if page.locator("#results-section").is_visible():
                    break
                    
            except:
                # Continue if elements not ready
                continue
        
        # Verify progress updates occurred
        if len(progress_values) > 1:
            # Progress should generally increase
            first_progress = int(progress_values[0].replace('%', ''))
            last_progress = int(progress_values[-1].replace('%', ''))
            assert last_progress >= first_progress
        
        # Verify step messages are informative
        assert len(step_messages) > 0
        for step in step_messages:
            assert len(step.strip()) > 0
            assert step.strip() != "undefined"
    
    def test_responsive_design(self, page):
        """Test responsive design on different screen sizes"""
        # Test mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        page.reload()
        
        # Verify main elements are still accessible
        assert page.locator("#upload-section").is_visible()
        assert page.locator("#optimization-settings").is_visible()
        
        # Test tablet viewport
        page.set_viewport_size({"width": 768, "height": 1024})
        page.reload()
        
        # Verify layout adapts
        assert page.locator("#upload-section").is_visible()
        assert page.locator("#optimization-settings").is_visible()
        
        # Test desktop viewport
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.reload()
        
        # Verify all elements visible
        assert page.locator("#upload-section").is_visible()
        assert page.locator("#optimization-settings").is_visible()
    
    def test_admin_dashboard_access(self, page):
        """Test admin dashboard functionality"""
        # Navigate to admin analytics
        page.goto(f"{self.base_url}/admin/analytics")
        
        # Verify admin dashboard loads
        page.wait_for_selector("h1:has-text('Analytics')", timeout=10000)
        
        # Verify key analytics sections are present
        assert page.locator(".analytics-summary").is_visible()
        
        # Test stats endpoint
        page.goto(f"{self.base_url}/admin/stats")
        
        # Should return JSON data
        content = page.content()
        assert "total_tasks" in content or "database_status" in content
    
    def test_3d_model_viewer(self, page):
        """Test 3D model comparison viewer (if available)"""
        # Upload and optimize a file first
        file_input = page.locator('input[type="file"]')
        file_input.set_input_files(self.test_glb_file)
        
        start_button = page.locator('button:has-text("Start Optimization")')
        start_button.click()
        
        # Wait for results
        try:
            page.wait_for_selector("#results-section", state="visible", timeout=30000)
        except:
            pytest.skip("Optimization did not complete, skipping 3D viewer test")
        
        # Check if 3D viewer button is available
        viewer_button = page.locator('button:has-text("Compare 3D Models")')
        
        if viewer_button.is_visible():
            viewer_button.click()
            
            # Wait for 3D viewer to load
            page.wait_for_selector("#model-viewer", state="visible", timeout=10000)
            
            # Verify viewer controls are present
            assert page.locator(".viewer-controls").is_visible()
            
            # Test sync/unsync functionality
            if page.locator('button:has-text("Unsync Cameras")').is_visible():
                page.locator('button:has-text("Unsync Cameras")').click()
                
                # Should change to sync button
                page.wait_for_selector('button:has-text("Sync Cameras")', timeout=5000)
        else:
            pytest.skip("3D viewer not available")

class TestE2EPerformance:
    """Performance-focused E2E tests"""
    
    def test_page_load_performance(self, page):
        """Test page load performance metrics"""
        # Navigate to homepage and measure load time
        start_time = time.time()
        page.goto("http://localhost:5000")
        page.wait_for_load_state("networkidle")
        load_time = time.time() - start_time
        
        # Page should load within reasonable time
        assert load_time < 5.0, f"Page load time {load_time:.2f}s exceeds 5 seconds"
        
        # Verify critical elements loaded
        assert page.locator("#upload-section").is_visible()
        assert page.locator("#optimization-settings").is_visible()
    
    def test_upload_performance(self, page):
        """Test file upload performance"""
        # Create moderately sized test file (1MB)
        test_file = tempfile.NamedTemporaryFile(suffix='.glb', delete=False)
        with open(test_file.name, 'wb') as f:
            f.write(b'glTF' + b'\x02\x00\x00\x00' + (1024*1024).to_bytes(4, 'little'))
            f.write(b'\x00' * (1024*1024 - 12))
        
        try:
            page.goto("http://localhost:5000")
            
            # Measure upload time
            start_time = time.time()
            
            file_input = page.locator('input[type="file"]')
            file_input.set_input_files(test_file.name)
            
            start_button = page.locator('button:has-text("Start Optimization")')
            start_button.click()
            
            # Wait for upload to complete (progress section appears)
            page.wait_for_selector("#progress-section", state="visible", timeout=15000)
            upload_time = time.time() - start_time
            
            # Upload should complete within reasonable time
            assert upload_time < 10.0, f"Upload time {upload_time:.2f}s exceeds 10 seconds"
            
        finally:
            os.unlink(test_file.name)

# Fixtures for E2E tests requiring browser automation
@pytest.fixture(scope="session")
def browser_context_args():
    """Configure browser context for E2E tests"""
    return {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }

@pytest.fixture
def app_server():
    """Start application server for E2E tests"""
    # This fixture would start the actual application server
    # In practice, you might use a test server or docker container
    import subprocess
    
    # Start development server in background
    server_process = subprocess.Popen([
        "python", "develop.py"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Wait for server to start
    time.sleep(5)
    
    yield "http://localhost:5000"
    
    # Cleanup
    server_process.terminate()
    server_process.wait()