"""
GLB Optimizer Package

This package provides the GLBOptimizer class and related utilities
for optimizing GLB (3D model) files using an industry-standard
multi-step workflow.
"""

from optimizer.core import GLBOptimizer
from optimizer.handlers import (
    run_gltfpack_geometry_parallel,
    run_draco_compression_parallel,
    run_gltf_transform_optimize_parallel,
)
from optimizer.metrics import collect_glb_metrics, compare_metrics

__all__ = [
    'GLBOptimizer',
    'run_gltfpack_geometry_parallel',
    'run_draco_compression_parallel',
    'run_gltf_transform_optimize_parallel',
    'collect_glb_metrics',
    'compare_metrics',
]
