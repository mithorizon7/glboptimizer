import os
import logging
from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
import uuid
import threading
from optimizer import GLBOptimizer

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

# Global dictionary to store optimization progress
optimization_progress = {}

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
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        original_name = filename.rsplit('.', 1)[0]
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{task_id}_{filename}")
        file.save(input_path)
        
        # Get original file size
        original_size = os.path.getsize(input_path)
        
        # Initialize progress tracking
        optimization_progress[task_id] = {
            'status': 'starting',
            'progress': 0,
            'step': 'Initializing...',
            'original_size': original_size,
            'optimized_size': 0,
            'compression_ratio': 0,
            'error': None,
            'completed': False,
            'output_file': None,
            'original_name': original_name
        }
        
        # Start optimization in background thread
        optimizer = GLBOptimizer()
        thread = threading.Thread(
            target=run_optimization,
            args=(optimizer, input_path, task_id, original_name)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'task_id': task_id,
            'message': 'File uploaded successfully. Optimization started.',
            'original_size': original_size
        })

def run_optimization(optimizer, input_path, task_id, original_name):
    """Run the optimization process in a background thread"""
    try:
        output_path = os.path.join(
            app.config['OUTPUT_FOLDER'],
            f"{task_id}_optimized_{original_name}.glb"
        )
        
        def progress_callback(step, progress, message):
            optimization_progress[task_id].update({
                'step': step,
                'progress': progress,
                'status': 'processing'
            })
            logging.debug(f"Task {task_id}: {step} - {progress}% - {message}")
        
        # Run optimization
        result = optimizer.optimize(input_path, output_path, progress_callback)
        
        if result['success']:
            optimized_size = os.path.getsize(output_path)
            compression_ratio = ((optimization_progress[task_id]['original_size'] - optimized_size) / optimization_progress[task_id]['original_size']) * 100
            
            optimization_progress[task_id].update({
                'status': 'completed',
                'progress': 100,
                'step': 'Optimization completed!',
                'optimized_size': optimized_size,
                'compression_ratio': compression_ratio,
                'completed': True,
                'output_file': f"{task_id}_optimized_{original_name}.glb",
                'processing_time': result.get('processing_time', 0)
            })
        else:
            optimization_progress[task_id].update({
                'status': 'error',
                'error': result.get('error', 'Unknown error occurred'),
                'completed': True
            })
    
    except Exception as e:
        logging.error(f"Optimization failed for task {task_id}: {str(e)}")
        optimization_progress[task_id].update({
            'status': 'error',
            'error': str(e),
            'completed': True
        })
    
    finally:
        # Clean up input file
        try:
            os.remove(input_path)
        except:
            pass

@app.route('/progress/<task_id>')
def get_progress(task_id):
    if task_id not in optimization_progress:
        return jsonify({'error': 'Task not found'}), 404
    
    return jsonify(optimization_progress[task_id])

@app.route('/download/<task_id>')
def download_file(task_id):
    if task_id not in optimization_progress:
        return jsonify({'error': 'Task not found'}), 404
    
    progress_info = optimization_progress[task_id]
    if not progress_info.get('completed') or progress_info.get('status') != 'completed':
        return jsonify({'error': 'Optimization not completed or failed'}), 400
    
    output_file = progress_info.get('output_file')
    if not output_file:
        return jsonify({'error': 'Output file not available'}), 404
    
    file_path = os.path.join(app.config['OUTPUT_FOLDER'], output_file)
    if not os.path.exists(file_path):
        return jsonify({'error': 'Output file not found'}), 404
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=f"optimized_{progress_info['original_name']}.glb",
        mimetype='model/gltf-binary'
    )

@app.route('/cleanup/<task_id>', methods=['POST'])
def cleanup_task(task_id):
    """Clean up task files and progress data"""
    if task_id in optimization_progress:
        progress_info = optimization_progress[task_id]
        output_file = progress_info.get('output_file')
        
        # Remove output file
        if output_file:
            output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_file)
            try:
                os.remove(output_path)
            except:
                pass
        
        # Remove progress data
        del optimization_progress[task_id]
    
    return jsonify({'message': 'Task cleaned up successfully'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
