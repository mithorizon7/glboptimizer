// Three.js ES Module Imports with Advanced Compression Support
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { KTX2Loader } from 'three/addons/loaders/KTX2Loader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { MeshoptDecoder } from 'meshopt-decoder';

// GLB Optimizer Frontend JavaScript

class GLBOptimizer {
    constructor() {
        this.currentTaskId = null;
        this.pollInterval = null;
        this.selectedFile = null;
        
        this.initializeElements();
        this.setupEventListeners();
        
        // Initialize tooltips and quality descriptions after DOM is ready
        setTimeout(() => {
            try {
                if (typeof this.initializeTooltips === 'function') {
                    this.initializeTooltips();
                }
                if (typeof this.initializeQualityDescriptions === 'function') {
                    this.initializeQualityDescriptions();
                }
                console.log('UI features initialized successfully');
            } catch (error) {
                console.warn('Error initializing UI features:', error);
            }
        }, 500);
    }
    
    initializeElements() {
        // Get DOM elements
        this.dropZone = document.getElementById('drop-zone');
        this.fileInput = document.getElementById('file-input');
        this.fileInfo = document.getElementById('file-info');
        this.fileDetails = document.getElementById('file-details');
        this.changeFileBtn = document.getElementById('change-file-btn');
        this.uploadBtn = document.getElementById('upload-btn');
        
        // Debug: Check if critical elements exist
        console.log('File input element:', this.fileInput);
        console.log('Drop zone element:', this.dropZone);
        console.log('Upload button element:', this.uploadBtn);
        
        if (!this.fileInput) {
            console.error('CRITICAL: File input element not found!');
        }
        if (!this.dropZone) {
            console.error('CRITICAL: Drop zone element not found!');
        }
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
        if (this.fileInput) {
            console.log('Adding change event listener to file input');
            this.fileInput.addEventListener('change', (e) => {
                console.log('File input change event fired', e.target.files);
                if (e.target.files.length > 0) {
                    this.handleFileSelect(e.target.files[0]);
                }
            });
            
            // Test if we can manually trigger the file dialog
            console.log('File input click test:', () => {
                console.log('Attempting to click file input...');
                this.fileInput.click();
            });
        } else {
            console.error('Cannot add event listener - file input not found!');
        }
        
        // Drop zone click (only for the drop zone area, not the button)
        this.dropZone.addEventListener('click', (e) => {
            // Only trigger file input if clicking on the drop zone itself, not the label/button
            if (e.target === this.dropZone || (e.target.closest('#drop-zone-content') && !e.target.closest('label'))) {
                console.log('Drop zone area clicked, triggering file input');
                this.fileInput.click();
            }
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
        
        // Upload button - now labeled "Start Optimization"
        if (this.uploadBtn) {
            this.uploadBtn.addEventListener('click', () => {
                console.log('Start optimization button clicked');
                this.startOptimization();
            });
        } else {
            console.error('Upload button not found!');
        }
        
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
        
        // Change file button
        if (this.changeFileBtn) {
            this.changeFileBtn.addEventListener('click', () => {
                console.log('Change file button clicked');
                this.fileInput.click();
            });
        }
        
        // Global test function for debugging
        window.testFileUpload = () => {
            console.log('Testing file upload functionality...');
            if (this.fileInput) {
                console.log('File input exists, triggering click...');
                this.fileInput.click();
            } else {
                console.error('File input element not found!');
            }
        };
    }
    
    handleFileSelect(file) {
        console.log('handleFileSelect called with file:', file.name, file.size);
        
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
        
        console.log('File validation passed, setting selectedFile');
        this.selectedFile = file;
        
        // Show file info
        console.log('Updating file details...');
        this.fileDetails.textContent = `Selected: ${file.name} (${this.formatFileSize(file.size)})`;
        this.fileInfo.style.display = 'block';
        
        // Show optimization settings
        console.log('Showing optimization settings...');
        this.optimizationSettings.style.display = 'block';
        
        // Enable upload button
        console.log('Enabling upload button...');
        this.uploadBtn.disabled = false;
        
        // Update drop zone content to show selected file
        const dropZoneContent = document.getElementById('drop-zone-content');
        if (dropZoneContent) {
            dropZoneContent.innerHTML = `
                <i class="fas fa-file-archive fa-3x mb-3 text-success"></i>
                <h5>${file.name}</h5>
                <p class="text-muted">${this.formatFileSize(file.size)}</p>
                <label for="file-input" class="btn btn-outline-secondary" style="cursor: pointer;">
                    <i class="fas fa-exchange-alt me-2"></i>
                    Change File
                </label>
            `;
        }
    }
    
    async startOptimization() {
        console.log('startOptimization called');
        console.log('selectedFile:', this.selectedFile);
        
        if (!this.selectedFile) {
            console.log('No file selected, showing error');
            this.showError('Please select a file first.');
            return;
        }

        // Show progress section immediately
        this.uploadSection.style.display = 'none';
        this.progressSection.style.display = 'block';
        this.progressBar.style.width = '0%';
        this.progressText.textContent = '0%';
        this.currentStep.textContent = 'Starting optimization...';
        
        // Create form data with optimization settings
        console.log('Creating form data...');
        const formData = new FormData();
        formData.append('file', this.selectedFile);
        formData.append('quality_level', this.qualityLevel.value);
        formData.append('enable_lod', this.enableLod.checked);
        formData.append('enable_simplification', this.enableSimplification.checked);
        console.log('Form data created, sending request...');
        
        try {
            // Upload file and start optimization
            console.log('Sending fetch request to /upload...');
            this.progressBar.style.width = '10%';
            this.progressText.textContent = '10%';
            this.currentStep.textContent = 'Uploading file...';
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            
            console.log('Response received:', response.status, response.statusText);
            const result = await response.json();
            console.log('Response data:', result);
            
            if (!response.ok) {
                console.error('Upload failed:', result.error);
                throw new Error(result.error || 'Upload failed');
            }
            
            // Store task ID
            this.currentTaskId = result.task_id;
            console.log('Task ID stored:', this.currentTaskId);
            this.originalSize.textContent = this.formatFileSize(result.original_size);
            
            // Check if processing completed immediately (synchronous mode)
            if (result.status === 'completed') {
                console.log('Optimization completed immediately (synchronous mode)');
                this.progressBar.style.width = '100%';
                this.progressText.textContent = '100%';
                this.currentStep.textContent = 'Optimization complete!';
                
                // Small delay to show completion, then show results
                setTimeout(() => {
                    this.showResults(result);
                }, 1000);
            } else {
                // Show progress section and start polling (async mode)
                console.log('Showing progress section...');
                this.showProgressSection();
                console.log('Starting progress polling for async processing...');
                this.startProgressPolling();
            }
            
        } catch (error) {
            console.error('Optimization error:', error);
            this.showError(error.message);
        }
    }
    
    showProgressSection() {
        console.log('showProgressSection called');
        console.log('Upload section:', this.uploadSection);
        console.log('Progress section:', this.progressSection);
        this.uploadSection.style.display = 'none';
        this.progressSection.style.display = 'block';
        this.resultsSection.style.display = 'none';
        this.errorSection.style.display = 'none';
        console.log('Progress section display set to block');
    }
    
    startProgressPolling() {
        console.log('startProgressPolling called with task ID:', this.currentTaskId);
        this.pollInterval = setInterval(async () => {
            try {
                console.log(`Polling progress for task: ${this.currentTaskId}`);
                const response = await fetch(`/progress/${this.currentTaskId}`);
                const progress = await response.json();
                console.log('Progress response:', progress);
                
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
        this.resultTime.textContent = `${(progress.processing_time || 0).toFixed ? (progress.processing_time || 0).toFixed(1) : (progress.processing_time || 'N/A')}s`;
        
        // Add performance metrics if available
        if (progress.performance_metrics) {
            const performanceHtml = this.generatePerformanceMetrics(progress);
            const resultsContainer = document.querySelector('#results-section .container');
            const existingMetrics = resultsContainer.querySelector('.performance-metrics');
            
            if (existingMetrics) {
                existingMetrics.remove();
            }
            
            const metricsDiv = document.createElement('div');
            metricsDiv.className = 'performance-metrics';
            metricsDiv.innerHTML = performanceHtml;
            resultsContainer.appendChild(metricsDiv);
        }
        
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
        
        // Reset drop zone content to initial state
        document.getElementById('drop-zone-content').innerHTML = `
            <i class="fas fa-cloud-upload-alt fa-3x mb-3 text-muted"></i>
            <h5>Drag & drop your GLB file here</h5>
            <p class="text-muted">or click to select a file</p>
            <label for="file-input" class="btn btn-outline-secondary" style="cursor: pointer;">
                <i class="fas fa-folder-open me-2"></i>
                Choose File
            </label>
        `;
        
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

    generatePerformanceMetrics(progress) {
        if (!progress.performance_metrics) return '';
        
        const metrics = progress.performance_metrics;
        const readiness = metrics.web_game_readiness || {};
        
        return `
            <div class="card mt-3">
                <div class="card-body">
                    <h5 class="card-title">
                        <i class="fas fa-rocket me-2"></i>Performance Gains
                    </h5>
                    <div class="row">
                        <div class="col-md-4">
                            <div class="text-center">
                                <h6 class="text-info">Load Time</h6>
                                <h4 class="text-success">${metrics.estimated_performance_gains?.load_time_improvement || 'N/A'}</h4>
                                <small class="text-muted">Faster Loading</small>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div class="text-center">
                                <h6 class="text-info">GPU Memory</h6>
                                <h4 class="text-success">${metrics.estimated_performance_gains?.gpu_memory_savings || 'N/A'}</h4>
                                <small class="text-muted">Memory Savings</small>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div class="text-center">
                                <h6 class="text-info">Bandwidth</h6>
                                <h4 class="text-success">${metrics.estimated_performance_gains?.bandwidth_savings || 'N/A'}</h4>
                                <small class="text-muted">Data Savings</small>
                            </div>
                        </div>
                    </div>
                    <hr>
                    <div class="row">
                        <div class="col-md-12">
                            <h6>Web Game Readiness</h6>
                            <div class="d-flex gap-2 flex-wrap">
                                ${readiness.ready_for_streaming ? '<span class="badge bg-success">Streaming Ready</span>' : '<span class="badge bg-warning">Large for Streaming</span>'}
                                ${readiness.mobile_friendly ? '<span class="badge bg-success">Mobile Friendly</span>' : '<span class="badge bg-warning">Consider Mobile Optimization</span>'}
                                ${readiness.web_optimized ? '<span class="badge bg-success">Web Optimized</span>' : '<span class="badge bg-danger">Needs Further Optimization</span>'}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
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
        this.setupAdvancedGLTFLoader();
        this.ktx2LoaderInitialized = false;
        this.meshoptInitialized = false;
        this.cameraSynced = false;
        this.isSynced = false;
    }
    
    async setupAdvancedGLTFLoader() {
        // Initialize GLTFLoader exactly as specified
        const loader = new GLTFLoader();
        
        // 1️⃣ Meshopt
        loader.setMeshoptDecoder(MeshoptDecoder);
        
        // 2️⃣ Draco fallback
        const draco = new DRACOLoader().setDecoderPath('/static/libs/draco/');
        loader.setDRACOLoader(draco);
        
        // 3️⃣ KTX2 / BasisU - will be initialized when renderer is available
        this.ktx2Loader = new KTX2Loader().setTranscoderPath('/static/libs/basis/');
        
        // 4️⃣ WebP extension
        loader.register(parser => ({
            name: 'EXT_texture_webp',
            parser,
            afterRoot: () => {}
        }));
        
        // Store configured loader
        this.loader = loader;
        this.dracoLoader = draco;
        
        console.log('✓ GLTFLoader initialized with exact specification pattern');
    }
    
    initializeViewers(originalContainer, optimizedContainer, originalUrl, optimizedUrl) {
        // Clear containers
        originalContainer.innerHTML = '';
        optimizedContainer.innerHTML = '';
        
        // Initialize original viewer
        this.setupViewer(originalContainer, 'original').then(async () => {
            await this.loadModel(originalUrl, 'original');
        });
        
        // Initialize optimized viewer
        this.setupViewer(optimizedContainer, 'optimized').then(async () => {
            await this.loadModel(optimizedUrl, 'optimized');
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
        camera.position.set(0, 0, 3); // Start closer
        
        // Create renderer with modern Three.js r178 settings
        const renderer = new THREE.WebGLRenderer({ 
            antialias: true,
            alpha: false,
            powerPreference: "high-performance"
        });
        renderer.setSize(width, height);
        renderer.setPixelRatio(window.devicePixelRatio);
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.3; // Brighter tone mapping for better visibility
        renderer.outputColorSpace = THREE.SRGBColorSpace; // Updated for r178
        renderer.setClearColor(0x1a1a2e, 1.0); // Ensure background is rendered
        
        // 3️⃣ KTX2 / BasisU initialization with GPU support detection (needs renderer)
        if (this.ktx2Loader && !this.ktx2LoaderInitialized) {
            const ktx2 = this.ktx2Loader.detectSupport(renderer);
            this.loader.setKTX2Loader(ktx2);
            this.ktx2LoaderInitialized = true;
            console.log('✓ KTX2 loader initialized with GPU support detection');
        }
        
        // Enhanced lighting setup for much better model visibility
        // Brighter fill
        scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 2.0));

        // Add a "key" light for contrast
        const key = new THREE.DirectionalLight(0xffffff, 1.5);
        key.position.set(5, 10, 7);
        key.castShadow = true;
        scene.add(key);

        // Soft ambient to fill shadows
        scene.add(new THREE.AmbientLight(0xffffff, 0.3));
        
        // Create controls
        const controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;
        controls.screenSpacePanning = false;
        controls.minDistance = 0.1;
        controls.maxDistance = 20;
        controls.maxPolarAngle = Math.PI;
        controls.target.set(0, 0, 0);
        
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
        
        // Ensure initial render
        renderer.render(scene, camera);
        
        // Ensure initial render
        renderer.render(scene, camera);
        
        return { scene, camera, renderer, controls };
    }
    
    async loadModel(url, type) {
        const container = type === 'original' ? 
            document.getElementById('original-viewer') : 
            document.getElementById('optimized-viewer');
        
        // Show loading indicator
        this.showLoading(container, type);
        
        // For optimized models, try fallback loading first since they use advanced compression
        if (type === 'optimized') {
            console.log('Optimized model detected - using fallback loader for better compatibility');
            this.loadModelWithFallback(url, type, container);
            return;
        }
        
        // Ensure decoders are initialized before loading compressed files
        await this.ensureDecodersInitialized(type);
        
        this.loader.load(
            url,
            (gltf) => {
                this.onModelLoaded(gltf, type);
                console.log(`${type} model loaded successfully`);
            },
            (progress) => {
                // Progress callback
                const percent = (progress.loaded / progress.total * 100);
                this.updateLoadingProgress(container, percent);
            },
            (error) => {
                console.error(`Error loading ${type} model:`, error);
                
                // Enhanced error handling for compression formats and GLB loading issues
                if (error.message && (error.message.includes('sourceDef.uri') || 
                    error.message.includes('undefined is not an object') ||
                    error.message.includes('Cannot read properties of undefined'))) {
                    console.warn('GLB texture/URI error detected - trying fallback loading approach');
                    // Try loading without advanced texture extensions
                    this.loadModelWithFallback(url, type, container);
                    return;
                } else if (error.message && error.message.includes('KTX2')) {
                    console.warn('KTX2 texture loading failed, model may still display with fallback textures');
                } else if (error.message && error.message.includes('Meshopt')) {
                    console.warn('Meshopt compression failed, trying fallback decompression');
                } else if (error.message && error.message.includes('WebP')) {
                    console.warn('WebP texture loading failed, checking browser support');
                }
                
                this.showError(container, `Failed to load ${type} model: ${error.message || 'Unknown error'}`);
            }
        );
    }
    
    async loadModelWithFallback(url, type, container) {
        console.log(`Attempting fallback loading for ${type} model without advanced texture extensions`);
        
        // Create a completely basic GLTFLoader without any advanced extensions
        const fallbackLoader = new GLTFLoader();
        
        // Only add Meshopt decoder which is more stable
        try {
            fallbackLoader.setMeshoptDecoder(MeshoptDecoder);
            console.log('✓ Basic Meshopt decoder added to fallback loader');
        } catch (error) {
            console.warn('Meshopt decoder failed for fallback loader:', error);
        }
        
        fallbackLoader.load(
            url,
            (gltf) => {
                this.onModelLoaded(gltf, type);
                console.log(`${type} model loaded successfully with fallback loader`);
            },
            (progress) => {
                const percent = (progress.loaded / progress.total * 100);
                this.updateLoadingProgress(container, percent);
            },
            (error) => {
                console.error(`Fallback loading also failed for ${type} model:`, error);
                this.showError(container, `Failed to load ${type} model even with fallback: ${error.message || 'Unknown error'}`);
            }
        );
    }
    
    async ensureDecodersInitialized(type) {
        // Ensure Meshopt decoder is properly initialized for each model
        if (!this.meshoptInitialized) {
            try {
                this.loader.setMeshoptDecoder(MeshoptDecoder);
                this.meshoptInitialized = true;
                console.log(`✓ Meshopt decoder ensured for ${type} model loading`);
            } catch (error) {
                console.error(`Meshopt decoder initialization failed for ${type}:`, error);
            }
        }
        
        // Ensure KTX2 loader is properly configured with GPU support
        if (this.ktx2Loader && !this.ktx2LoaderInitialized) {
            // Get the renderer based on type
            const renderer = type === 'original' ? this.originalRenderer : this.optimizedRenderer;
            if (renderer) {
                this.ktx2Loader.detectSupport(renderer);
                this.loader.setKTX2Loader(this.ktx2Loader);
                this.ktx2LoaderInitialized = true;
                console.log(`✓ KTX2 loader initialized with GPU support for ${type} model`);
            }
        }
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
        
        // Scale to fit in view - make models larger and closer
        const maxSize = Math.max(size.x, size.y, size.z);
        const scale = 4 / maxSize;  // Larger scale for better visibility
        model.scale.setScalar(scale);
        
        // Adjust camera position based on model size - much closer
        const distance = Math.max(maxSize * 1.5, 3); // Closer distance, minimum 3 units
        camera.position.set(0, 0, distance);
        camera.lookAt(0, 0, 0);
        
        // Update controls target and force render
        const controls = type === 'original' ? this.originalControls : this.optimizedControls;
        const renderer = type === 'original' ? this.originalRenderer : this.optimizedRenderer;
        
        if (controls) {
            controls.target.set(0, 0, 0);
            controls.update();
        }
        
        // Force immediate render after model load
        if (renderer) {
            renderer.render(scene, camera);
            console.log(`${type} model rendered successfully`);
        }
        
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
        
        // Debug information
        console.log(`${type} model loaded successfully`);
        console.log(`${type} model info:`, {
            position: model.position.toArray(),
            scale: model.scale.toArray(),
            box: box,
            center: center.toArray(),
            size: size.toArray(),
            maxSize: maxSize,
            cameraDistance: distance,
            sceneChildren: scene.children.length,
            modelVisible: model.visible,
            rendererInfo: renderer.info
        });
        
        // Ensure model is visible
        model.visible = true;
        model.traverse((child) => {
            if (child.isMesh) {
                child.visible = true;
                child.frustumCulled = false; // Prevent culling issues
            }
        });
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
    
    initializeTooltips() {
        // Initialize Bootstrap tooltips for all elements with data-bs-toggle="tooltip"
        // Use a timeout to ensure Bootstrap is loaded
        setTimeout(() => {
            try {
                if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
                    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
                    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
                    console.log('Tooltips initialized successfully');
                } else {
                    console.warn('Bootstrap tooltips not available, falling back to title attributes');
                }
            } catch (error) {
                console.warn('Error initializing tooltips:', error);
            }
        }, 100);
    }
    
    initializeQualityDescriptions() {
        // Update quality description when selection changes
        const qualitySelect = document.getElementById('quality-level');
        const qualityDescription = document.getElementById('quality-description');
        
        if (qualitySelect && qualityDescription) {
            qualitySelect.addEventListener('change', (e) => {
                const selectedOption = e.target.selectedOptions[0];
                const description = selectedOption.getAttribute('data-description');
                if (description) {
                    qualityDescription.textContent = description;
                }
            });
        }
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing GLB Optimizer...');
    try {
        new GLBOptimizer();
        console.log('GLB Optimizer initialized successfully');
    } catch (error) {
        console.error('Error initializing GLB Optimizer:', error);
    }
});
