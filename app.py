import os
import logging
from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
import uuid
from celery_app import celery
from tasks import optimize_glb_file

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key_change_in_production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configuration
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
ALLOWED_EXTENSIONS = {'glb'}
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file selected'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only GLB files are allowed.'}), 400
    
    if file:
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        
        # Get optimization settings from form
        quality_level = request.form.get('quality_level', 'high')
        enable_lod = request.form.get('enable_lod') == 'true'
        enable_simplification = request.form.get('enable_simplification') == 'true'
        
        # Save uploaded file
        filename = secure_filename(file.filename or "uploaded.glb")
        original_name = filename.rsplit('.', 1)[0]
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{task_id}_{filename}")
        file.save(input_path)
        
        # Get original file size
        original_size = os.path.getsize(input_path)
        
        # Generate output file path
        output_path = os.path.join(
            app.config['OUTPUT_FOLDER'],
            f"{task_id}_optimized_{original_name}.glb"
        )
        
        # Store original file info for comparison viewer
        original_file_info = {
            'path': input_path,
            'size': original_size,
            'name': original_name
        }
        
        # Start Celery task for optimization
        celery_task = optimize_glb_file.delay(
            input_path=input_path,
            output_path=output_path,
            original_name=original_name,
            quality_level=quality_level,
            enable_lod=enable_lod,
            enable_simplification=enable_simplification
        )
        
        return jsonify({
            'task_id': celery_task.id,
            'message': 'File uploaded successfully. Optimization queued.',
            'original_size': original_size
        })



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
            response = {
                'status': 'error',
                'error': str(celery_task.info),
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
