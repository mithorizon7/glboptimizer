# pipeline_tasks_fixed.py
"""
Enhanced Pipeline Tasks with Robust Error Handling
Fixed version addressing critical initialization and method access issues
"""

import os
import logging
from celery_app import make_celery
from optimizer import GLBOptimizer
from database import SessionLocal
from models import OptimizationTask
from sqlalchemy import text
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
celery_app = make_celery('glb_pipeline')

class PipelineStage:
    """
    Self-contained pipeline stage that handles its own optimizer instance,
    progress updates, and error logging. Fixes the 'optimizer' attribute issues.
    """
    def __init__(self, task_id: str, stage_name: str):
        self.task_id = task_id
        self.stage_name = stage_name
        # Each stage gets its own optimizer instance - THIS FIXES THE ATTRIBUTE ERROR
        self.optimizer = GLBOptimizer()

    def update_progress(self, progress: int, message: str, status: str = 'processing'):
        """Update task progress in database with proper error handling"""
        try:
            db = SessionLocal()
            query = text("""
                UPDATE optimization_tasks 
                SET progress = :progress, current_step = :step, status = :status, updated_at = :updated_at
                WHERE id = :task_id
            """)
            db.execute(query, {
                'progress': progress,
                'step': f"{self.stage_name}: {message}",
                'status': status,
                'updated_at': datetime.now(timezone.utc),
                'task_id': self.task_id
            })
            db.commit()
            logger.info(f"Progress updated for {self.task_id}: {progress}% - {message}")
        except Exception as e:
            logger.error(f"Failed to update progress for task {self.task_id}: {e}")
        finally:
            db.close()

@celery_app.task(bind=True, name='pipeline.inspect_model')
def inspect_model_task(self, task_id: str, input_path: str, output_path: str):
    """Stage 1: Model inspection and analysis"""
    stage = PipelineStage(task_id, "Model Analysis")
    stage.update_progress(5, "Analyzing 3D model structure")

    try:
        # Use the properly initialized optimizer
        result = stage.optimizer._run_subprocess(
            ['gltf-transform', 'inspect', input_path],
            'inspect',
            'Analyzing model structure'
        )

        if result['success']:
            model_info = {
                'has_animations': 'animations' in result.get('stdout', '').lower(),
                'has_textures': 'textures' in result.get('stdout', '').lower(),
                'vertex_count': 'vertices' in result.get('stdout', '').lower()
            }
            stage.update_progress(10, "Analysis complete")
            
            # Chain to next task
            prune_model_task.delay(task_id, input_path, output_path, model_info)
            return {'success': True, 'model_info': model_info}
        else:
            raise Exception(result.get('error', 'Model inspection failed'))

    except Exception as e:
        logger.error(f"Inspection failed for task {task_id}: {e}")
        stage.update_progress(5, f"Analysis failed: {e}", status='failed')
        return {'success': False, 'error': str(e)}

@celery_app.task(bind=True, name='pipeline.prune_model')
def prune_model_task(self, task_id: str, input_path: str, output_path: str, model_info: dict):
    """Stage 2: Prune unused data"""
    stage = PipelineStage(task_id, "Data Cleanup")
    stage.update_progress(15, "Removing unused data")

    try:
        prune_output = input_path.replace('.glb', '_pruned.glb')

        # This now works because optimizer is properly initialized
        result = stage.optimizer._run_subprocess(
            ['gltf-transform', 'prune', input_path, prune_output],
            'prune',
            'Removing unused data'
        )

        if result['success']:
            stage.update_progress(25, "Cleanup complete")
            # Chain to next task
            weld_model_task.delay(task_id, prune_output, output_path, model_info)
            return {'success': True, 'output': prune_output}
        else:
            raise Exception(result.get('error', 'Pruning failed'))

    except Exception as e:
        logger.error(f"Pruning failed for task {task_id}: {e}")
        stage.update_progress(15, f"Cleanup failed: {e}", status='failed')
        return {'success': False, 'error': str(e)}

@celery_app.task(bind=True, name='pipeline.weld_model')
def weld_model_task(self, task_id: str, input_path: str, output_path: str, model_info: dict):
    """Stage 3: Weld vertices and join meshes"""
    stage = PipelineStage(task_id, "Mesh Processing")
    stage.update_progress(35, "Welding vertices")

    try:
        weld_output = input_path.replace('.glb', '_welded.glb')

        result = stage.optimizer._run_subprocess(
            ['gltf-transform', 'weld', '--tolerance', '0.0001', input_path, weld_output],
            'weld',
            'Welding vertices'
        )

        if result['success']:
            # Join compatible meshes
            join_result = stage.optimizer._run_subprocess(
                ['gltf-transform', 'join', weld_output, weld_output],
                'join',
                'Joining meshes'
            )
            
            if join_result['success']:
                stage.update_progress(45, "Mesh processing complete")
                # Chain to geometry compression
                compress_geometry_task.delay(task_id, weld_output, output_path, model_info)
                return {'success': True, 'output': weld_output}
            else:
                raise Exception(join_result.get('error', 'Mesh joining failed'))
        else:
            raise Exception(result.get('error', 'Vertex welding failed'))

    except Exception as e:
        logger.error(f"Welding failed for task {task_id}: {e}")
        stage.update_progress(35, f"Mesh processing failed: {e}", status='failed')
        return {'success': False, 'error': str(e)}

@celery_app.task(bind=True, name='pipeline.compress_geometry')
def compress_geometry_task(self, task_id: str, input_path: str, output_path: str, model_info: dict):
    """Stage 4: Apply geometry compression"""
    stage = PipelineStage(task_id, "Geometry Compression")
    stage.update_progress(55, "Compressing geometry")

    try:
        geom_output = input_path.replace('.glb', '_compressed.glb')

        # Try meshopt compression first
        result = stage.optimizer._run_subprocess(
            ['gltf-transform', 'meshopt', '--quantize', '14', input_path, geom_output],
            'meshopt',
            'Applying meshopt compression'
        )

        if not result['success']:
            # Fallback to gltfpack
            result = stage.optimizer._run_subprocess(
                ['gltfpack', '-i', input_path, '-o', geom_output, '-cc'],
                'gltfpack',
                'Applying geometry compression'
            )

        if result['success']:
            stage.update_progress(65, "Geometry compression complete")
            # Chain to texture compression if model has textures
            if model_info.get('has_textures', False):
                compress_textures_task.delay(task_id, geom_output, output_path, model_info)
            else:
                # Skip to animation optimization
                optimize_animations_task.delay(task_id, geom_output, output_path, model_info)
            return {'success': True, 'output': geom_output}
        else:
            raise Exception(result.get('error', 'Geometry compression failed'))

    except Exception as e:
        logger.error(f"Geometry compression failed for task {task_id}: {e}")
        stage.update_progress(55, f"Compression failed: {e}", status='failed')
        return {'success': False, 'error': str(e)}

@celery_app.task(bind=True, name='pipeline.compress_textures')
def compress_textures_task(self, task_id: str, input_path: str, output_path: str, model_info: dict):
    """Stage 5: Apply texture compression"""
    stage = PipelineStage(task_id, "Texture Compression")
    stage.update_progress(75, "Compressing textures")

    try:
        texture_output = input_path.replace('.glb', '_textured.glb')

        # Try KTX2 compression
        result = stage.optimizer._run_subprocess(
            ['gltf-transform', 'ktx', '--format', 'uastc', '--level', '4', input_path, texture_output],
            'ktx',
            'Applying KTX2 compression'
        )

        if not result['success']:
            # Fallback to WebP compression
            result = stage.optimizer._run_subprocess(
                ['gltf-transform', 'webp', '--quality', '90', input_path, texture_output],
                'webp',
                'Applying WebP compression'
            )

        if result['success']:
            stage.update_progress(85, "Texture compression complete")
            # Chain to animation optimization
            optimize_animations_task.delay(task_id, texture_output, output_path, model_info)
            return {'success': True, 'output': texture_output}
        else:
            # Continue without texture compression
            stage.update_progress(85, "Texture compression skipped")
            optimize_animations_task.delay(task_id, input_path, output_path, model_info)
            return {'success': True, 'output': input_path}

    except Exception as e:
        logger.error(f"Texture compression failed for task {task_id}: {e}")
        # Continue with next stage even if texture compression fails
        stage.update_progress(85, "Texture compression skipped due to error")
        optimize_animations_task.delay(task_id, input_path, output_path, model_info)
        return {'success': True, 'output': input_path, 'warning': str(e)}

@celery_app.task(bind=True, name='pipeline.optimize_animations')
def optimize_animations_task(self, task_id: str, input_path: str, output_path: str, model_info: dict):
    """Stage 6: Optimize animations (if present)"""
    stage = PipelineStage(task_id, "Animation Optimization")
    stage.update_progress(90, "Processing animations")

    try:
        if model_info.get('has_animations', False):
            # Resample animations
            result = stage.optimizer._run_subprocess(
                ['gltf-transform', 'resample', '--hz', '30', input_path, input_path],
                'resample',
                'Resampling animations'
            )
            
            if result['success']:
                stage.update_progress(95, "Animations optimized")
            else:
                stage.update_progress(95, "Animation optimization skipped")
        else:
            stage.update_progress(95, "No animations to process")

        # Chain to final assembly
        finalize_optimization_task.delay(task_id, input_path, output_path, model_info)
        return {'success': True, 'output': input_path}

    except Exception as e:
        logger.error(f"Animation optimization failed for task {task_id}: {e}")
        # Continue to finalization even if animation optimization fails
        stage.update_progress(95, "Animation optimization skipped")
        finalize_optimization_task.delay(task_id, input_path, output_path, model_info)
        return {'success': True, 'output': input_path, 'warning': str(e)}

@celery_app.task(bind=True, name='pipeline.finalize_optimization')
def finalize_optimization_task(self, task_id: str, input_path: str, output_path: str, model_info: dict):
    """Stage 7: Final assembly and cleanup"""
    stage = PipelineStage(task_id, "Finalization")
    stage.update_progress(98, "Finalizing optimization")

    try:
        # Copy final result to output path
        import shutil
        shutil.copy2(input_path, output_path)
        
        # Generate performance report
        performance_report = stage.optimizer._generate_performance_report(
            input_path, output_path, processing_time=0
        )

        # Update database with final results
        try:
            db = SessionLocal()
            query = text("""
                UPDATE optimization_tasks 
                SET status = 'completed', progress = 100, 
                    compressed_size = :size, compression_ratio = :ratio,
                    completed_at = :completed_at,
                    performance_metrics = :metrics
                WHERE id = :task_id
            """)
            
            db.execute(query, {
                'size': int(performance_report.get('compressed_size_mb', 0) * 1024 * 1024),
                'ratio': performance_report.get('compression_ratio', 0),
                'completed_at': datetime.now(timezone.utc),
                'metrics': str(performance_report),
                'task_id': task_id
            })
            db.commit()
            
        except Exception as db_error:
            logger.error(f"Database update failed: {db_error}")
        finally:
            db.close()

        stage.update_progress(100, "Optimization complete", status='completed')
        
        # Cleanup intermediate files
        cleanup_intermediate_files(input_path)
        
        return {
            'success': True, 
            'output': output_path,
            'performance': performance_report
        }

    except Exception as e:
        logger.error(f"Finalization failed for task {task_id}: {e}")
        stage.update_progress(98, f"Finalization failed: {e}", status='failed')
        return {'success': False, 'error': str(e)}

def cleanup_intermediate_files(base_path: str):
    """Clean up intermediate files from the pipeline"""
    try:
        import glob
        import os
        
        base_name = base_path.replace('.glb', '')
        intermediate_patterns = [
            f"{base_name}_pruned.glb",
            f"{base_name}_welded.glb", 
            f"{base_name}_compressed.glb",
            f"{base_name}_textured.glb"
        ]
        
        for pattern in intermediate_patterns:
            if os.path.exists(pattern):
                os.remove(pattern)
                logger.info(f"Cleaned up intermediate file: {pattern}")
                
    except Exception as e:
        logger.warning(f"Failed to clean up intermediate files: {e}")

# Entry point for the pipeline
@celery_app.task(bind=True, name='pipeline.start_optimization')
def start_optimization_pipeline(self, task_id: str, input_path: str, output_path: str):
    """Entry point for the modular optimization pipeline"""
    logger.info(f"Starting optimization pipeline for task {task_id}")
    
    try:
        # Validate input file exists
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Start with model inspection
        inspect_model_task.delay(task_id, input_path, output_path)
        return {'success': True, 'message': 'Pipeline started successfully'}
        
    except Exception as e:
        logger.error(f"Failed to start pipeline for task {task_id}: {e}")
        # Update task status to failed
        try:
            db = SessionLocal()
            query = text("""
                UPDATE optimization_tasks 
                SET status = 'failed', error_message = :error
                WHERE id = :task_id
            """)
            db.execute(query, {'error': str(e), 'task_id': task_id})
            db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update task status: {db_error}")
        finally:
            db.close()
            
        return {'success': False, 'error': str(e)}