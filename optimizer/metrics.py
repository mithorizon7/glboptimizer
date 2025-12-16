"""
GLB Metrics Collection module.

Analyzes GLB files to extract detailed metrics for audit reports.
Uses gltf-transform inspect for structured analysis.
"""

import json
import logging
import subprocess
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def collect_glb_metrics(file_path: str, timeout: int = 30) -> Dict[str, Any]:
    """
    Collect detailed metrics from a GLB file.
    
    Args:
        file_path: Path to the GLB file
        timeout: Command timeout in seconds
        
    Returns:
        Dictionary with metrics including:
        - vertices: vertex count
        - faces: face/primitive count
        - textures: list of textures with sizes
        - materials: material count
        - animations: animation count
        - file_size_bytes: file size
    """
    try:
        # Get file size first
        import os
        file_size = os.path.getsize(file_path)
        
        # Use gltf-transform inspect to get detailed info
        cmd = ['npx', 'gltf-transform', 'inspect', file_path, '--format', 'json']
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode != 0:
            logger.warning(f"gltf-transform inspect failed: {result.stderr}")
            # Return basic metrics from file size only
            return _basic_metrics(file_path, file_size)
        
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            logger.warning("Failed to parse gltf-transform output")
            return _basic_metrics(file_path, file_size)
        
        # Extract metrics from inspection data
        scenes = data.get('scenes', [{}])
        scene = scenes[0] if scenes else {}
        
        # Count textures and their memory usage
        textures = data.get('textures', [])
        texture_memory = sum(t.get('memSize', 0) for t in textures if isinstance(t, dict))
        
        # Count materials
        materials = data.get('materials', [])
        
        # Count animations
        animations = data.get('animations', [])
        
        # Count meshes and primitives
        meshes = data.get('meshes', [])
        
        return {
            'vertices': scene.get('vertices', 0),
            'primitives': scene.get('primitives', 0),
            'faces': scene.get('primitives', 0),  # Alias for backward compatibility
            'meshes': len(meshes),
            'materials': len(materials),
            'textures': len(textures),
            'texture_memory_bytes': texture_memory,
            'texture_memory_mb': round(texture_memory / (1024 * 1024), 2),
            'animations': len(animations),
            'file_size_bytes': file_size,
            'file_size_mb': round(file_size / (1024 * 1024), 2),
            'collection_method': 'gltf-transform'
        }
        
    except subprocess.TimeoutExpired:
        logger.warning(f"Metrics collection timed out for {file_path}")
        return _basic_metrics(file_path)
    except Exception as e:
        logger.error(f"Failed to collect metrics: {e}")
        return _basic_metrics(file_path)


def _basic_metrics(file_path: str, file_size: int = None) -> Dict[str, Any]:
    """Return basic metrics when detailed inspection fails."""
    import os
    if file_size is None:
        try:
            file_size = os.path.getsize(file_path)
        except Exception:
            file_size = 0
    
    return {
        'vertices': None,
        'primitives': None,
        'faces': None,
        'meshes': None,
        'materials': None,
        'textures': None,
        'texture_memory_bytes': None,
        'texture_memory_mb': None,
        'animations': None,
        'file_size_bytes': file_size,
        'file_size_mb': round(file_size / (1024 * 1024), 2) if file_size else None,
        'collection_method': 'basic'
    }


def compare_metrics(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare before and after metrics to generate an audit report.
    
    Args:
        before: Metrics collected before optimization
        after: Metrics collected after optimization
        
    Returns:
        Dictionary with comparison data and reduction percentages
    """
    comparison = {}
    
    # Metrics to compare
    metrics_to_compare = [
        'vertices', 'primitives', 'meshes', 'materials', 
        'textures', 'texture_memory_bytes', 'animations', 'file_size_bytes'
    ]
    
    for metric in metrics_to_compare:
        before_val = before.get(metric)
        after_val = after.get(metric)
        
        if before_val is not None and after_val is not None and before_val > 0:
            reduction = ((before_val - after_val) / before_val) * 100
            comparison[metric] = {
                'before': before_val,
                'after': after_val,
                'reduction_percent': round(reduction, 1),
                'reduction_absolute': before_val - after_val
            }
        else:
            comparison[metric] = {
                'before': before_val,
                'after': after_val,
                'reduction_percent': None,
                'reduction_absolute': None
            }
    
    # Add human-readable summary
    comparison['summary'] = _generate_summary(comparison)
    
    return comparison


def _generate_summary(comparison: Dict[str, Any]) -> Dict[str, str]:
    """Generate human-readable summary strings."""
    summary = {}
    
    if 'file_size_bytes' in comparison:
        data = comparison['file_size_bytes']
        if data['reduction_percent'] is not None:
            before_mb = data['before'] / (1024 * 1024)
            after_mb = data['after'] / (1024 * 1024)
            summary['file_size'] = f"{before_mb:.1f}MB → {after_mb:.1f}MB ({data['reduction_percent']:.1f}% smaller)"
    
    if 'vertices' in comparison:
        data = comparison['vertices']
        if data['before'] and data['after']:
            summary['vertices'] = f"{data['before']:,} → {data['after']:,}"
            if data['reduction_percent']:
                summary['vertices'] += f" ({data['reduction_percent']:.1f}% reduction)"
    
    if 'texture_memory_bytes' in comparison:
        data = comparison['texture_memory_bytes']
        if data['before'] and data['after']:
            before_mb = data['before'] / (1024 * 1024)
            after_mb = data['after'] / (1024 * 1024)
            summary['textures'] = f"{before_mb:.1f}MB → {after_mb:.1f}MB"
            if data['reduction_percent']:
                summary['textures'] += f" ({data['reduction_percent']:.1f}% smaller)"
    
    return summary
