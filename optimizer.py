"""
GLB Optimizer - Legacy compatibility shim.

This module is deprecated. Please import from the `optimizer` package directly:

    from optimizer import GLBOptimizer
    from optimizer import run_gltfpack_geometry_parallel

This shim re-exports all public symbols from the optimizer package for
backward compatibility with existing code.
"""

# Re-export all public symbols from the new package location
from optimizer.core import GLBOptimizer
from optimizer.handlers import (
    run_gltfpack_geometry_parallel,
    run_draco_compression_parallel,
    run_gltf_transform_optimize_parallel,
)

# Maintain backward compatibility by exporting all names at module level
__all__ = [
    'GLBOptimizer',
    'run_gltfpack_geometry_parallel',
    'run_draco_compression_parallel',
    'run_gltf_transform_optimize_parallel',
]
