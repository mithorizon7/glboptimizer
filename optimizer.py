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
                
                # Step 3: Compress geometry with meshopt (with Draco fallback)
                if progress_callback:
                    progress_callback("Step 2: Geometry Compression", 40, "Compressing geometry with meshopt...")
                
                step3_output = os.path.join(temp_dir, "step3_compressed.glb")
                result = self._run_gltfpack_geometry(step2_output, step3_output)
                if not result['success']:
                    # Try Draco compression as fallback (as mentioned in workflow)
                    if progress_callback:
                        progress_callback("Step 2: Geometry Compression", 45, "Trying Draco compression fallback...")
                    result = self._run_draco_compression(step2_output, step3_output)
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
        """Step 3: Compress geometry with meshopt and optional simplification"""
        # Try with light simplification first (recommended in workflow)
        cmd = [
            'gltfpack',
            '-i', input_path,
            '-o', output_path,
            '--meshopt',
            '--quantize',
            '--simplify', '0.7'  # 70% triangle count (light simplification)
        ]
        result = self._run_subprocess(cmd, "Geometry Compression", "Compressing geometry with meshopt and simplification")
        
        if not result['success']:
            self.logger.warning(f"Geometry compression with simplification failed, trying without: {result.get('error', 'Unknown error')}")
            # Fallback without simplification
            cmd_fallback = [
                'gltfpack',
                '-i', input_path,
                '-o', output_path,
                '--meshopt',
                '--quantize'
            ]
            fallback_result = self._run_subprocess(cmd_fallback, "Geometry Compression (Fallback)", "Compressing geometry without simplification")
            return fallback_result
        
        return result
    
    def _run_draco_compression(self, input_path, output_path):
        """Alternative geometry compression using Draco (fallback option)"""
        try:
            cmd = [
                'npx', 'gltf-transform', 'compress-geometry',
                '--method', 'edgebreaker',
                input_path, output_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode != 0:
                self.logger.error(f"Draco compression failed: {result.stderr}")
                return {
                    'success': False,
                    'error': f'Draco compression failed: {result.stderr}'
                }
            
            return {'success': True}
        
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Draco compression timed out'}
        except Exception as e:
            return {'success': False, 'error': f'Draco compression failed: {str(e)}'}
    
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
