import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, Blueprint, render_template, request, jsonify, send_file, flash, redirect, url_for, session, current_app
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
import uuid
import time
from datetime import datetime, timezone
from config import get_config
from celery_app import make_celery
# Import the task function to ensure it's registered
import tasks
from database import SessionLocal, init_database
from models import OptimizationTask, PerformanceMetric, UserSession, SystemMetric
from analytics import get_analytics_dashboard_data

# Load environment variables
load_dotenv()

# Get configuration
config = get_config()

# Create Blueprint for main routes
main_routes = Blueprint('main_routes', __name__)

# Configure logging - Use console only in development to avoid file path issues
log_level = getattr(logging, config.LOG_LEVEL, logging.INFO)
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Import the proper Celery instance with Redis support
try:
    from celery_redis_proper import celery, broker_type
    logger.info(f"Celery loaded with {broker_type} broker")
except Exception as e:
    # Fallback mode - disable Celery entirely
    celery = None
    broker_type = 'none'
    logger.warning(f"Celery unavailable: {e}. Running in fallback mode.")

# Import tasks to ensure they're registered with Celery
try:
    import tasks
    import pipeline_tasks
    logger.info("Celery tasks imported successfully")
except ImportError as e:
    logger.warning(f"Failed to import tasks: {e}")
    logger.info("Application will continue without background processing")

# Note: Flask app creation is now handled by the factory pattern in main.py
# This file now contains only the route functions and utilities

def get_db():
    """Get database session"""
    return SessionLocal()

def process_file_synchronously(file_path, output_path, task_id, quality_level, enable_lod, enable_simplification):
    """Synchronous file processing when Celery is unavailable"""
    try:
        from optimizer import GLBOptimizer
        import time
        
        # Update task to processing
        db = get_db()
        
        # Create task record
        optimization_task = OptimizationTask(
            id=task_id,
            original_filename=Path(file_path).name,
            secure_filename=f"{task_id}.glb",
            original_size=Path(file_path).stat().st_size,
            quality_level=quality_level,
            enable_lod=enable_lod,
            enable_simplification=enable_simplification,
            status='processing',
            progress=10,
            current_step='Starting optimization',
            started_at=datetime.now(timezone.utc)
        )
        db.add(optimization_task)
        db.commit()
        
        # Run optimization
        optimizer = GLBOptimizer(quality_level=quality_level)
        start_time = time.time()
        
        # Get original file size
        original_size = Path(file_path).stat().st_size
        
        result = optimizer.optimize(
            input_path=file_path,
            output_path=output_path,
            progress_callback=lambda p, s, m=None: None  # Skip progress updates for sync mode
        )
        
        processing_time = time.time() - start_time
        compressed_size = Path(output_path).stat().st_size if Path(output_path).exists() else 0
        compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
        
        # Update task to completed
        optimization_task.status = 'completed'
        optimization_task.progress = 100
        optimization_task.current_step = 'Optimization complete!'
        optimization_task.completed_at = datetime.now(timezone.utc)
        optimization_task.original_size = original_size
        optimization_task.compressed_size = compressed_size
        optimization_task.compression_ratio = compression_ratio
        optimization_task.processing_time = processing_time
        db.commit()
        
        logger.info(f"Synchronous optimization completed: {original_size} -> {compressed_size} bytes ({compression_ratio:.1f}% reduction)")
        return True
        
    except Exception as e:
        logger.error(f"Synchronous optimization failed: {e}")
        try:
            optimization_task.status = 'failed'
            optimization_task.error_message = str(e)
            db.commit()
        except:
            pass
        return False

def get_or_create_user_session():
    """Get or create user session for tracking"""
    try:
        session_id = session.get('session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
            session['session_id'] = session_id
        
        db = get_db()
        try:
            user_session = db.query(UserSession).filter(UserSession.session_id == session_id).first()
            if not user_session:
                user_session = UserSession(
                    session_id=session_id,
                    user_agent=request.headers.get('User-Agent', '')[:500]
                )
                db.add(user_session)
                db.commit()
                logger.info(f"Created new user session: {session_id}")
            return user_session
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to get/create user session: {e}")
        return None

# Security headers middleware - now applied by factory pattern
def add_security_headers(response):
    """Add security headers to all responses"""
    if os.environ.get('SECURITY_HEADERS_ENABLED', 'true').lower() in ['true', '1', 'yes']:
        # Prevent clickjacking
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        
        # Prevent MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # Enable XSS protection
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Control referrer information
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # CORS headers for same-origin requests
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        
        # Content Security Policy (allowing required external resources)
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' cdnjs.cloudflare.com cdn.jsdelivr.net unpkg.com; "
            "style-src 'self' 'unsafe-inline' cdnjs.cloudflare.com cdn.jsdelivr.net cdn.replit.com fonts.googleapis.com; "
            "font-src 'self' cdnjs.cloudflare.com fonts.gstatic.com; "
            "img-src 'self' data:; "
            "object-src 'none'; "
            "base-uri 'self'"
        )
        
        # HTTPS enforcement (if enabled)
        if os.environ.get('HTTPS_ENABLED', 'false').lower() in ['true', '1', 'yes']:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    return response

# Ensure directories exist
config.ensure_directories()

# Validate configuration
config_issues = config.validate_config()
if config_issues:
    for issue in config_issues:
        logger.error(f"Configuration issue: {issue}")

# Log configuration summary
logger.info(f"GLB Optimizer starting with config: {config.get_config_summary()}")


def process_file_synchronously(input_path, output_path, task_id, quality_level, enable_lod, enable_simplification):
    """Synchronous file processing when Celery is unavailable"""
    try:
        start_time = time.time()
        
        # Create optimization task in database
        with get_db() as db:
            optimization_task = OptimizationTask(
                id=task_id,
                original_filename=os.path.basename(input_path),
                secure_filename=os.path.basename(input_path),
                quality_level=quality_level,
                enable_lod=enable_lod,
                enable_simplification=enable_simplification,
                status='processing',
                started_at=datetime.now(timezone.utc)
            )
            db.add(optimization_task)
            db.commit()
        
        # Initialize optimizer with context manager for guaranteed cleanup
        from optimizer import GLBOptimizer
        
        # Set up progress callback to update database
        def progress_callback(step, progress, message):
            try:
                with get_db() as db:
                    task = db.query(OptimizationTask).filter_by(id=task_id).first()
                    if task:
                        task.progress = progress
                        task.current_step = message
                        db.commit()
            except Exception as e:
                logger.warning(f"Failed to update progress: {e}")
        
        # Run optimization with context manager
        with GLBOptimizer(quality_level=quality_level) as optimizer:
            result = optimizer.optimize(
                input_path, 
                output_path,
                progress_callback=progress_callback
            )
        success = result.get('success', False)
        
        processing_time = time.time() - start_time
        original_size = Path(input_path).stat().st_size if Path(input_path).exists() else 0
        optimized_size = Path(output_path).stat().st_size if Path(output_path).exists() else 0
        compression_ratio = ((original_size - optimized_size) / original_size * 100) if original_size > 0 else 0.0
        
        # Update task with final results
        with get_db() as db:
            task = db.query(OptimizationTask).filter_by(id=task_id).first()
            if task:
                task.status = 'completed' if success else 'failed'
                task.progress = 100
                task.original_size = original_size
                task.compressed_size = optimized_size
                task.compression_ratio = compression_ratio
                task.processing_time = processing_time
                task.completed_at = datetime.now(timezone.utc)
                if not success:
                    task.error_message = result.get('error', 'Unknown error') if isinstance(result, dict) else 'Optimization failed'
                db.commit()
                logger.info(f"Updated task {task_id}: {original_size} -> {optimized_size} bytes ({compression_ratio:.1f}% reduction)")
        
        return success
        
    except Exception as e:
        logger.error(f"Synchronous processing failed: {e}")
        # Update task with error
        try:
            with get_db() as db:
                task = db.query(OptimizationTask).filter_by(id=task_id).first()
                if task:
                    task.status = 'failed'
                    task.error_message = str(e)
                    task.completed_at = datetime.now(timezone.utc)
                    db.commit()
        except:
            pass
        return False


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS


@main_routes.route('/')
def index():
    return render_template('index.html')


@main_routes.route('/upload', methods=['POST'])
def upload_file():
    logger.info("Upload endpoint called")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Request files: {list(request.files.keys())}")
    logger.info(f"Request form: {dict(request.form)}")
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file selected'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Only GLB files are allowed.'}), 400
        
        # Check file size before reading content
        if hasattr(file, 'content_length') and file.content_length > config.MAX_CONTENT_LENGTH:
            return jsonify({'error': f'File too large. Maximum size is {config.MAX_CONTENT_LENGTH // (1024*1024)}MB.'}), 400
        
        # Additional security: Basic file content validation for GLB files
        # Reset file pointer to beginning for content check
        file.seek(0)
        file_header = file.read(12)  # Read first 12 bytes for GLB magic header
        file.seek(0)  # Reset for actual save
        
        # GLB files must start with "glTF" magic number (0x46546C67) followed by version
        if len(file_header) < 4 or file_header[:4] != b'glTF':
            return jsonify({'error': 'Invalid GLB file format. File does not contain valid GLB header.'}), 400
        
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        
        # Get optimization settings from form
        quality_level = request.form.get('quality_level', 'high')
        enable_lod = request.form.get('enable_lod') == 'true'
        enable_simplification = request.form.get('enable_simplification') == 'true'
        
        # Secure: Store original filename only for display/download purposes
        original_filename = secure_filename(file.filename or "uploaded.glb")
        original_name = original_filename.rsplit('.', 1)[0] if '.' in original_filename else "model"
        
        # Secure: Generate completely safe, server-controlled filenames using task_id only
        # No user input is used in the actual file paths passed to shell commands
        input_path = str(Path(config.UPLOAD_FOLDER) / f"{task_id}.glb")
        output_path = str(Path(config.OUTPUT_FOLDER) / f"{task_id}_optimized.glb")
        
        file.save(input_path)
        
        # Get original file size
        original_size = Path(input_path).stat().st_size
        
        # Store original file info for comparison viewer
        original_file_info = {
            'path': input_path,
            'size': original_size,
            'name': original_name
        }
        
        # Always use synchronous processing for immediate results
        logger.info("Using synchronous processing for immediate optimization")
        success = process_file_synchronously(input_path, output_path, task_id, quality_level, enable_lod, enable_simplification)
        
        if success:
            optimized_size = Path(output_path).stat().st_size if Path(output_path).exists() else 0
            compression_ratio = ((original_size - optimized_size) / original_size * 100) if original_size > 0 else 0
            
            return jsonify({
                'task_id': task_id, 
                'status': 'completed', 
                'fallback_mode': True,
                'original_size': original_size,
                'optimized_size': optimized_size,
                'compression_ratio': compression_ratio,
                'message': 'Optimization completed successfully'
            })
        else:
            return jsonify({'error': 'Optimization failed'}), 500
        
        # Create database record for tracking
        try:
            db = get_db()
            try:
                final_task_id = getattr(celery_task, 'id', task_id)
                optimization_task = OptimizationTask(
                    id=final_task_id,
                    original_filename=original_filename,
                    secure_filename=f"{final_task_id}.glb",
                    original_size=original_size,
                    quality_level=quality_level,
                    enable_lod=enable_lod,
                    enable_simplification=enable_simplification,
                    status='pending'
                )
                db.add(optimization_task)
                db.commit()
                logger.info(f"Created database record for task {final_task_id}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to create database record: {e}")
            # Continue without database tracking
        
        task_id = getattr(celery_task, 'id', f'sync_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        logger.info(f"Preparing response for task {task_id}")
        response_data = {
            'task_id': task_id,
            'message': 'File uploaded successfully. Optimization queued.',
            'original_size': original_size
        }
        logger.info(f"Sending response: {response_data}")
        return jsonify(response_data)
    
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({
            'error': 'An error occurred during file upload. Please try again.',
            'details': str(e) if config.DEBUG else None
        }), 500




@main_routes.route('/progress/<task_id>')
def get_progress(task_id):
    try:
        # Get task result from Celery
        celery_task = celery.AsyncResult(task_id)
        
        if celery_task.state == 'PENDING':
            response = {
                'status': 'pending',
                'progress': 0,
                'step': 'Task is queued...',
                'completed': False
            }
        elif celery_task.state == 'PROGRESS':
            response = celery_task.info
            response['completed'] = False
        elif celery_task.state == 'SUCCESS':
            result = celery_task.result
            response = result
            response['completed'] = True
        elif celery_task.state == 'FAILURE':
            error_info = celery_task.info
            if isinstance(error_info, dict):
                # Enhanced error response with details
                response = {
                    'status': 'error',
                    'completed': True,
                    **error_info  # Include all error details
                }
            else:
                # Simple error string
                response = {
                    'status': 'error',
                    'error': str(error_info),
                    'completed': True
                }
        else:
            response = {
                'status': celery_task.state.lower(),
                'completed': False
            }
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({'error': f'Failed to get task status: {str(e)}'}), 500


@main_routes.route('/download/<task_id>')
def download_file(task_id):
    try:
        # Check if task exists in database
        db = get_db()
        optimization_task = db.query(OptimizationTask).filter_by(id=task_id).first()
        
        if not optimization_task:
            return jsonify({'error': 'Task not found'}), 404
        
        if optimization_task.status != 'completed':
            return jsonify({'error': 'Task not completed successfully'}), 400
        
        # Look for the output file
        expected_output_file = f"{task_id}_optimized.glb"
        file_path = str(Path(config.OUTPUT_FOLDER) / expected_output_file)
        
        if not Path(file_path).exists():
            return jsonify({'error': 'Output file not found'}), 404
        
        # Use original filename for download
        original_name = optimization_task.original_filename.replace('.glb', '') if optimization_task.original_filename else 'optimized'
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=f"optimized_{original_name}.glb",
            mimetype='model/gltf-binary'
        )
    
    except Exception as e:
        return jsonify({'error': f'Download failed: {str(e)}'}), 500


@main_routes.route('/cleanup/<task_id>', methods=['POST'])
def cleanup_task(task_id):
    """Clean up task files and result data"""
    try:
        # Get task result from Celery
        celery_task = celery.AsyncResult(task_id)
        
        # Clean up both files using direct path construction (no directory scanning needed)
        # This is more efficient than the previous approach of scanning directories
        original_filename = f"{task_id}.glb"
        original_path = str(Path(config.UPLOAD_FOLDER) / original_filename)
        
        if Path(original_path).exists():
            try:
                Path(original_path).unlink()
                logging.info(f"Cleaned up original file: {original_path}")
            except Exception as e:
                logging.warning(f"Failed to remove original file {original_path}: {str(e)}")
        
        # DO NOT remove the optimized file - users need to download it!
        # Optimized files will be cleaned up later by scheduled cleanup task
        optimized_filename = f"{task_id}_optimized.glb"
        optimized_path = str(Path(config.OUTPUT_FOLDER) / optimized_filename)
        
        # Just log that the file exists for download
        if Path(optimized_path).exists():
            logging.info(f"Optimized file ready for download: {optimized_path}")
        else:
            logging.warning(f"Optimized file not found: {optimized_path}")
        
        # Revoke/forget the task in Celery
        celery_task.forget()
        
        return jsonify({'message': 'Task cleaned up successfully'})
    
    except Exception as e:
        logging.error(f"Cleanup failed for task {task_id}: {str(e)}")
        return jsonify({'error': f'Cleanup failed: {str(e)}'}), 500


@main_routes.route('/original/<task_id>')
def get_original_file(task_id):
    """Serve the original GLB file for 3D comparison viewer"""
    try:
        # Look for the original file in uploads directory using task_id
        original_file_path = str(Path(config.UPLOAD_FOLDER) / f"{task_id}.glb")
        
        if not Path(original_file_path).exists():
            return jsonify({'error': 'Original file not found'}), 404
        
        response = send_file(
            original_file_path,
            mimetype='model/gltf-binary',
            as_attachment=False
        )
        # Add CORS headers for 3D viewer access
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    except Exception as e:
        return jsonify({'error': f'Failed to serve original file: {str(e)}'}), 500


@main_routes.route('/error-logs/<task_id>')
def download_error_logs(task_id):
    """Download detailed error logs for optimization tasks"""
    try:
        import time
        from io import BytesIO
        
        # Get task result from Celery
        celery_task = celery.AsyncResult(task_id)
        
        if celery_task.state == 'FAILURE':
            error_info = celery_task.info
            log_content = f"""GLB Optimization Error Report
Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}
Task ID: {task_id}
Status: FAILED

Error Details:
{error_info.get('detailed_error', 'No detailed error information available') if isinstance(error_info, dict) else str(error_info)}

User Message:
{error_info.get('error', 'No user message available') if isinstance(error_info, dict) else 'See error details above'}
"""
        elif celery_task.state == 'SUCCESS':
            log_content = f"""GLB Optimization Log
Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}
Task ID: {task_id}
Status: SUCCESS

No errors occurred during optimization.
"""
        else:
            log_content = f"""GLB Optimization Log
Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}
Task ID: {task_id}
Status: {celery_task.state}

Task is still in progress or in an unknown state.
"""
        
        # Convert to BytesIO for proper file serving
        log_bytes = BytesIO(log_content.encode('utf-8'))
        log_bytes.seek(0)
        
        return send_file(
            log_bytes,
            as_attachment=True,
            download_name=f"glb_optimization_log_{task_id}.txt",
            mimetype='text/plain'
        )
    
    except Exception as e:
        logging.error(f"Log download failed for task {task_id}: {str(e)}")
        return jsonify({'error': f'Log download failed: {str(e)}'}), 500



@main_routes.route('/admin/analytics')
def admin_analytics():
    """Admin analytics dashboard showing database insights"""
    try:
        analytics_data = get_analytics_dashboard_data()
        return jsonify(analytics_data)
    except Exception as e:
        logger.error(f"Analytics error: {str(e)}")
        return jsonify({'error': 'Failed to generate analytics'}), 500



@main_routes.route('/admin/stats')
def admin_stats():
    """Quick database statistics endpoint"""
    try:
        db = get_db()
        try:
            stats = {
                'total_tasks': db.query(OptimizationTask).count(),
                'completed_tasks': db.query(OptimizationTask).filter(OptimizationTask.status == 'completed').count(),
                'total_users': db.query(UserSession).count(),
                'total_performance_records': db.query(PerformanceMetric).count(),
                'database_status': 'connected'
            }
            return jsonify(stats)
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Stats error: {str(e)}")
        return jsonify({'error': 'Failed to get database stats', 'database_status': 'error'}), 500

@main_routes.route('/health')
def health_check():
    """Health check endpoint for monitoring."""
    services = {}
    
    # Check Celery worker status with database broker
    try:
        import subprocess
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        if 'celery' in result.stdout and 'worker' in result.stdout:
            services['celery_worker'] = "Worker process running (Database broker)"
        else:
            services['celery_worker'] = "Worker process not found"
    except Exception as e:
        services['celery_worker'] = f"Process check failed: {str(e)}"
    
    # Check database connectivity
    try:
        from database import get_db
        db = get_db()
        db.execute('SELECT 1')
        services['database'] = "Connected"
    except Exception as e:
        services['database'] = f"ERROR: {str(e)}"
    
    return jsonify({
        'status': 'ok',
        'services': services
    })

def create_app():
    """
    Creates and configures the Flask application object.
    This is the factory that Gunicorn will use via wsgi.py.
    """
    # Create Flask app
    app = Flask(__name__)
    
    # Load configuration
    app.secret_key = config.SECRET_KEY
    app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH
    
    # Apply middleware
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # Register the Blueprint with all routes
    app.register_blueprint(main_routes)
    
    # Register middleware
    app.after_request(add_security_headers)
        
    logger.info("Flask application created with factory pattern")
    return app

# Create the app instance for imports
app = create_app()

if __name__ == '__main__':
    # Run the app
    app.run(host='0.0.0.0', port=5000, debug=config.DEBUG)
