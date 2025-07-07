"""
Modular GLB Optimization Pipeline
Granular Celery tasks for improved resilience and flexibility
"""

import os
import json
import subprocess
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from celery import Celery
from celery.utils.log import get_task_logger
from celery_app import make_celery

from database import SessionLocal
from models import OptimizationTask
from optimizer import GLBOptimizer

# Configure Celery using the factory pattern
celery_app = make_celery('glb_pipeline')

logger = get_task_logger(__name__)

class PipelineStage:
    """Base class for pipeline stages with common functionality"""
    
    def __init__(self, task_id: str, stage_name: str):
        self.task_id = task_id
        self.stage_name = stage_name
        self.optimizer = GLBOptimizer()
    
    def update_progress(self, progress: int, message: str):
        """Update task progress in database"""
        try:
            db = SessionLocal()
            try:
                from sqlalchemy import text
                query = text("""
                    UPDATE optimization_tasks 
                    SET progress = :progress, current_step = :step, status = :status
                    WHERE id = :task_id
                """)
                
                status = 'completed' if progress >= 100 else 'processing'
                db.execute(query, {
                    'progress': progress,
                    'step': f"{self.stage_name}: {message}",
                    'status': status,
                    'task_id': self.task_id
                })
                db.commit()
                
                logger.info(f"Task {self.task_id}: {self.stage_name} - {progress}% - {message}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to update progress: {e}")

@celery_app.task(bind=True, name='pipeline.inspect_model')
def inspect_model_task(self, task_id: str, input_path: str, output_path: str) -> Dict[str, Any]:
    """
    Stage 1: Inspect GLB model to determine optimization strategy
    """
    stage = PipelineStage(task_id, "Model Analysis")
    stage.update_progress(5, "Analyzing model structure")
    
    try:
        # Use gltf-transform inspect to analyze model
        cmd = ['gltf-transform', 'inspect', input_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        model_info = {
            'has_animations': 'animations' in result.stdout.lower(),
            'has_textures': 'textures' in result.stdout.lower() or 'materials' in result.stdout.lower(),
            'vertex_count': 0,
            'triangle_count': 0,
            'texture_count': 0,
            'animation_count': 0
        }
        
        # Parse detailed information from inspect output
        lines = result.stdout.split('\n')
        for line in lines:
            line = line.lower().strip()
            if 'vertices' in line and 'total' in line:
                try:
                    model_info['vertex_count'] = int(''.join(filter(str.isdigit, line)))
                except:
                    pass
            elif 'triangles' in line:
                try:
                    model_info['triangle_count'] = int(''.join(filter(str.isdigit, line)))
                except:
                    pass
            elif 'textures' in line and ':' in line:
                try:
                    model_info['texture_count'] = int(line.split(':')[1].strip().split()[0])
                except:
                    pass
            elif 'animations' in line and ':' in line:
                try:
                    model_info['animation_count'] = int(line.split(':')[1].strip().split()[0])
                except:
                    pass
        
        stage.update_progress(10, f"Analysis complete: {model_info['vertex_count']} vertices, {model_info['texture_count']} textures")
        
        # Chain to next task: pruning
        prune_model_task.delay(task_id, input_path, output_path, model_info)
        
        return {
            'success': True,
            'model_info': model_info,
            'next_stage': 'prune'
        }
        
    except Exception as e:
        logger.error(f"Model inspection failed: {e}")
        stage.update_progress(0, f"Analysis failed: {str(e)}")
        return {'success': False, 'error': str(e)}

@celery_app.task(bind=True, name='pipeline.prune_model')
def prune_model_task(self, task_id: str, input_path: str, output_path: str, model_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stage 2: Prune unused data and clean up model
    """
    stage = PipelineStage(task_id, "Data Cleanup")
    stage.update_progress(15, "Removing unused data")
    
    try:
        # Create intermediate file for this stage
        prune_output = input_path.replace('.glb', '_pruned.glb')
        
        # Run pruning operation
        result = stage.optimizer._run_gltf_transform_prune(input_path, prune_output)
        
        if result['success']:
            stage.update_progress(25, "Cleanup complete")
            
            # Chain to next task: welding
            weld_model_task.delay(task_id, prune_output, output_path, model_info)
            
            return {
                'success': True,
                'intermediate_file': prune_output,
                'next_stage': 'weld'
            }
        else:
            raise Exception(result.get('error', 'Pruning failed'))
            
    except Exception as e:
        logger.error(f"Pruning failed: {e}")
        stage.update_progress(15, f"Cleanup failed: {str(e)}")
        return {'success': False, 'error': str(e)}

@celery_app.task(bind=True, name='pipeline.weld_model')
def weld_model_task(self, task_id: str, input_path: str, output_path: str, model_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stage 3: Weld vertices and join meshes
    """
    stage = PipelineStage(task_id, "Mesh Processing")
    stage.update_progress(30, "Welding vertices and joining meshes")
    
    try:
        # Create intermediate file for this stage
        weld_output = input_path.replace('.glb', '_welded.glb').replace('_pruned', '_welded')
        
        # Run welding operation
        result = stage.optimizer._run_gltf_transform_weld(input_path, weld_output)
        
        if result['success']:
            stage.update_progress(40, "Mesh processing complete")
            
            # Chain to next task: geometry compression
            compress_geometry_task.delay(task_id, weld_output, output_path, model_info)
            
            return {
                'success': True,
                'intermediate_file': weld_output,
                'next_stage': 'geometry'
            }
        else:
            raise Exception(result.get('error', 'Welding failed'))
            
    except Exception as e:
        logger.error(f"Welding failed: {e}")
        stage.update_progress(30, f"Mesh processing failed: {str(e)}")
        return {'success': False, 'error': str(e)}

@celery_app.task(bind=True, name='pipeline.compress_geometry')
def compress_geometry_task(self, task_id: str, input_path: str, output_path: str, model_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stage 4: Advanced geometry compression
    """
    stage = PipelineStage(task_id, "Geometry Compression")
    stage.update_progress(45, "Applying advanced geometry compression")
    
    try:
        # Create intermediate file for this stage
        geometry_output = input_path.replace('.glb', '_geometry.glb').replace('_welded', '_geometry')
        
        # Run geometry compression
        result = stage.optimizer._run_advanced_geometry_compression(input_path, geometry_output)
        
        if result['success']:
            compression_info = f"Geometry compressed ({result.get('compression_ratio', 0):.1%} reduction)"
            stage.update_progress(60, compression_info)
            
            # Decide next stage based on model content
            if model_info.get('has_textures', False) and model_info.get('texture_count', 0) > 0:
                # Chain to texture compression
                compress_textures_task.delay(task_id, geometry_output, output_path, model_info)
                next_stage = 'textures'
            elif model_info.get('has_animations', False) and model_info.get('animation_count', 0) > 0:
                # Skip textures, go to animations
                optimize_animations_task.delay(task_id, geometry_output, output_path, model_info)
                next_stage = 'animations'
            else:
                # Skip to final packaging
                finalize_model_task.delay(task_id, geometry_output, output_path, model_info)
                next_stage = 'finalize'
            
            return {
                'success': True,
                'intermediate_file': geometry_output,
                'next_stage': next_stage,
                'compression_ratio': result.get('compression_ratio', 0)
            }
        else:
            raise Exception(result.get('error', 'Geometry compression failed'))
            
    except Exception as e:
        logger.error(f"Geometry compression failed: {e}")
        stage.update_progress(45, f"Geometry compression failed: {str(e)}")
        return {'success': False, 'error': str(e)}

@celery_app.task(bind=True, name='pipeline.compress_textures')
def compress_textures_task(self, task_id: str, input_path: str, output_path: str, model_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stage 5: Texture compression (conditional)
    """
    stage = PipelineStage(task_id, "Texture Compression")
    stage.update_progress(65, "Compressing textures")
    
    try:
        # Create intermediate file for this stage
        texture_output = input_path.replace('.glb', '_textures.glb').replace('_geometry', '_textures')
        
        # Run texture compression
        result = stage.optimizer._run_gltf_transform_textures(input_path, texture_output)
        
        if result['success']:
            compression_info = f"Textures compressed ({result.get('compression_ratio', 0):.1%} reduction)"
            stage.update_progress(75, compression_info)
            
            # Decide next stage
            if model_info.get('has_animations', False) and model_info.get('animation_count', 0) > 0:
                # Chain to animations
                optimize_animations_task.delay(task_id, texture_output, output_path, model_info)
                next_stage = 'animations'
            else:
                # Skip to final packaging
                finalize_model_task.delay(task_id, texture_output, output_path, model_info)
                next_stage = 'finalize'
            
            return {
                'success': True,
                'intermediate_file': texture_output,
                'next_stage': next_stage,
                'texture_compression_ratio': result.get('compression_ratio', 0)
            }
        else:
            # Continue with uncompressed textures
            logger.warning(f"Texture compression failed, continuing: {result.get('error', '')}")
            
            if model_info.get('has_animations', False):
                optimize_animations_task.delay(task_id, input_path, output_path, model_info)
                next_stage = 'animations'
            else:
                finalize_model_task.delay(task_id, input_path, output_path, model_info)
                next_stage = 'finalize'
            
            return {
                'success': True,
                'intermediate_file': input_path,
                'next_stage': next_stage,
                'texture_compression_skipped': True
            }
            
    except Exception as e:
        logger.error(f"Texture compression failed: {e}")
        stage.update_progress(65, f"Texture compression failed, continuing: {str(e)}")
        
        # Continue pipeline even if textures fail
        if model_info.get('has_animations', False):
            optimize_animations_task.delay(task_id, input_path, output_path, model_info)
        else:
            finalize_model_task.delay(task_id, input_path, output_path, model_info)
        
        return {'success': True, 'error': str(e), 'stage_skipped': True}

@celery_app.task(bind=True, name='pipeline.optimize_animations')
def optimize_animations_task(self, task_id: str, input_path: str, output_path: str, model_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stage 6: Animation optimization (conditional)
    """
    stage = PipelineStage(task_id, "Animation Optimization")
    stage.update_progress(80, "Optimizing animations")
    
    try:
        # Create intermediate file for this stage
        animation_output = input_path.replace('.glb', '_animations.glb').replace('_textures', '_animations')
        
        # Run animation optimization
        result = stage.optimizer._run_gltf_transform_animations(input_path, animation_output)
        
        if result['success']:
            stage.update_progress(90, "Animation optimization complete")
            
            # Chain to final packaging
            finalize_model_task.delay(task_id, animation_output, output_path, model_info)
            
            return {
                'success': True,
                'intermediate_file': animation_output,
                'next_stage': 'finalize'
            }
        else:
            # Continue without animation optimization
            logger.warning(f"Animation optimization failed, continuing: {result.get('error', '')}")
            finalize_model_task.delay(task_id, input_path, output_path, model_info)
            
            return {
                'success': True,
                'intermediate_file': input_path,
                'next_stage': 'finalize',
                'animation_optimization_skipped': True
            }
            
    except Exception as e:
        logger.error(f"Animation optimization failed: {e}")
        stage.update_progress(80, f"Animation optimization failed, continuing: {str(e)}")
        
        # Continue pipeline even if animations fail
        finalize_model_task.delay(task_id, input_path, output_path, model_info)
        
        return {'success': True, 'error': str(e), 'stage_skipped': True}

@celery_app.task(bind=True, name='pipeline.finalize_model')
def finalize_model_task(self, task_id: str, input_path: str, output_path: str, model_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stage 7: Final packaging and cleanup
    """
    stage = PipelineStage(task_id, "Final Packaging")
    stage.update_progress(95, "Finalizing optimized model")
    
    try:
        # Run final packaging with gltfpack
        result = stage.optimizer._run_gltfpack_final(input_path, output_path)
        
        if result['success']:
            # Calculate final statistics
            original_size = os.path.getsize(input_path) if os.path.exists(input_path) else 0
            final_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
            compression_ratio = ((original_size - final_size) / original_size) if original_size > 0 else 0
            
            # Update database with final results
            try:
                db = SessionLocal()
                try:
                    from sqlalchemy import text
                    query = text("""
                        UPDATE optimization_tasks 
                        SET status = :status, progress = :progress, current_step = :step,
                            compressed_size = :compressed_size, compression_ratio = :compression_ratio,
                            completed_at = :completed_at
                        WHERE id = :task_id
                    """)
                    
                    db.execute(query, {
                        'status': 'completed',
                        'progress': 100,
                        'step': 'Optimization complete',
                        'compressed_size': final_size,
                        'compression_ratio': compression_ratio,
                        'completed_at': datetime.now(timezone.utc),
                        'task_id': task_id
                    })
                    db.commit()
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Failed to update final database record: {e}")
            
            # Clean up intermediate files
            try:
                base_path = os.path.dirname(input_path)
                for file in os.listdir(base_path):
                    if task_id in file and ('_pruned' in file or '_welded' in file or '_geometry' in file or '_textures' in file or '_animations' in file):
                        os.remove(os.path.join(base_path, file))
            except Exception as e:
                logger.warning(f"Failed to clean up intermediate files: {e}")
            
            stage.update_progress(100, f"Complete! {compression_ratio:.1%} size reduction achieved")
            
            return {
                'success': True,
                'final_file': output_path,
                'original_size': original_size,
                'final_size': final_size,
                'compression_ratio': compression_ratio,
                'model_info': model_info
            }
        else:
            raise Exception(result.get('error', 'Final packaging failed'))
            
    except Exception as e:
        logger.error(f"Finalization failed: {e}")
        stage.update_progress(95, f"Finalization failed: {str(e)}")
        return {'success': False, 'error': str(e)}

def start_optimization_pipeline(task_id: str, input_path: str, output_path: str) -> str:
    """
    Start the modular optimization pipeline
    """
    logger.info(f"Starting modular optimization pipeline for task {task_id}")
    
    # Trigger the first stage: model inspection
    inspect_model_task.delay(task_id, input_path, output_path)
    
    return task_id