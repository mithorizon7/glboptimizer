"""
Parallel processing handlers for GLB optimization.

These standalone functions are designed to be used with multiprocessing
for parallel compression testing.
"""

from config import OptimizationThresholds
from path_utils import path_exists, path_size


def run_gltfpack_geometry_parallel(input_path, output_path):
    """Standalone function for parallel gltfpack geometry compression using hardened subprocess wrapper"""
    try:
        # Import here to avoid circular dependency
        from optimizer.core import GLBOptimizer
        
        # Use a temporary GLBOptimizer instance for secure subprocess execution
        with GLBOptimizer('high') as optimizer:
            cmd = [
                'gltfpack',
                '-i', input_path,
                '-o', output_path,
                '-cc',  # Aggressive compression
                '-cf'   # No fallback compression
            ]
            
            # Route through hardened subprocess wrapper with sanitized environment
            result = optimizer._run_subprocess(
                cmd,
                step_name='parallel_gltfpack_geometry',
                description='Parallel GLTFPack geometry compression',
                timeout=optimizer.config.SUBPROCESS_TIMEOUT
            )
            
            # Check output using pathlib.Path operations
            if result['success'] and path_exists(output_path) and path_size(output_path) > 0:
                return {'success': True}
            else:
                return {
                    'success': False, 
                    'error': result.get('error', 'gltfpack failed'),
                    'detailed_error': result.get('detailed_error', '')
                }
                
    except Exception as e:
        return {'success': False, 'error': str(e)}


def run_draco_compression_parallel(input_path, output_path):
    """Standalone function for parallel Draco compression using hardened subprocess wrapper"""
    try:
        # Import here to avoid circular dependency
        from optimizer.core import GLBOptimizer
        
        # Use a temporary GLBOptimizer instance for secure subprocess execution
        with GLBOptimizer('high') as optimizer:
            cmd = [
                'npx', 'gltf-transform', 'draco',
                input_path, output_path,
                '--method', 'edgebreaker',
                '--quantize-position', '14',
                '--quantize-normal', '10',
                '--quantize-color', '8',
                '--quantize-texcoord', '12'
            ]
            
            # Route through hardened subprocess wrapper with sanitized environment
            result = optimizer._run_subprocess(
                cmd,
                step_name='parallel_draco_compression',
                description='Parallel Draco geometry compression',
                timeout=optimizer.config.SUBPROCESS_TIMEOUT
            )
            
            # Check output using standard os operations
            if result['success'] and path_exists(output_path) and path_size(output_path) > 0:
                return {'success': True}
            else:
                return {
                    'success': False, 
                    'error': result.get('error', 'Draco compression failed'),
                    'detailed_error': result.get('detailed_error', '')
                }
                
    except Exception as e:
        return {'success': False, 'error': str(e)}


def run_gltf_transform_optimize_parallel(input_path, output_path):
    """Standalone function for parallel gltf-transform optimize using hardened subprocess wrapper"""
    try:
        # Import here to avoid circular dependency
        from optimizer.core import GLBOptimizer
        
        # Use a temporary GLBOptimizer instance for secure subprocess execution
        with GLBOptimizer('high') as optimizer:
            cmd = [
                'npx', 'gltf-transform', 'optimize',
                input_path, output_path,
                '--compress', 'meshopt',
                '--instance',
                '--simplify', str(OptimizationThresholds.SIMPLIFY_RATIOS['high']),
                '--weld', '0.0001'
            ]
            
            # Route through hardened subprocess wrapper with sanitized environment
            result = optimizer._run_subprocess(
                cmd,
                step_name='parallel_gltf_transform_optimize',
                description='Parallel gltf-transform optimization',
                timeout=optimizer.config.SUBPROCESS_TIMEOUT
            )
            
            # Check output using standard os operations
            if result['success'] and path_exists(output_path) and path_size(output_path) > 0:
                return {'success': True}
            else:
                return {
                    'success': False, 
                    'error': result.get('error', 'gltf-transform optimize failed'),
                    'detailed_error': result.get('detailed_error', '')
                }
                
    except Exception as e:
        return {'success': False, 'error': str(e)}
