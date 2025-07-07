import os
import subprocess
import tempfile
import time
import logging
import shutil
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional

class GLBOptimizer:
    def __init__(self, quality_level='high'):
        """
        Initialize GLB Optimizer
        quality_level: 'high' (default), 'balanced', or 'maximum_compression'
        """
        self.logger = logging.getLogger(__name__)
        self.quality_level = quality_level
        self.detailed_logs = []  # Store detailed error logs for user download
        
        # Security: Define allowed base directories for file operations
        # Only allow uploads and output directories for security
        self.allowed_dirs = {
            os.path.abspath('uploads'),
            os.path.abspath('output')
        }
    
    def _validate_path(self, file_path: str, allow_temp: bool = False) -> str:
        """
        Security: Validate and sanitize file paths to prevent command injection
        Returns: Validated absolute path or raises ValueError
        """
        try:
            # Convert to absolute path and resolve any path traversal attempts
            abs_path = os.path.abspath(file_path)
            
            # Security: Ensure path doesn't contain dangerous characters
            if any(char in abs_path for char in [';', '|', '&', '$', '`', '>', '<', '\n', '\r']):
                raise ValueError(f"Path contains dangerous characters: {file_path}")
            
            # Security: Ensure path is within allowed directories
            path_allowed = False
            
            # Check against allowed directories
            for allowed_dir in self.allowed_dirs:
                try:
                    # Check if the path is within an allowed directory
                    Path(abs_path).relative_to(Path(allowed_dir))
                    path_allowed = True
                    break
                except ValueError:
                    continue
            
            # If temp paths are allowed, check if it's in system temp directory
            if not path_allowed and allow_temp:
                try:
                    Path(abs_path).relative_to(Path(tempfile.gettempdir()))
                    path_allowed = True
                except ValueError:
                    pass
            
            if not path_allowed:
                raise ValueError(f"Path outside allowed directories: {file_path}")
            
            # Security: Additional validation for GLB files
            if not abs_path.endswith('.glb'):
                raise ValueError(f"Path must be a .glb file: {file_path}")
            
            return abs_path
            
        except Exception as e:
            self.logger.error(f"Path validation failed for {file_path}: {e}")
            raise ValueError(f"Invalid or unsafe file path: {file_path}")
        
    def _run_subprocess(self, cmd: list, step_name: str, description: str) -> Dict[str, Any]:
        """
        Run subprocess with comprehensive error handling and logging
        Security: All file paths in commands are validated before execution
        """
        try:
            # Security: Validate all file paths in the command
            validated_cmd = []
            for arg in cmd:
                if arg.endswith('.glb') and os.path.sep in arg:
                    # This looks like a file path - validate it
                    try:
                        # Allow temp paths for intermediate processing files
                        validated_path = self._validate_path(arg, allow_temp=True)
                        validated_cmd.append(validated_path)
                    except ValueError as e:
                        # If validation fails, reject the command
                        self.logger.error(f"Security: Blocked potentially dangerous path in command: {arg}")
                        raise ValueError(f"Command contains invalid file path: {arg}")
                else:
                    validated_cmd.append(arg)
            
            self.logger.info(f"Running {step_name}: {' '.join(validated_cmd)}")
            
            # Run subprocess with full output capture
            result = subprocess.run(
                validated_cmd, 
                capture_output=True, 
                text=True, 
                timeout=300,  # 5 minute timeout
                cwd=os.getcwd()
            )
            
            # Log all output for debugging
            if result.stdout:
                self.logger.debug(f"{step_name} stdout: {result.stdout}")
                
            if result.stderr:
                self.logger.debug(f"{step_name} stderr: {result.stderr}")
                
            if result.returncode == 0:
                return {
                    'success': True,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'step': step_name
                }
            else:
                error_details = self._analyze_error(result.stderr, result.stdout, step_name)
                detailed_log = {
                    'step': step_name,
                    'description': description,
                    'command': ' '.join(validated_cmd),  # Log the validated command, not original
                    'exit_code': result.returncode,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'analysis': error_details,
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                self.detailed_logs.append(detailed_log)
                
                return {
                    'success': False,
                    'error': error_details['user_message'],
                    'detailed_error': error_details['technical_details'],
                    'step': step_name,
                    'logs': detailed_log
                }
                
        except subprocess.TimeoutExpired:
            error_msg = f"{step_name} timed out after 5 minutes"
            self.logger.error(error_msg)
            return {
                'success': False,
                'error': f"{description} took too long and was stopped. This usually indicates a very complex model or insufficient system resources.",
                'detailed_error': error_msg,
                'step': step_name
            }
            
        except FileNotFoundError:
            error_msg = f"Required tool not found for {step_name}"
            self.logger.error(error_msg)
            return {
                'success': False,
                'error': f"Required optimization tool is not installed. Please contact support.",
                'detailed_error': error_msg,
                'step': step_name
            }
            
        except Exception as e:
            error_msg = f"Unexpected error in {step_name}: {str(e)}"
            self.logger.error(error_msg)
            return {
                'success': False,
                'error': f"An unexpected error occurred during {description.lower()}.",
                'detailed_error': error_msg,
                'step': step_name
            }
    
    def _analyze_error(self, stderr: str, stdout: str, step_name: str) -> Dict[str, str]:
        """
        Analyze error output and provide user-friendly explanations
        """
        combined_output = (stderr + stdout).lower()
        
        # Common error patterns and user-friendly explanations
        error_patterns = {
            'out of memory': {
                'user_message': 'The model is too large for available memory. Try using "Maximum Compression" quality level or reduce the model complexity.',
                'category': 'Resource Limitation'
            },
            'unsupported format': {
                'user_message': 'The GLB file contains unsupported features or corrupted data. Please verify the file is a valid GLB.',
                'category': 'File Format Error'
            },
            'texture compression failed': {
                'user_message': 'Texture optimization failed, possibly due to unsupported image formats. The model may contain non-standard textures.',
                'category': 'Texture Processing Error'
            },
            'mesh optimization failed': {
                'user_message': 'Geometry optimization failed. The model may have invalid mesh data or unsupported mesh features.',
                'category': 'Geometry Processing Error'
            },
            'animation compression failed': {
                'user_message': 'Animation optimization failed. The model may contain complex or corrupted animation data.',
                'category': 'Animation Processing Error'
            },
            'draco': {
                'user_message': 'Draco compression failed. Trying alternative compression method.',
                'category': 'Compression Error'
            },
            'ktx2': {
                'user_message': 'Advanced texture compression failed. Falling back to standard compression.',
                'category': 'Texture Compression Error'
            },
            'basis': {
                'user_message': 'Basis Universal texture compression failed. Using fallback compression.',
                'category': 'Texture Compression Error'
            },
            'file not found': {
                'user_message': 'Required file was not found during processing. This may indicate file corruption.',
                'category': 'File System Error'
            },
            'permission denied': {
                'user_message': 'File access permission denied. Please try uploading the file again.',
                'category': 'File System Error'
            },
            'invalid gltf': {
                'user_message': 'The GLB file is corrupted or invalid. Please verify the file is properly exported.',
                'category': 'File Format Error'
            },
            'node.js': {
                'user_message': 'JavaScript optimization tool error. This is usually a temporary issue.',
                'category': 'Tool Error'
            }
        }
        
        # Find matching error pattern
        for pattern, info in error_patterns.items():
            if pattern in combined_output:
                return {
                    'user_message': info['user_message'],
                    'category': info['category'],
                    'technical_details': f"{step_name} failed: {stderr[:500]}..." if len(stderr) > 500 else stderr
                }
        
        # Generic error handling
        if stderr:
            return {
                'user_message': f'Optimization step "{step_name}" failed. This may be due to complex model features or file corruption.',
                'category': 'Processing Error',
                'technical_details': f"{step_name} error: {stderr[:500]}..." if len(stderr) > 500 else stderr
            }
        
        return {
            'user_message': f'Optimization step "{step_name}" failed for an unknown reason.',
            'category': 'Unknown Error',
            'technical_details': f"No error details available for {step_name}"
        }
    
    def get_detailed_logs(self) -> str:
        """
        Get formatted detailed logs for user download
        """
        if not self.detailed_logs:
            return "No detailed error logs available."
            
        log_content = []
        log_content.append("GLB Optimization Error Report")
        log_content.append("=" * 40)
        log_content.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        log_content.append("")
        
        for i, log in enumerate(self.detailed_logs, 1):
            log_content.append(f"Error #{i}: {log['step']}")
            log_content.append("-" * 30)
            log_content.append(f"Description: {log['description']}")
            log_content.append(f"Command: {log['command']}")
            log_content.append(f"Exit Code: {log['exit_code']}")
            log_content.append(f"Timestamp: {log['timestamp']}")
            log_content.append("")
            log_content.append("Error Analysis:")
            log_content.append(f"  Category: {log['analysis']['category']}")
            log_content.append(f"  User Message: {log['analysis']['user_message']}")
            log_content.append("")
            log_content.append("Technical Details:")
            if log['stdout']:
                log_content.append("STDOUT:")
                log_content.append(log['stdout'])
                log_content.append("")
            if log['stderr']:
                log_content.append("STDERR:")
                log_content.append(log['stderr'])
                log_content.append("")
            log_content.append("=" * 40)
            log_content.append("")
            
        return "\n".join(log_content)
    
    def optimize(self, input_path, output_path, progress_callback=None):
        """
        Optimize a GLB file using the industry-standard 6-step workflow
        """
        start_time = time.time()
        
        try:
            # Security: Validate all file paths before any operations
            validated_input = self._validate_path(input_path)
            validated_output = self._validate_path(output_path)
            
            self.logger.info(f"Starting optimization with validated paths: {validated_input} -> {validated_output}")
            
            # Verify input file exists and is readable
            if not os.path.exists(validated_input):
                return {
                    'success': False,
                    'error': f'Input file does not exist: {input_path}',
                    'user_message': 'The uploaded file could not be found. Please try uploading again.',
                    'category': 'File System Error'
                }
            
            # Additional security: Ensure paths are within expected directories
            expected_upload_dir = os.path.abspath('uploads')
            expected_output_dir = os.path.abspath('output')
            
            if not (validated_input.startswith(expected_upload_dir) or validated_input.startswith(expected_output_dir)):
                self.logger.error(f"Security violation: Input path outside allowed directories: {validated_input}")
                return {
                    'success': False,
                    'error': 'Security violation: Invalid input path',
                    'user_message': 'File access denied for security reasons.',
                    'category': 'Security Error'
                }
            
            if not validated_output.startswith(expected_output_dir):
                self.logger.error(f"Security violation: Output path outside allowed directories: {validated_output}")
                return {
                    'success': False,
                    'error': 'Security violation: Invalid output path',
                    'user_message': 'File access denied for security reasons.',
                    'category': 'Security Error'
                }
            # Create temporary directory for intermediate files
            with tempfile.TemporaryDirectory() as temp_dir:
                
                # Step 1: Strip the fat first (cleanup & deduplication)
                if progress_callback:
                    progress_callback("Step 1: Cleanup & Deduplication", 10, "Pruning unused data...")
                
                step1_output = os.path.join(temp_dir, "step1_pruned.glb")
                result = self._run_gltf_transform_prune(validated_input, step1_output)
                if not result['success']:
                    return result
                
                # Step 2: Weld and join meshes
                if progress_callback:
                    progress_callback("Step 1: Cleanup & Deduplication", 20, "Welding and joining meshes...")
                
                step2_output = os.path.join(temp_dir, "step2_welded.glb")
                result = self._run_gltf_transform_weld(step1_output, step2_output)
                if not result['success']:
                    return result
                
                # Step 3: Advanced geometry compression with intelligent method selection
                if progress_callback:
                    progress_callback("Step 2: Geometry Compression", 40, "Analyzing model for optimal compression...")
                
                step3_output = os.path.join(temp_dir, "step3_compressed.glb")
                result = self._run_advanced_geometry_compression(step2_output, step3_output, progress_callback)
                if not result['success']:
                    return result
                
                # Step 4: Compress textures with KTX2/BasisU
                if progress_callback:
                    progress_callback("Step 3: Texture Compression", 60, "Compressing textures with KTX2...")
                
                step4_output = os.path.join(temp_dir, "step4_textures.glb")
                result = self._run_gltf_transform_textures(step3_output, step4_output)
                if not result['success']:
                    return result
                
                # Step 5: Optimize animations (if any)
                if progress_callback:
                    progress_callback("Step 4: Animation Optimization", 75, "Optimizing animations...")
                
                step5_output = os.path.join(temp_dir, "step5_animations.glb")
                result = self._run_gltf_transform_animations(step4_output, step5_output)
                if not result['success']:
                    return result
                
                # Step 6: Final bundle and minify
                if progress_callback:
                    progress_callback("Step 5: Final Optimization", 90, "Final bundling and minification...")
                
                result = self._run_gltfpack_final(step5_output, validated_output)
                if not result['success']:
                    return result
                
                if progress_callback:
                    progress_callback("Step 6: Completed", 100, "Optimization completed successfully!")
                
                processing_time = time.time() - start_time
                return {
                    'success': True,
                    'processing_time': processing_time,
                    'message': 'Optimization completed successfully'
                }
        
        except Exception as e:
            self.logger.error(f"Optimization failed: {str(e)}")
            return {
                'success': False,
                'error': f'Optimization failed: {str(e)}'
            }
    
    def _run_gltf_transform_prune(self, input_path, output_path):
        """Step 1: Prune unused data"""
        cmd = ['npx', 'gltf-transform', 'prune', input_path, output_path]
        return self._run_subprocess(cmd, "Prune Unused Data", "Removing unused data and orphaned nodes")
    
    def _run_gltf_transform_weld(self, input_path, output_path):
        """Step 2: Weld vertices and join meshes"""
        try:
            # First weld vertices
            temp_welded = input_path + '.welded.glb'
            cmd = ['npx', 'gltf-transform', 'weld', '--tolerance', '0.0001', input_path, temp_welded]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                self.logger.warning(f"Welding failed, continuing: {result.stderr}")
                # If welding fails, just copy the file
                shutil.copy2(input_path, output_path)
                return {'success': True}
            
            # Then join meshes
            cmd = ['npx', 'gltf-transform', 'join', temp_welded, output_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            # Clean up temp file
            try:
                os.remove(temp_welded)
            except:
                pass
            
            if result.returncode != 0:
                self.logger.warning(f"Joining failed, using welded version: {result.stderr}")
                shutil.copy2(temp_welded, output_path)
                return {'success': True}
            
            return {'success': True}
        
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Welding/joining operation timed out'}
        except Exception as e:
            return {'success': False, 'error': f'Welding/joining failed: {str(e)}'}
    
    def _run_gltfpack_geometry(self, input_path, output_path):
        """Step 3: Advanced geometry compression with meshopt and aggressive optimization"""
        # Quality-based simplification levels
        simplify_ratio = {
            'high': '0.8',  # 80% triangle count (preserve quality)
            'balanced': '0.6',  # 60% triangle count (balance quality/size)
            'maximum_compression': '0.4'  # 40% triangle count (maximum compression)
        }.get(self.quality_level, '0.7')
        
        # Advanced meshopt compression with aggressive settings
        cmd = [
            'gltfpack',
            '-i', input_path,
            '-o', output_path,
            '--meshopt',  # Enable meshopt compression
            '--quantize',  # Quantize vertex attributes
            '--simplify', simplify_ratio,  # Polygon simplification
            '--simplify-error', '0.01',  # Low error threshold for quality
            '--attributes',  # Optimize vertex attributes
            '--indices',  # Optimize index buffers
            '--normals',  # Optimize normal vectors
            '--tangents',  # Optimize tangent vectors
            '--join',  # Join compatible meshes
            '--dedup',  # Remove duplicate vertices
            '--reorder',  # Reorder primitives for GPU efficiency
            '--sparse',  # Use sparse accessors when beneficial
        ]
        
        # Add quality-specific options
        if self.quality_level == 'maximum_compression':
            cmd.extend([
                '--simplify-aggressive',  # More aggressive simplification
                '--simplify-lock-border',  # Preserve mesh borders
            ])
        
        result = self._run_subprocess(cmd, "Advanced Geometry Compression", "Applying meshopt with aggressive optimization")
        
        if not result['success']:
            self.logger.warning(f"Advanced geometry compression failed, trying basic meshopt: {result.get('error', 'Unknown error')}")
            # Fallback to basic meshopt compression
            cmd_fallback = [
                'gltfpack',
                '-i', input_path,
                '-o', output_path,
                '--meshopt',
                '--quantize'
            ]
            fallback_result = self._run_subprocess(cmd_fallback, "Basic Geometry Compression", "Applying basic meshopt compression")
            return fallback_result
        
        return result
    
    def _run_draco_compression(self, input_path, output_path):
        """Advanced Draco geometry compression for maximum compression"""
        # Quality-based compression levels for Draco
        compression_settings = {
            'high': {
                'position_bits': '12',  # High precision for positions
                'normal_bits': '8',     # Good precision for normals
                'color_bits': '8',      # Full color precision
                'tex_coord_bits': '10', # High texture coordinate precision
                'compression_level': '7' # Balanced compression
            },
            'balanced': {
                'position_bits': '10',  # Reduced position precision
                'normal_bits': '6',     # Lower normal precision
                'color_bits': '6',      # Reduced color precision
                'tex_coord_bits': '8',  # Lower texture precision
                'compression_level': '8' # Higher compression
            },
            'maximum_compression': {
                'position_bits': '8',   # Minimal position precision
                'normal_bits': '4',     # Minimal normal precision
                'color_bits': '4',      # Minimal color precision
                'tex_coord_bits': '6',  # Minimal texture precision
                'compression_level': '10' # Maximum compression
            }
        }
        
        settings = compression_settings.get(self.quality_level, compression_settings['balanced'])
        
        try:
            # Use gltf-transform with advanced Draco settings
            cmd = [
                'npx', 'gltf-transform', 'draco',
                '--method', 'edgebreaker',  # Best compression method
                '--encodeSpeed', '0',       # Favor compression over speed
                '--decodeSpeed', '5',       # Balance decode speed
                '--quantizePosition', settings['position_bits'],
                '--quantizeNormal', settings['normal_bits'],
                '--quantizeColor', settings['color_bits'],
                '--quantizeTexcoord', settings['tex_coord_bits'],
                '--compressionLevel', settings['compression_level'],
                '--unifiedQuantization',    # Better compression
                input_path, output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode != 0:
                self.logger.error(f"Advanced Draco compression failed: {result.stderr}")
                # Try basic Draco compression as fallback
                cmd_fallback = [
                    'npx', 'gltf-transform', 'draco',
                    '--method', 'edgebreaker',
                    input_path, output_path
                ]
                fallback_result = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=600)
                
                if fallback_result.returncode != 0:
                    return {
                        'success': False,
                        'error': f'Draco compression failed: {fallback_result.stderr}'
                    }
            
            return {'success': True}
        
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Draco compression timed out'}
        except Exception as e:
            return {'success': False, 'error': f'Draco compression failed: {str(e)}'}
    
    def _run_advanced_geometry_compression(self, input_path, output_path, progress_callback=None):
        """Advanced geometry compression with intelligent method selection and adaptive strategy"""
        import os
        import tempfile
        import json
        
        # First, analyze the model to determine optimal compression strategy
        if progress_callback:
            progress_callback("Step 2: Geometry Compression", 40, "Analyzing model complexity...")
        
        model_analysis = self._analyze_model_complexity(input_path)
        
        # Create temporary files for testing selected methods based on analysis
        temp_dir = os.path.dirname(output_path)
        meshopt_output = os.path.join(temp_dir, "test_meshopt.glb")
        draco_output = os.path.join(temp_dir, "test_draco.glb")
        hybrid_output = os.path.join(temp_dir, "test_hybrid.glb")
        
        results = {}
        file_sizes = {}
        
        # Select compression methods based on model characteristics
        methods_to_test = self._select_compression_methods(model_analysis)
        
        # Test selected compression methods based on model analysis
        progress_step = 41
        
        for method in methods_to_test:
            if progress_callback:
                method_name = method.replace('_', ' ').title()
                progress_callback("Step 2: Geometry Compression", progress_step, f"Testing {method_name} compression...")
            
            if method == 'meshopt':
                results['meshopt'] = self._run_gltfpack_geometry(input_path, meshopt_output)
                if results['meshopt']['success'] and os.path.exists(meshopt_output):
                    file_sizes['meshopt'] = os.path.getsize(meshopt_output)
                    self.logger.info(f"Enhanced Meshopt: {file_sizes['meshopt']} bytes")
            
            elif method == 'draco':
                results['draco'] = self._run_draco_compression(input_path, draco_output)
                if results['draco']['success'] and os.path.exists(draco_output):
                    file_sizes['draco'] = os.path.getsize(draco_output)
                    self.logger.info(f"Advanced Draco: {file_sizes['draco']} bytes")
            
            elif method == 'hybrid':
                results['hybrid'] = self._run_gltf_transform_optimize(input_path, hybrid_output)
                if results['hybrid']['success'] and os.path.exists(hybrid_output):
                    file_sizes['hybrid'] = os.path.getsize(hybrid_output)
                    self.logger.info(f"Hybrid optimization: {file_sizes['hybrid']} bytes")
            
            progress_step += 2
        
        # Find the best compression method based on file size and success
        successful_methods = {method: size for method, size in file_sizes.items() 
                            if results[method]['success']}
        
        if not successful_methods:
            self.logger.error("All compression methods failed")
            # Cleanup temp files
            for temp_file in [meshopt_output, draco_output, hybrid_output]:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except:
                    pass
            return results.get('meshopt', {'success': False, 'error': 'All compression methods failed'})
        
        # Select the method with the smallest file size
        best_method = min(successful_methods.items(), key=lambda x: x[1])
        selected_method = best_method[0]
        selected_size = best_method[1]
        
        # Map method names to file paths
        method_files = {
            'meshopt': meshopt_output,
            'draco': draco_output,
            'hybrid': hybrid_output
        }
        selected_file = method_files[selected_method]
        
        # Log compression comparison
        compression_info = []
        for method, size in successful_methods.items():
            status = "SELECTED" if method == selected_method else ""
            compression_info.append(f"{method.title()}: {size} bytes {status}")
        
        self.logger.info(f"Compression results: {', '.join(compression_info)}")
        
        # Copy the best result to the final output
        if progress_callback:
            progress_callback("Step 2: Geometry Compression", 48, f"Finalizing {selected_method} compression...")
        
        try:
            import shutil
            shutil.copy2(selected_file, output_path)
            
            # Cleanup temp files
            for temp_file in [meshopt_output, draco_output]:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except:
                    pass
            
            # Calculate compression ratio for logging
            input_size = os.path.getsize(input_path)
            output_size = os.path.getsize(output_path)
            compression_ratio = (1 - output_size / input_size) * 100
            
            self.logger.info(f"Geometry compression ({selected_method}): {input_size} → {output_size} bytes ({compression_ratio:.1f}% reduction)")
            
            return {
                'success': True,
                'method': selected_method,
                'compression_ratio': compression_ratio,
                'input_size': input_size,
                'output_size': output_size
            }
            
        except Exception as e:
            self.logger.error(f"Failed to finalize compression: {str(e)}")
            return {'success': False, 'error': f'Failed to finalize compression: {str(e)}'}
    
    def _run_gltf_transform_optimize(self, input_path, output_path):
        """Hybrid optimization using gltf-transform's comprehensive optimize command"""
        # Quality-based optimization settings
        quality_settings = {
            'high': {
                'compress': 'meshopt',  # Use meshopt for better compatibility
                'instance': True,       # Instance repeated geometry
                'simplify': '0.8',      # Light simplification
                'weld': '0.0001'        # Precise vertex welding
            },
            'balanced': {
                'compress': 'draco',    # Use Draco for better compression
                'instance': True,
                'simplify': '0.6',      # Moderate simplification  
                'weld': '0.001'         # Moderate vertex welding
            },
            'maximum_compression': {
                'compress': 'draco',    # Use Draco for maximum compression
                'instance': True,
                'simplify': '0.4',      # Aggressive simplification
                'weld': '0.01',         # Aggressive vertex welding
                'quantize': '16'        # Quantize positions
            }
        }
        
        settings = quality_settings.get(self.quality_level, quality_settings['balanced'])
        
        try:
            # Build gltf-transform optimize command
            cmd = [
                'npx', 'gltf-transform', 'optimize',
                input_path, output_path,
                '--compress', settings['compress']
            ]
            
            # Add conditional parameters
            if settings.get('instance'):
                cmd.append('--instance')
            
            if settings.get('simplify'):
                cmd.extend(['--simplify', settings['simplify']])
            
            if settings.get('weld'):
                cmd.extend(['--weld', settings['weld']])
            
            if settings.get('quantize'):
                cmd.extend(['--quantize', settings['quantize']])
            
            # Add additional optimization flags
            cmd.extend([
                '--join',       # Join compatible primitives
                '--palette',    # Optimize texture palettes
                '--sparse'      # Use sparse accessors when beneficial
            ])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode != 0:
                self.logger.error(f"gltf-transform optimize failed: {result.stderr}")
                return {
                    'success': False,
                    'error': f'Hybrid optimization failed: {result.stderr}'
                }
            
            return {'success': True}
            
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Hybrid optimization timed out'}
        except Exception as e:
            return {'success': False, 'error': f'Hybrid optimization failed: {str(e)}'}
    
    def _analyze_model_complexity(self, input_path):
        """Analyze model characteristics to determine optimal compression strategy"""
        try:
            # Use gltf-transform inspect to analyze the model
            cmd = ['npx', 'gltf-transform', 'inspect', input_path, '--format', 'json']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                import json
                try:
                    analysis = json.loads(result.stdout)
                    return {
                        'vertices': analysis.get('scenes', [{}])[0].get('vertices', 0),
                        'primitives': analysis.get('scenes', [{}])[0].get('primitives', 0),
                        'materials': len(analysis.get('materials', [])),
                        'textures': len(analysis.get('textures', [])),
                        'animations': len(analysis.get('animations', [])),
                        'complexity': 'unknown'
                    }
                except json.JSONDecodeError:
                    pass
            
            # Fallback: simple file size-based analysis
            file_size = os.path.getsize(input_path)
            return {
                'file_size': file_size,
                'complexity': 'high' if file_size > 10_000_000 else 'medium' if file_size > 1_000_000 else 'low'
            }
            
        except Exception as e:
            self.logger.warning(f"Model analysis failed: {str(e)}")
            return {'complexity': 'unknown'}
    
    def _select_compression_methods(self, analysis):
        """Select optimal compression methods based on model analysis"""
        methods = []
        complexity = analysis.get('complexity', 'unknown')
        vertex_count = analysis.get('vertices', 0)
        
        # Always test meshopt as baseline
        methods.append('meshopt')
        
        # For high-complexity or high-vertex models, Draco often performs better
        if (complexity in ['high', 'unknown'] or 
            vertex_count > 50000 or 
            self.quality_level == 'maximum_compression'):
            methods.append('draco')
        
        # Test hybrid approach for complex models or when maximum compression is needed
        if (complexity == 'high' or 
            vertex_count > 100000 or 
            analysis.get('file_size', 0) > 5_000_000 or
            self.quality_level in ['balanced', 'maximum_compression']):
            methods.append('hybrid')
        
        self.logger.info(f"Selected compression methods based on analysis: {methods}")
        return methods
    
    def _run_gltf_transform_textures(self, input_path, output_path):
        """Step 4: Compress textures with KTX2/BasisU (high quality settings)"""
        try:
            # Use high-quality settings as recommended in the workflow
            # --q 255 for maximum quality, --uastc for normals, mixed approach for best results
            cmd = [
                'npx', 'gltf-transform', 'copy',
                input_path, output_path,
                '--ktx2', '--uastc',
                '--filter', 'r13z',  # channel packing for roughness/metallic
                '--q', '255'  # maximum quality as recommended for hero assets
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode != 0:
                self.logger.warning(f"High-quality texture compression failed, trying fallback: {result.stderr}")
                # Fallback to basic KTX2 compression
                cmd_fallback = [
                    'npx', 'gltf-transform', 'copy',
                    input_path, output_path,
                    '--ktx2'
                ]
                result = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=600)
                
                if result.returncode != 0:
                    self.logger.warning(f"Fallback texture compression failed, skipping: {result.stderr}")
                    shutil.copy2(input_path, output_path)
                    return {'success': True}
            
            return {'success': True}
        
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Texture compression timed out'}
        except Exception as e:
            self.logger.warning(f"Texture compression failed, skipping: {str(e)}")
            shutil.copy2(input_path, output_path)
            return {'success': True}
    
    def _run_gltf_transform_animations(self, input_path, output_path):
        """Step 5: Optimize animations"""
        try:
            # First try to resample animations
            temp_resampled = input_path + '.resampled.glb'
            cmd = ['npx', 'gltf-transform', 'resample', '--fps', '30', input_path, temp_resampled]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                self.logger.warning(f"Animation resampling failed, skipping: {result.stderr}")
                shutil.copy2(input_path, output_path)
                return {'success': True}
            
            # Then compress animations
            cmd = ['npx', 'gltf-transform', 'compress-animation', '--quantize', '16', temp_resampled, output_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            # Clean up temp file
            try:
                os.remove(temp_resampled)
            except:
                pass
            
            if result.returncode != 0:
                self.logger.warning(f"Animation compression failed, using resampled version: {result.stderr}")
                shutil.copy2(temp_resampled, output_path)
                return {'success': True}
            
            return {'success': True}
        
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Animation optimization timed out'}
        except Exception as e:
            self.logger.warning(f"Animation optimization failed, skipping: {str(e)}")
            shutil.copy2(input_path, output_path)
            return {'success': True}
    
    def _run_gltfpack_final(self, input_path, output_path):
        """Step 6: Final bundle and minify with LOD generation"""
        try:
            # Try with LOD generation first (progressive delivery as mentioned in workflow)
            cmd = [
                'gltfpack',
                '-i', input_path,
                '-o', output_path,
                '--meshopt',
                '--quantize',
                '--texture-compress',
                '--ktx2',  # ensure KTX2 textures are preserved
                '--no-copy',  # embed textures
                '--lod', '3',  # 3 levels of detail
                '--lod-scale', '0.5'  # each LOD is 50% of previous
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)  # longer timeout for LOD
            
            if result.returncode != 0:
                self.logger.warning(f"Final optimization with LOD failed, trying without: {result.stderr}")
                # Fallback without LOD generation
                cmd_fallback = [
                    'gltfpack',
                    '-i', input_path,
                    '-o', output_path,
                    '--meshopt',
                    '--quantize',
                    '--texture-compress',
                    '--ktx2',
                    '--no-copy'
                ]
                result = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=600)
                
                if result.returncode != 0:
                    self.logger.error(f"Basic final optimization failed: {result.stderr}")
                    return {
                        'success': False,
                        'error': f'Final optimization failed: {result.stderr}'
                    }
            
            return {'success': True}
        
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Final optimization timed out'}
        except Exception as e:
            return {'success': False, 'error': f'Final optimization failed: {str(e)}'}
