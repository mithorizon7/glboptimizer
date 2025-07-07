import os
import subprocess
import tempfile
import time
import logging
import shutil

class GLBOptimizer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def optimize(self, input_path, output_path, progress_callback=None):
        """
        Optimize a GLB file using the industry-standard 6-step workflow
        """
        start_time = time.time()
        
        try:
            # Create temporary directory for intermediate files
            with tempfile.TemporaryDirectory() as temp_dir:
                
                # Step 1: Strip the fat first (cleanup & deduplication)
                if progress_callback:
                    progress_callback("Step 1: Cleanup & Deduplication", 10, "Pruning unused data...")
                
                step1_output = os.path.join(temp_dir, "step1_pruned.glb")
                result = self._run_gltf_transform_prune(input_path, step1_output)
                if not result['success']:
                    return result
                
                # Step 2: Weld and join meshes
                if progress_callback:
                    progress_callback("Step 1: Cleanup & Deduplication", 20, "Welding and joining meshes...")
                
                step2_output = os.path.join(temp_dir, "step2_welded.glb")
                result = self._run_gltf_transform_weld(step1_output, step2_output)
                if not result['success']:
                    return result
                
                # Step 3: Compress geometry with meshopt
                if progress_callback:
                    progress_callback("Step 2: Geometry Compression", 40, "Compressing geometry with meshopt...")
                
                step3_output = os.path.join(temp_dir, "step3_compressed.glb")
                result = self._run_gltfpack_geometry(step2_output, step3_output)
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
                
                result = self._run_gltfpack_final(step5_output, output_path)
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
        try:
            cmd = ['npx', 'gltf-transform', 'prune', input_path, output_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                self.logger.error(f"gltf-transform prune failed: {result.stderr}")
                return {
                    'success': False,
                    'error': f'Pruning failed: {result.stderr}'
                }
            
            return {'success': True}
        
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Pruning operation timed out'}
        except Exception as e:
            return {'success': False, 'error': f'Pruning failed: {str(e)}'}
    
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
        """Step 3: Compress geometry with meshopt"""
        try:
            cmd = [
                'gltfpack',
                '-i', input_path,
                '-o', output_path,
                '--meshopt',
                '--quantize'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode != 0:
                self.logger.error(f"gltfpack geometry compression failed: {result.stderr}")
                return {
                    'success': False,
                    'error': f'Geometry compression failed: {result.stderr}'
                }
            
            return {'success': True}
        
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Geometry compression timed out'}
        except Exception as e:
            return {'success': False, 'error': f'Geometry compression failed: {str(e)}'}
    
    def _run_gltf_transform_textures(self, input_path, output_path):
        """Step 4: Compress textures with KTX2/BasisU"""
        try:
            cmd = [
                'npx', 'gltf-transform', 'copy',
                input_path, output_path,
                '--ktx2', '--uastc'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode != 0:
                self.logger.warning(f"Texture compression failed, skipping: {result.stderr}")
                # If texture compression fails, just copy the file
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
        """Step 6: Final bundle and minify"""
        try:
            cmd = [
                'gltfpack',
                '-i', input_path,
                '-o', output_path,
                '--meshopt',
                '--quantize',
                '--texture-compress',
                '--no-copy'  # embed textures
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode != 0:
                self.logger.error(f"Final gltfpack optimization failed: {result.stderr}")
                return {
                    'success': False,
                    'error': f'Final optimization failed: {result.stderr}'
                }
            
            return {'success': True}
        
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Final optimization timed out'}
        except Exception as e:
            return {'success': False, 'error': f'Final optimization failed: {str(e)}'}
