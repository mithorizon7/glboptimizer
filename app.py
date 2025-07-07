import os
import logging
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
import uuid
from config import get_config
from celery_app import celery
# Import the task function to ensure it's registered
import tasks

# Load environment variables
load_dotenv()

# Get configuration
config = get_config()

# Configure logging
log_level = getattr(logging, config.LOG_LEVEL, logging.INFO)
if config.LOG_TO_FILE:
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config.LOG_FILE_PATH),
            logging.StreamHandler()
        ]
    )
else:
    logging.basicConfig(level=log_level)

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Apply configuration
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH

# Security headers middleware
@app.after_request
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
        
        # Content Security Policy (restrictive for uploads)
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' cdnjs.cloudflare.com cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' cdnjs.cloudflare.com cdn.jsdelivr.net; "
            "font-src 'self' cdnjs.cloudflare.com; "
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

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
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
        input_path = os.path.join(config.UPLOAD_FOLDER, f"{task_id}.glb")
        output_path = os.path.join(config.OUTPUT_FOLDER, f"{task_id}_optimized.glb")
        
        file.save(input_path)
        
        # Get original file size
        original_size = os.path.getsize(input_path)
        
        # Store original file info for comparison viewer
        original_file_info = {
            'path': input_path,
            'size': original_size,
            'name': original_name
        }
        
        # Start Celery task for optimization
        celery_task = tasks.optimize_glb_file.delay(
            input_path,
            output_path,
            original_name,
            quality_level,
            enable_lod,
            enable_simplification
        )
        
        return jsonify({
            'task_id': celery_task.id,
            'message': 'File uploaded successfully. Optimization queued.',
            'original_size': original_size
        })
    
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({
            'error': 'An error occurred during file upload. Please try again.',
            'details': str(e) if config.DEBUG else None
        }), 500



@app.route('/progress/<task_id>')
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

@app.route('/download/<task_id>')
def download_file(task_id):
    try:
        # Get task result from Celery
        celery_task = celery.AsyncResult(task_id)
        
        if celery_task.state != 'SUCCESS':
            return jsonify({'error': 'Task not completed successfully'}), 400
        
        result = celery_task.result
        if not result.get('success'):
            return jsonify({'error': 'Optimization failed'}), 400
        
        output_file = result.get('output_file')
        original_name = result.get('original_name', 'optimized')
        
        if not output_file:
            return jsonify({'error': 'Output file not available'}), 404
        
        file_path = os.path.join(app.config['OUTPUT_FOLDER'], output_file)
        if not os.path.exists(file_path):
            return jsonify({'error': 'Output file not found'}), 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=f"optimized_{original_name}.glb",
            mimetype='model/gltf-binary'
        )
    
    except Exception as e:
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

@app.route('/cleanup/<task_id>', methods=['POST'])
def cleanup_task(task_id):
    """Clean up task files and result data"""
    try:
        # Get task result from Celery
        celery_task = celery.AsyncResult(task_id)
        
        if celery_task.state == 'SUCCESS':
            result = celery_task.result
            output_file = result.get('output_file')
            
            # Remove output file
            if output_file:
                output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_file)
                try:
                    os.remove(output_path)
                    logging.info(f"Cleaned up output file: {output_path}")
                except Exception as e:
                    logging.warning(f"Failed to remove output file {output_path}: {str(e)}")
        
        # Remove original file (kept for 3D viewer comparison)
        upload_dir = app.config['UPLOAD_FOLDER']
        for filename in os.listdir(upload_dir):
            if filename.startswith(f"{task_id}_"):
                original_path = os.path.join(upload_dir, filename)
                try:
                    os.remove(original_path)
                    logging.info(f"Cleaned up original file: {original_path}")
                except Exception as e:
                    logging.warning(f"Failed to remove original file {original_path}: {str(e)}")
                break
        
        # Revoke/forget the task in Celery
        celery_task.forget()
        
        return jsonify({'message': 'Task cleaned up successfully'})
    
    except Exception as e:
        logging.error(f"Cleanup failed for task {task_id}: {str(e)}")
        return jsonify({'error': f'Cleanup failed: {str(e)}'}), 500

@app.route('/original/<task_id>')
def get_original_file(task_id):
    """Serve the original GLB file for 3D comparison viewer"""
    try:
        # Look for the original file in uploads directory
        # Original files are temporarily kept until task completion for comparison
        original_file_path = None
        upload_dir = app.config['UPLOAD_FOLDER']
        
        # Find the original file by task_id prefix
        for filename in os.listdir(upload_dir):
            if filename.startswith(f"{task_id}_") and filename.endswith('.glb'):
                original_file_path = os.path.join(upload_dir, filename)
                break
        
        if not original_file_path or not os.path.exists(original_file_path):
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

@app.route('/download-logs/<task_id>')
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
