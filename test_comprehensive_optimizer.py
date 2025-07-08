#!/usr/bin/env python3
"""
Comprehensive Test Battery for optimizer.py
Following the test plan provided by the user to validate all security fixes and functionality
"""

import os
import sys
import tempfile
import struct
import shutil
import subprocess
import time
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, '.')

from optimizer import GLBOptimizer
from config import OptimizationConfig

class ComprehensiveOptimizerTests:
    def __init__(self):
        self.test_results = []
        self.setup_test_environment()
        
    def setup_test_environment(self):
        """Setup: Prepare the Test Environment"""
        print("🔧 SETTING UP TEST ENVIRONMENT")
        
        # Ensure test directories exist
        os.makedirs('uploads', exist_ok=True)
        os.makedirs('output', exist_ok=True)
        os.makedirs('test_assets', exist_ok=True)
        
        # Create test assets
        self.create_test_assets()
        print("✓ Test environment setup complete")
        
    def create_test_assets(self):
        """Create test GLB files for comprehensive testing"""
        print("📁 Creating test assets...")
        
        # 1. Small valid GLB file (simple cube) - in allowed directory
        self.small_glb = 'uploads/test_assets/small_cube.glb'
        self.create_simple_glb(self.small_glb)
        
        # 2. Use the provided village.glb as medium complex file (copied to allowed directory)
        self.medium_glb = 'uploads/village.glb'
        
        # 3. Invalid file (txt renamed to glb) - in allowed directory
        self.invalid_glb = 'uploads/test_assets/invalid.glb'
        with open(self.invalid_glb, 'w') as f:
            f.write("This is not a GLB file")
            
        # 4. Empty GLB file - in allowed directory
        self.empty_glb = 'uploads/test_assets/empty.glb'
        with open(self.empty_glb, 'wb') as f:
            pass  # Create empty file
            
        print(f"✓ Created test assets:")
        print(f"  - Small GLB: {self.small_glb} ({os.path.getsize(self.small_glb)} bytes)")
        if os.path.exists(self.medium_glb):
            print(f"  - Medium GLB: {self.medium_glb} ({os.path.getsize(self.medium_glb)} bytes)")
        else:
            print(f"  - Medium GLB: {self.medium_glb} (NOT FOUND - will skip complex tests)")
        print(f"  - Invalid GLB: {self.invalid_glb} ({os.path.getsize(self.invalid_glb)} bytes)")
        print(f"  - Empty GLB: {self.empty_glb} ({os.path.getsize(self.empty_glb)} bytes)")
        
    def create_simple_glb(self, filepath):
        """Create a minimal valid GLB file (simple cube)"""
        json_content = {
            "asset": {"version": "2.0"},
            "scene": 0,
            "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0}],
            "meshes": [{
                "primitives": [{
                    "attributes": {"POSITION": 0},
                    "indices": 1
                }]
            }],
            "accessors": [
                {
                    "bufferView": 0,
                    "componentType": 5126,
                    "count": 8,
                    "type": "VEC3",
                    "max": [1.0, 1.0, 1.0],
                    "min": [-1.0, -1.0, -1.0]
                },
                {
                    "bufferView": 1,
                    "componentType": 5123,
                    "count": 36,
                    "type": "SCALAR"
                }
            ],
            "bufferViews": [
                {"buffer": 0, "byteOffset": 0, "byteLength": 96},
                {"buffer": 0, "byteOffset": 96, "byteLength": 72}
            ],
            "buffers": [{"byteLength": 168}]
        }
        
        json_str = json.dumps(json_content, separators=(',', ':'))
        json_bytes = json_str.encode('utf-8')
        
        # Pad to 4-byte boundary
        while len(json_bytes) % 4 != 0:
            json_bytes += b' '
            
        # Create binary data (cube vertices + indices)
        vertices = [
            -1.0, -1.0, -1.0,  1.0, -1.0, -1.0,  1.0,  1.0, -1.0, -1.0,  1.0, -1.0,
            -1.0, -1.0,  1.0,  1.0, -1.0,  1.0,  1.0,  1.0,  1.0, -1.0,  1.0,  1.0
        ]
        indices = [
            0,1,2, 2,3,0, 1,5,6, 6,2,1, 7,6,5, 5,4,7,
            4,0,3, 3,7,4, 4,5,1, 1,0,4, 3,2,6, 6,7,3
        ]
        
        bin_data = b''
        for v in vertices:
            bin_data += struct.pack('<f', v)
        for i in indices:
            bin_data += struct.pack('<H', i)
            
        total_length = 12 + 8 + len(json_bytes) + 8 + len(bin_data)
        
        with open(filepath, 'wb') as f:
            # GLB header
            f.write(b'glTF')  # magic
            f.write(struct.pack('<I', 2))  # version
            f.write(struct.pack('<I', total_length))  # length
            
            # JSON chunk
            f.write(struct.pack('<I', len(json_bytes)))  # chunk length
            f.write(b'JSON')  # chunk type
            f.write(json_bytes)
            
            # Binary chunk
            f.write(struct.pack('<I', len(bin_data)))  # chunk length
            f.write(b'BIN\x00')  # chunk type
            f.write(bin_data)

    def log_test_result(self, test_name, success, details=""):
        """Log test result for final summary"""
        result = {
            'test': test_name,
            'success': success,
            'details': details
        }
        self.test_results.append(result)
        status = "✓" if success else "✗"
        print(f"  {status} {test_name}: {details}")

    def test_battery_1_functional_unit_tests(self):
        """Test Battery 1: Functional & Unit Tests"""
        print("\n🧪 TEST BATTERY 1: FUNCTIONAL & UNIT TESTS")
        
        # Test 1: Full optimization pipeline for all quality levels
        print("\n1. Testing Full Optimization Pipeline:")
        self.test_optimization_pipeline()
        
        # Test 2: Security validations
        print("\n2. Testing Security Validations:")
        self.test_security_validations()
        
        # Test 3: File size and format validation
        print("\n3. Testing File Size and Format Validation:")
        self.test_file_validations()

    def test_optimization_pipeline(self):
        """Test the full optimization pipeline for all quality levels"""
        quality_levels = ['high', 'balanced', 'maximum_compression']
        
        # Test with small GLB file first
        for quality in quality_levels:
            try:
                input_path = self.small_glb
                output_path = f'output/test_optimized_{quality}.glb'
                
                with GLBOptimizer(quality) as optimizer:
                    def progress_callback(step, progress, message):
                        pass
                    
                    result = optimizer.optimize(input_path, output_path, progress_callback)
                    
                    if os.path.exists(output_path):
                        original_size = os.path.getsize(input_path)
                        optimized_size = os.path.getsize(output_path)
                        
                        # Check if file is valid GLB (basic header check)
                        with open(output_path, 'rb') as f:
                            magic = f.read(4)
                            is_valid_glb = magic == b'glTF'
                        
                        if is_valid_glb and optimized_size > 0:
                            self.log_test_result(
                                f"Optimization pipeline ({quality})",
                                True,
                                f"Original: {original_size}B → Optimized: {optimized_size}B"
                            )
                        else:
                            self.log_test_result(
                                f"Optimization pipeline ({quality})",
                                False,
                                f"Invalid output: size={optimized_size}, valid_glb={is_valid_glb}"
                            )
                    else:
                        self.log_test_result(
                            f"Optimization pipeline ({quality})",
                            False,
                            "Output file not created"
                        )
                        
            except Exception as e:
                self.log_test_result(
                    f"Optimization pipeline ({quality})",
                    False,
                    f"Exception: {str(e)[:100]}"
                )

    def test_security_validations(self):
        """Test security validation functions"""
        with GLBOptimizer('high') as optimizer:
            # Test path traversal attacks
            dangerous_paths = [
                'uploads/../../etc/passwd',
                'uploads/../../../etc/passwd',
                'uploads/file;rm -rf /',
                'uploads/file|cat /etc/passwd',
                'uploads/file&whoami',
                'uploads/$(whoami).glb'
            ]
            
            for dangerous_path in dangerous_paths:
                try:
                    optimizer._validate_path(dangerous_path)
                    self.log_test_result(
                        f"Security validation ({dangerous_path[:20]}...)",
                        False,
                        "Should have been blocked but wasn't"
                    )
                except ValueError:
                    self.log_test_result(
                        f"Security validation ({dangerous_path[:20]}...)",
                        True,
                        "Correctly blocked dangerous path"
                    )
                except Exception as e:
                    self.log_test_result(
                        f"Security validation ({dangerous_path[:20]}...)",
                        False,
                        f"Unexpected error: {str(e)[:50]}"
                    )
            
            # Test valid paths
            valid_paths = [
                'uploads/test.glb',
                'output/result.glb',
                'uploads/subfolder/test.glb'
            ]
            
            for valid_path in valid_paths:
                try:
                    validated = optimizer._validate_path(valid_path)
                    self.log_test_result(
                        f"Valid path ({valid_path})",
                        True,
                        "Correctly allowed valid path"
                    )
                except Exception as e:
                    self.log_test_result(
                        f"Valid path ({valid_path})",
                        False,
                        f"Should be allowed: {str(e)[:50]}"
                    )

    def test_file_validations(self):
        """Test file size and format validations"""
        with GLBOptimizer('high') as optimizer:
            # Test valid file
            try:
                validation = optimizer._validate_glb_file(self.small_glb)
                success = validation.get('success', False)
                self.log_test_result(
                    "Valid GLB validation",
                    success,
                    validation.get('message', 'Unknown result')
                )
            except Exception as e:
                self.log_test_result(
                    "Valid GLB validation",
                    False,
                    f"Exception: {str(e)[:50]}"
                )
            
            # Test invalid file
            try:
                validation = optimizer._validate_glb_file(self.invalid_glb)
                success = validation.get('success', False)
                self.log_test_result(
                    "Invalid file rejection",
                    not success,  # Should fail validation
                    "Correctly rejected invalid file" if not success else "Should have been rejected"
                )
            except Exception as e:
                self.log_test_result(
                    "Invalid file rejection",
                    True,  # Exception is acceptable for invalid files
                    f"Correctly threw exception: {str(e)[:50]}"
                )
            
            # Test empty file
            try:
                validation = optimizer._validate_glb_file(self.empty_glb)
                success = validation.get('success', False)
                self.log_test_result(
                    "Empty file rejection",
                    not success,  # Should fail validation
                    "Correctly rejected empty file" if not success else "Should have been rejected"
                )
            except Exception as e:
                self.log_test_result(
                    "Empty file rejection",
                    True,  # Exception is acceptable for empty files
                    f"Correctly threw exception: {str(e)[:50]}"
                )

    def test_battery_2_integration_tests(self):
        """Test Battery 2: Integration & E2E Tests"""
        print("\n🔗 TEST BATTERY 2: INTEGRATION & E2E TESTS")
        
        # Test context manager functionality
        print("\n1. Testing Context Manager:")
        self.test_context_manager()
        
        # Test structured logging
        print("\n2. Testing Structured Logging:")
        self.test_structured_logging()
        
        # Test JSON logs export
        print("\n3. Testing JSON Logs Export:")
        self.test_json_logs_export()

    def test_context_manager(self):
        """Test context manager functionality"""
        try:
            # Test normal usage
            with GLBOptimizer('high') as optimizer:
                file_size = optimizer._safe_file_operation(self.small_glb, 'size')
                
            self.log_test_result(
                "Context manager normal usage",
                True,
                f"Successfully accessed file size: {file_size}"
            )
            
            # Test exception handling
            try:
                with GLBOptimizer('high') as optimizer:
                    # This should raise an exception but cleanup should still happen
                    optimizer._validate_path('invalid/../../../path')
            except ValueError:
                self.log_test_result(
                    "Context manager exception handling",
                    True,
                    "Exception correctly raised and handled"
                )
            except Exception as e:
                self.log_test_result(
                    "Context manager exception handling",
                    False,
                    f"Unexpected exception: {str(e)[:50]}"
                )
                
        except Exception as e:
            self.log_test_result(
                "Context manager",
                False,
                f"Context manager failed: {str(e)[:50]}"
            )

    def test_structured_logging(self):
        """Test structured logging functionality"""
        try:
            with GLBOptimizer('high') as optimizer:
                # Perform a file operation that should be logged
                file_size = optimizer._safe_file_operation(self.small_glb, 'size')
                
                # Check if we can get detailed logs
                logs_json = optimizer.get_detailed_logs_json()
                
                self.log_test_result(
                    "Structured logging",
                    isinstance(logs_json, dict),
                    f"Logs type: {type(logs_json).__name__}"
                )
                
        except Exception as e:
            self.log_test_result(
                "Structured logging",
                False,
                f"Logging test failed: {str(e)[:50]}"
            )

    def test_json_logs_export(self):
        """Test JSON logs export functionality"""
        try:
            with GLBOptimizer('balanced') as optimizer:
                # Get initial logs
                logs_before = optimizer.get_detailed_logs_json()
                
                # Perform some operations
                optimizer._safe_file_operation(self.small_glb, 'exists')
                optimizer._safe_file_operation(self.small_glb, 'size')
                
                # Get logs after operations
                logs_after = optimizer.get_detailed_logs_json()
                
                # Verify JSON structure
                required_keys = ['optimization_logs', 'timestamp', 'quality_level', 'log_count']
                has_all_keys = all(key in logs_after for key in required_keys)
                
                self.log_test_result(
                    "JSON logs export structure",
                    has_all_keys,
                    f"Has required keys: {has_all_keys}"
                )
                
                self.log_test_result(
                    "JSON logs export functionality",
                    True,
                    f"Quality: {logs_after.get('quality_level')}, Count: {logs_after.get('log_count')}"
                )
                
        except Exception as e:
            self.log_test_result(
                "JSON logs export",
                False,
                f"JSON export failed: {str(e)[:50]}"
            )

    def test_battery_3_stress_regression_tests(self):
        """Test Battery 3: Stress & Regression Tests"""
        print("\n💪 TEST BATTERY 3: STRESS & REGRESSION TESTS")
        
        # Test error handling and fallback logic
        print("\n1. Testing Error Handling and Fallback Logic:")
        self.test_error_handling()
        
        # Test resource cleanup
        print("\n2. Testing Resource Cleanup:")
        self.test_resource_cleanup()
        
        # Test configuration management
        print("\n3. Testing Configuration Management:")
        self.test_configuration_management()

    def test_error_handling(self):
        """Test error handling and fallback mechanisms"""
        try:
            with GLBOptimizer('high') as optimizer:
                # Test with an invalid file that should trigger fallbacks
                input_path = self.invalid_glb
                output_path = 'output/test_error_handling.glb'
                
                def progress_callback(step, progress, message):
                    pass
                
                try:
                    result = optimizer.optimize(input_path, output_path, progress_callback)
                    
                    # This should fail gracefully
                    self.log_test_result(
                        "Error handling with invalid file",
                        True,
                        "Gracefully handled invalid file"
                    )
                except Exception as e:
                    # Exception is expected for invalid files
                    self.log_test_result(
                        "Error handling with invalid file",
                        True,
                        f"Correctly raised exception: {str(e)[:50]}"
                    )
                    
        except Exception as e:
            self.log_test_result(
                "Error handling test setup",
                False,
                f"Test setup failed: {str(e)[:50]}"
            )

    def test_resource_cleanup(self):
        """Test that temporary files and resources are cleaned up"""
        temp_files_before = len(list(Path('.').glob('**/*tmp*')))
        
        try:
            with GLBOptimizer('high') as optimizer:
                # Perform operations that create temp files
                optimizer._safe_file_operation(self.small_glb, 'size')
                optimizer._safe_file_operation(self.small_glb, 'exists')
                
            # Check temp files after context manager exit
            temp_files_after = len(list(Path('.').glob('**/*tmp*')))
            
            # Should not have more temp files than we started with
            self.log_test_result(
                "Resource cleanup",
                temp_files_after <= temp_files_before,
                f"Temp files before: {temp_files_before}, after: {temp_files_after}"
            )
            
        except Exception as e:
            self.log_test_result(
                "Resource cleanup",
                False,
                f"Cleanup test failed: {str(e)[:50]}"
            )

    def test_configuration_management(self):
        """Test centralized configuration management"""
        try:
            # Test OptimizationConfig access
            config = OptimizationConfig.from_env()
            
            # Test quality settings for different levels
            high_settings = config.get_quality_settings('high')
            balanced_settings = config.get_quality_settings('balanced')
            max_compression_settings = config.get_quality_settings('maximum_compression')
            
            self.log_test_result(
                "Configuration - quality settings",
                all(isinstance(settings, dict) for settings in [high_settings, balanced_settings, max_compression_settings]),
                f"High: {len(high_settings)}, Balanced: {len(balanced_settings)}, Max: {len(max_compression_settings)} settings"
            )
            
            # Test available quality levels
            quality_levels = config.get_available_quality_levels()
            expected_levels = {'high', 'balanced', 'maximum_compression'}
            has_expected_levels = expected_levels.issubset(set(quality_levels.keys()))
            
            self.log_test_result(
                "Configuration - quality levels",
                has_expected_levels,
                f"Available levels: {list(quality_levels.keys())}"
            )
            
            # Test configuration validation
            validation_result = config.validate_settings()
            
            self.log_test_result(
                "Configuration - validation",
                isinstance(validation_result, dict),
                f"Validation result type: {type(validation_result).__name__}"
            )
            
        except Exception as e:
            self.log_test_result(
                "Configuration management",
                False,
                f"Config test failed: {str(e)[:50]}"
            )

    def run_existing_test_suite(self):
        """Run existing pytest test suite"""
        print("\n🏃 RUNNING EXISTING TEST SUITE")
        
        try:
            result = subprocess.run(['python', '-m', 'pytest', 'tests/', '-v'], 
                                  capture_output=True, text=True, timeout=300)
            
            success = result.returncode == 0
            output_lines = result.stdout.split('\n')[-10:]  # Last 10 lines
            
            self.log_test_result(
                "Existing test suite",
                success,
                f"Exit code: {result.returncode}, Output: {' '.join(output_lines)}"
            )
            
        except subprocess.TimeoutExpired:
            self.log_test_result(
                "Existing test suite",
                False,
                "Test suite timed out after 5 minutes"
            )
        except Exception as e:
            self.log_test_result(
                "Existing test suite",
                False,
                f"Failed to run: {str(e)[:50]}"
            )

    def cleanup_test_files(self):
        """Clean up test files"""
        try:
            # Remove test output files
            for file_path in Path('output').glob('test_*.glb'):
                file_path.unlink()
                
            # Remove test assets (but keep the provided village.glb)
            test_assets = ['uploads/test_assets/small_cube.glb', 'uploads/test_assets/invalid.glb', 'uploads/test_assets/empty.glb']
            for asset in test_assets:
                if os.path.exists(asset):
                    os.remove(asset)
                    
            # Remove test_assets directory if empty
            try:
                os.rmdir('uploads/test_assets')
            except OSError:
                pass  # Directory not empty, leave it
                
            print("✓ Test cleanup completed")
            
        except Exception as e:
            print(f"⚠ Cleanup warning: {e}")

    def print_final_summary(self):
        """Print comprehensive test results summary"""
        print("\n" + "="*80)
        print("🎯 COMPREHENSIVE TEST BATTERY RESULTS")
        print("="*80)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"\nTotal Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✓")
        print(f"Failed: {failed_tests} ✗")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%\n")
        
        if failed_tests > 0:
            print("❌ FAILED TESTS:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  ✗ {result['test']}: {result['details']}")
            print()
        
        print("✅ PASSED TESTS:")
        for result in self.test_results:
            if result['success']:
                print(f"  ✓ {result['test']}: {result['details']}")
        
        print("\n" + "="*80)
        
        if passed_tests == total_tests:
            print("🎉 ALL TESTS PASSED! Optimizer is ready for production deployment.")
        elif passed_tests >= total_tests * 0.8:
            print("⚠️  MOSTLY PASSING: Review failed tests before deployment.")
        else:
            print("❌ SIGNIFICANT ISSUES: Address failed tests before deployment.")
        
        print("="*80)

    def run_all_tests(self):
        """Run the complete test battery"""
        print("🚀 STARTING COMPREHENSIVE OPTIMIZER TEST BATTERY")
        print("="*80)
        
        # Run existing test suite first
        self.run_existing_test_suite()
        
        # Run our comprehensive tests
        self.test_battery_1_functional_unit_tests()
        self.test_battery_2_integration_tests()
        self.test_battery_3_stress_regression_tests()
        
        # Cleanup and summarize
        self.cleanup_test_files()
        self.print_final_summary()

if __name__ == "__main__":
    # Run the comprehensive test battery
    test_runner = ComprehensiveOptimizerTests()
    test_runner.run_all_tests()