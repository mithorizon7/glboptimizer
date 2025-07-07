// Three.js ES Module Imports
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// GLB Optimizer Frontend JavaScript

class GLBOptimizer {
    constructor() {
        this.currentTaskId = null;
        this.pollInterval = null;
        this.selectedFile = null;
        
        this.initializeElements();
        this.setupEventListeners();
    }
    
    initializeElements() {
        // Get DOM elements
        this.dropZone = document.getElementById('drop-zone');
        this.fileInput = document.getElementById('file-input');
        this.fileInfo = document.getElementById('file-info');
        this.fileDetails = document.getElementById('file-details');
        this.uploadBtn = document.getElementById('upload-btn');
        this.optimizationSettings = document.getElementById('optimization-settings');
        this.qualityLevel = document.getElementById('quality-level');
        this.enableLod = document.getElementById('enable-lod');
        this.enableSimplification = document.getElementById('enable-simplification');
        
        // 3D Viewer elements
        this.modelViewerSection = document.getElementById('model-viewer-section');
        this.originalViewer = document.getElementById('original-viewer');
        this.optimizedViewer = document.getElementById('optimized-viewer');
        this.originalModelSize = document.getElementById('original-model-size');
        this.optimizedModelSize = document.getElementById('optimized-model-size');
        this.syncCamerasBtn = document.getElementById('sync-cameras-btn');
        this.resetCamerasBtn = document.getElementById('reset-cameras-btn');
        
        // 3D Viewer instances
        this.viewer3D = new ModelViewer3D();
        
        // Sections
        this.uploadSection = document.getElementById('upload-section');
        this.progressSection = document.getElementById('progress-section');
        this.resultsSection = document.getElementById('results-section');
        this.errorSection = document.getElementById('error-section');
        
        // Progress elements
        this.progressBar = document.getElementById('progress-bar');
        this.currentStep = document.getElementById('current-step');
        this.progressText = document.getElementById('progress-text');
        this.sizeInfo = document.getElementById('size-info');
        this.originalSize = document.getElementById('original-size');
        this.optimizedSize = document.getElementById('optimized-size');
        this.compressionRatio = document.getElementById('compression-ratio');
        
        // Result elements
        this.resultOriginalSize = document.getElementById('result-original-size');
        this.resultOptimizedSize = document.getElementById('result-optimized-size');
        this.resultCompression = document.getElementById('result-compression');
        this.resultTime = document.getElementById('result-time');
        this.downloadBtn = document.getElementById('download-btn');
        this.newOptimizationBtn = document.getElementById('new-optimization-btn');
        
        // Error elements
        this.errorMessage = document.getElementById('error-message');
        this.errorDetails = document.getElementById('error-details');
        this.errorCategory = document.getElementById('error-category');
        this.technicalDetails = document.getElementById('technical-details');
        this.showErrorDetailsBtn = document.getElementById('show-error-details-btn');
        this.downloadLogsBtn = document.getElementById('download-logs-btn');
        this.retryBtn = document.getElementById('retry-btn');
    }
    
    setupEventListeners() {
        // File input change
        this.fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleFileSelect(e.target.files[0]);
            }
        });
        
        // Drag and drop
        this.dropZone.addEventListener('click', () => {
            this.fileInput.click();
        });
        
        this.dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.dropZone.classList.add('dragover');
        });
        
        this.dropZone.addEventListener('dragleave', () => {
            this.dropZone.classList.remove('dragover');
        });
        
        this.dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            this.dropZone.classList.remove('dragover');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.handleFileSelect(files[0]);
            }
        });
        
        // Upload button
        this.uploadBtn.addEventListener('click', () => {
            this.startOptimization();
        });
        
        // Download button
        this.downloadBtn.addEventListener('click', () => {
            this.downloadOptimizedFile();
        });
        
        // New optimization button
        this.newOptimizationBtn.addEventListener('click', () => {
            this.resetUI();
        });
        
        // Retry button
        this.retryBtn.addEventListener('click', () => {
            this.resetUI();
        });
        
        // 3D Viewer controls
        this.syncCamerasBtn.addEventListener('click', () => {
            // Toggle camera sync state
            if (this.viewer3D.isSynced) {
                this.viewer3D.unsyncCameras();
                this.syncCamerasBtn.innerHTML = '<i class="fas fa-link me-1"></i>Sync Cameras';
                this.syncCamerasBtn.classList.remove('btn-success');
                this.syncCamerasBtn.classList.add('btn-outline-secondary');
            } else {
                this.viewer3D.syncCameras();
                this.syncCamerasBtn.innerHTML = '<i class="fas fa-unlink me-1"></i>Unsync Cameras';
                this.syncCamerasBtn.classList.remove('btn-outline-secondary');
                this.syncCamerasBtn.classList.add('btn-success');
            }
        });
        
        this.resetCamerasBtn.addEventListener('click', () => {
            this.viewer3D.resetCameras();
        });
    }
    
    handleFileSelect(file) {
        // Validate file type
        if (!file.name.toLowerCase().endsWith('.glb')) {
            this.showError('Please select a valid GLB file.');
            return;
        }
        
        // Validate file size (100MB limit)
        const maxSize = 100 * 1024 * 1024; // 100MB
        if (file.size > maxSize) {
            this.showError('File size must be less than 100MB.');
            return;
        }
        
        this.selectedFile = file;
        
        // Show file info
        this.fileDetails.textContent = `Selected: ${file.name} (${this.formatFileSize(file.size)})`;
        this.fileInfo.style.display = 'block';
        
        // Show optimization settings
        this.optimizationSettings.style.display = 'block';
        
        // Enable upload button
        this.uploadBtn.disabled = false;
        
        // Update drop zone text
        this.dropZone.innerHTML = `
            <i class="fas fa-file-archive fa-3x mb-3 text-success"></i>
            <h5>${file.name}</h5>
            <p class="text-muted">${this.formatFileSize(file.size)}</p>
            <button type="button" class="btn btn-outline-secondary" onclick="document.getElementById('file-input').click()">
                <i class="fas fa-exchange-alt me-2"></i>
                Change File
            </button>
        `;
    }
    
    async startOptimization() {
        if (!this.selectedFile) {
            this.showError('Please select a file first.');
            return;
        }
        
        // Create form data with optimization settings
        const formData = new FormData();
        formData.append('file', this.selectedFile);
        formData.append('quality_level', this.qualityLevel.value);
        formData.append('enable_lod', this.enableLod.checked);
        formData.append('enable_simplification', this.enableSimplification.checked);
        
        try {
            // Upload file and start optimization
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (!response.ok) {
                throw new Error(result.error || 'Upload failed');
            }
            
            // Store task ID and start polling
            this.currentTaskId = result.task_id;
            this.originalSize.textContent = this.formatFileSize(result.original_size);
            
            // Show progress section
            this.showProgressSection();
            this.startProgressPolling();
            
        } catch (error) {
            this.showError(error.message);
        }
    }
    
    showProgressSection() {
        this.uploadSection.style.display = 'none';
        this.progressSection.style.display = 'block';
        this.resultsSection.style.display = 'none';
        this.errorSection.style.display = 'none';
    }
    
    startProgressPolling() {
        this.pollInterval = setInterval(async () => {
            try {
                const response = await fetch(`/progress/${this.currentTaskId}`);
                const progress = await response.json();
                
                if (!response.ok) {
                    throw new Error(progress.error || 'Failed to get progress');
                }
                
                this.updateProgress(progress);
                
                if (progress.completed) {
                    clearInterval(this.pollInterval);
                    
                    if (progress.status === 'completed') {
                        this.showResults(progress);
                    } else if (progress.status === 'error') {
                        this.showError(progress.error);
                    }
                }
                
            } catch (error) {
                clearInterval(this.pollInterval);
                this.showError(error.message);
            }
        }, 1000); // Poll every second
    }
    
    updateProgress(progress) {
        // Update progress bar
        this.progressBar.style.width = `${progress.progress}%`;
        this.progressText.textContent = `${progress.progress}%`;
        
        // Update current step
        this.currentStep.textContent = progress.step;
        
        // Show size info if available
        if (progress.optimized_size > 0) {
            this.optimizedSize.textContent = this.formatFileSize(progress.optimized_size);
            this.compressionRatio.textContent = `${progress.compression_ratio.toFixed(1)}%`;
            this.sizeInfo.style.display = 'block';
        }
    }
    
    showResults(progress) {
        // Hide progress section, show results and viewer
        this.progressSection.style.display = 'none';
        this.resultsSection.style.display = 'block';
        this.modelViewerSection.style.display = 'block';
        
        // Update result statistics
        this.resultOriginalSize.textContent = this.formatFileSize(progress.original_size);
        this.resultOptimizedSize.textContent = this.formatFileSize(progress.optimized_size);
        this.resultCompression.textContent = `${progress.compression_ratio.toFixed(1)}%`;
        this.resultTime.textContent = `${progress.processing_time.toFixed(1)}s`;
        
        // Initialize 3D model viewer with before/after comparison
        this.initialize3DViewer(progress);
    }
    
    async downloadOptimizedFile() {
        if (!this.currentTaskId) return;
        
        try {
            const response = await fetch(`/download/${this.currentTaskId}`);
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Download failed');
            }
            
            // Create download link
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `optimized_${this.selectedFile.name}`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            // Clean up task
            await fetch(`/cleanup/${this.currentTaskId}`, { method: 'POST' });
            
        } catch (error) {
            this.showError(error.message);
        }
    }
    
    showError(error) {
        // Hide other sections
        this.uploadSection.style.display = 'none';
        this.progressSection.style.display = 'none';
        this.resultsSection.style.display = 'none';
        this.errorSection.style.display = 'block';
        
        // Handle error object or string
        if (typeof error === 'object' && error !== null) {
            // Detailed error object
            this.errorMessage.textContent = error.user_message || error.error || 'An unknown error occurred';
            
            if (error.category || error.detailed_error) {
                // Show enhanced error details
                if (this.errorCategory) {
                    this.errorCategory.textContent = `Category: ${error.category || 'Unknown'}`;
                }
                if (this.technicalDetails && error.detailed_error) {
                    this.technicalDetails.textContent = error.detailed_error;
                }
                
                // Enable show details button
                if (this.showErrorDetailsBtn) {
                    this.showErrorDetailsBtn.style.display = 'inline-block';
                    this.showErrorDetailsBtn.onclick = () => {
                        if (this.errorDetails) {
                            const isHidden = this.errorDetails.style.display === 'none';
                            this.errorDetails.style.display = isHidden ? 'block' : 'none';
                            this.showErrorDetailsBtn.innerHTML = isHidden ? 
                                '<i class="fas fa-eye-slash me-1"></i>Hide Technical Details' : 
                                '<i class="fas fa-info-circle me-1"></i>Show Technical Details';
                        }
                    };
                }
            }
        } else {
            // Simple error string
            this.errorMessage.textContent = error || 'An unknown error occurred';
            
            // Hide enhanced error features
            if (this.showErrorDetailsBtn) {
                this.showErrorDetailsBtn.style.display = 'none';
            }
            if (this.errorDetails) {
                this.errorDetails.style.display = 'none';
            }
        }
        
        // Enable download logs button
        if (this.downloadLogsBtn && this.currentTaskId) {
            this.downloadLogsBtn.style.display = 'inline-block';
            this.downloadLogsBtn.onclick = () => {
                window.open(`/download-logs/${this.currentTaskId}`, '_blank');
            };
        }
        
        // Stop polling if active
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
        }
    }
    
    resetUI() {
        // Clear current task
        this.currentTaskId = null;
        this.selectedFile = null;
        
        // Stop polling
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
        }
        
        // Reset UI elements
        this.fileInput.value = '';
        this.fileInfo.style.display = 'none';
        this.optimizationSettings.style.display = 'none';
        this.uploadBtn.disabled = true;
        
        // Reset drop zone
        this.dropZone.innerHTML = `
            <i class="fas fa-cloud-upload-alt fa-3x mb-3 text-muted"></i>
            <h5>Drag & drop your GLB file here</h5>
            <p class="text-muted">or click to select a file</p>
            <input type="file" id="file-input" accept=".glb" style="display: none;">
            <button type="button" class="btn btn-outline-secondary" onclick="document.getElementById('file-input').click()">
                <i class="fas fa-folder-open me-2"></i>
                Choose File
            </button>
        `;
        
        // Re-setup file input listener
        this.fileInput = document.getElementById('file-input');
        this.fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleFileSelect(e.target.files[0]);
            }
        });
        
        // Reset progress
        this.progressBar.style.width = '0%';
        this.progressText.textContent = '0%';
        this.currentStep.textContent = 'Initializing...';
        this.sizeInfo.style.display = 'none';
        
        // Show upload section
        this.uploadSection.style.display = 'block';
        this.progressSection.style.display = 'none';
        this.resultsSection.style.display = 'none';
        this.errorSection.style.display = 'none';
        this.modelViewerSection.style.display = 'none';
        
        // Clear 3D viewers
        if (this.viewer3D) {
            this.originalViewer.innerHTML = '';
            this.optimizedViewer.innerHTML = '';
        }
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    initialize3DViewer(progress) {
        // Update model size displays
        this.originalModelSize.textContent = this.formatFileSize(progress.original_size);
        this.optimizedModelSize.textContent = this.formatFileSize(progress.optimized_size);
        
        // Initialize viewers with model URLs
        const originalUrl = `/original/${this.currentTaskId}`;
        const optimizedUrl = `/download/${this.currentTaskId}`;
        
        try {
            this.viewer3D.initializeViewers(
                this.originalViewer,
                this.optimizedViewer,
                originalUrl,
                optimizedUrl
            );
            
            // Enable camera syncing by default for better comparison experience
            setTimeout(() => {
                this.viewer3D.syncCameras();
                // Update button state to reflect default syncing
                this.syncCamerasBtn.innerHTML = '<i class="fas fa-unlink me-1"></i>Unsync Cameras';
                this.syncCamerasBtn.classList.remove('btn-outline-secondary');
                this.syncCamerasBtn.classList.add('btn-success');
            }, 1000); // Give viewers time to initialize
            
        } catch (error) {
            console.error('Failed to initialize 3D viewer:', error);
            // Show fallback message
            this.originalViewer.innerHTML = `
                <div class="model-viewer-error">
                    <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                    <div>3D viewer not available</div>
                    <small class="text-muted">Models can still be downloaded</small>
                </div>
            `;
            this.optimizedViewer.innerHTML = `
                <div class="model-viewer-error">
                    <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                    <div>3D viewer not available</div>
                    <small class="text-muted">Models can still be downloaded</small>
                </div>
            `;
        }
    }
}

// 3D Model Viewer Class using Three.js
class ModelViewer3D {
    constructor() {
        this.originalScene = null;
        this.optimizedScene = null;
        this.originalCamera = null;
        this.optimizedCamera = null;
        this.originalRenderer = null;
        this.optimizedRenderer = null;
        this.originalControls = null;
        this.optimizedControls = null;
        this.loader = new GLTFLoader();
        this.cameraSynced = false;
        this.isSynced = false;
    }
    
    initializeViewers(originalContainer, optimizedContainer, originalUrl, optimizedUrl) {
        // Clear containers
        originalContainer.innerHTML = '';
        optimizedContainer.innerHTML = '';
        
        // Initialize original viewer
        this.setupViewer(originalContainer, 'original').then(() => {
            this.loadModel(originalUrl, 'original');
        });
        
        // Initialize optimized viewer
        this.setupViewer(optimizedContainer, 'optimized').then(() => {
            this.loadModel(optimizedUrl, 'optimized');
        });
    }
    
    async setupViewer(container, type) {
        const width = container.clientWidth;
        const height = container.clientHeight;
        
        // Create scene
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x1a1a2e);
        
        // Create camera
        const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
        camera.position.set(0, 0, 5);
        
        // Create renderer
        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(width, height);
        renderer.setPixelRatio(window.devicePixelRatio);
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1;
        
        // Add lights
        const ambientLight = new THREE.AmbientLight(0x404040, 0.6);
        scene.add(ambientLight);
        
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(5, 5, 5);
        directionalLight.castShadow = true;
        directionalLight.shadow.mapSize.width = 2048;
        directionalLight.shadow.mapSize.height = 2048;
        scene.add(directionalLight);
        
        const directionalLight2 = new THREE.DirectionalLight(0xffffff, 0.4);
        directionalLight2.position.set(-5, -5, -5);
        scene.add(directionalLight2);
        
        // Create controls
        const controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;
        controls.screenSpacePanning = false;
        controls.minDistance = 1;
        controls.maxDistance = 100;
        controls.maxPolarAngle = Math.PI;
        
        // Store references
        if (type === 'original') {
            this.originalScene = scene;
            this.originalCamera = camera;
            this.originalRenderer = renderer;
            this.originalControls = controls;
        } else {
            this.optimizedScene = scene;
            this.optimizedCamera = camera;
            this.optimizedRenderer = renderer;
            this.optimizedControls = controls;
        }
        
        // Add to container
        container.appendChild(renderer.domElement);
        
        // Handle resize
        const resizeObserver = new ResizeObserver(entries => {
            for (let entry of entries) {
                const { width, height } = entry.contentRect;
                camera.aspect = width / height;
                camera.updateProjectionMatrix();
                renderer.setSize(width, height);
            }
        });
        resizeObserver.observe(container);
        
        // Start render loop
        const animate = () => {
            requestAnimationFrame(animate);
            controls.update();
            renderer.render(scene, camera);
        };
        animate();
        
        return { scene, camera, renderer, controls };
    }
    
    loadModel(url, type) {
        const container = type === 'original' ? 
            document.getElementById('original-viewer') : 
            document.getElementById('optimized-viewer');
        
        // Show loading indicator
        this.showLoading(container, type);
        
        this.loader.load(
            url,
            (gltf) => {
                this.onModelLoaded(gltf, type);
            },
            (progress) => {
                // Progress callback
                const percent = (progress.loaded / progress.total * 100);
                this.updateLoadingProgress(container, percent);
            },
            (error) => {
                console.error(`Error loading ${type} model:`, error);
                this.showError(container, `Failed to load ${type} model`);
            }
        );
    }
    
    onModelLoaded(gltf, type) {
        const scene = type === 'original' ? this.originalScene : this.optimizedScene;
        const camera = type === 'original' ? this.originalCamera : this.optimizedCamera;
        const container = type === 'original' ? 
            document.getElementById('original-viewer') : 
            document.getElementById('optimized-viewer');
        
        // Remove loading indicator
        this.hideLoading(container);
        
        // Add model to scene
        const model = gltf.scene;
        scene.add(model);
        
        // Center and scale model
        const box = new THREE.Box3().setFromObject(model);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        
        // Center the model
        model.position.sub(center);
        
        // Scale to fit in view
        const maxSize = Math.max(size.x, size.y, size.z);
        const scale = 3 / maxSize;
        model.scale.setScalar(scale);
        
        // Adjust camera position
        camera.position.set(0, 0, maxSize * 1.5);
        
        // Enable animations if present
        if (gltf.animations && gltf.animations.length > 0) {
            const mixer = new THREE.AnimationMixer(model);
            const action = mixer.clipAction(gltf.animations[0]);
            action.play();
            
            // Store mixer for animation updates
            const animate = () => {
                requestAnimationFrame(animate);
                mixer.update(0.01);
            };
            animate();
        }
        
        console.log(`${type} model loaded successfully`);
    }
    
    showLoading(container, type) {
        const loading = document.createElement('div');
        loading.className = 'model-loading';
        loading.innerHTML = `
            <div class="spinner-border" role="status"></div>
            <div>Loading ${type} model...</div>
        `;
        container.appendChild(loading);
    }
    
    updateLoadingProgress(container, percent) {
        const loading = container.querySelector('.model-loading div:last-child');
        if (loading) {
            loading.textContent = `Loading... ${Math.round(percent)}%`;
        }
    }
    
    hideLoading(container) {
        const loading = container.querySelector('.model-loading');
        if (loading) {
            loading.remove();
        }
    }
    
    showError(container, message) {
        container.innerHTML = `
            <div class="model-viewer-error">
                <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                <div>${message}</div>
            </div>
        `;
    }
    
    syncCameras() {
        if (!this.originalCamera || !this.optimizedCamera || this.isSynced) return;
        
        this.cameraSynced = true;
        this.isSynced = true;
        
        // Sync optimized camera to original
        this.optimizedCamera.position.copy(this.originalCamera.position);
        this.optimizedCamera.rotation.copy(this.originalCamera.rotation);
        this.optimizedControls.target.copy(this.originalControls.target);
        this.optimizedControls.update();
        
        // Add sync indicators
        document.querySelector('#original-viewer').closest('.card').classList.add('camera-synced');
        document.querySelector('#optimized-viewer').closest('.card').classList.add('camera-synced');
        
        // Sync on camera changes
        this.originalControls.addEventListener('change', this.onCameraChange.bind(this));
    }
    
    unsyncCameras() {
        if (!this.isSynced) return;
        
        this.cameraSynced = false;
        this.isSynced = false;
        
        // Remove sync
        this.originalControls.removeEventListener('change', this.onCameraChange.bind(this));
        
        // Remove sync indicators
        document.querySelector('#original-viewer').closest('.card').classList.remove('camera-synced');
        document.querySelector('#optimized-viewer').closest('.card').classList.remove('camera-synced');
    }
    
    onCameraChange() {
        if (this.cameraSynced && this.optimizedCamera && this.optimizedControls) {
            this.optimizedCamera.position.copy(this.originalCamera.position);
            this.optimizedCamera.rotation.copy(this.originalCamera.rotation);
            this.optimizedControls.target.copy(this.originalControls.target);
            this.optimizedControls.update();
        }
    }
    
    resetCameras() {
        if (this.originalControls) {
            this.originalControls.reset();
        }
        if (this.optimizedControls) {
            this.optimizedControls.reset();
        }
        
        // Unsync cameras and update state
        this.unsyncCameras();
        
        // Reset sync button to default state
        const syncBtn = document.getElementById('sync-cameras-btn');
        if (syncBtn) {
            syncBtn.innerHTML = '<i class="fas fa-link me-1"></i>Sync Cameras';
            syncBtn.classList.remove('btn-success');
            syncBtn.classList.add('btn-outline-secondary');
        }
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new GLBOptimizer();
});

// Initialize the optimizer when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new GLBOptimizer();
});
