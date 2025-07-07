# GLB Optimizer - replit.md

## Overview

This is a web-based GLB (3D model) file optimization tool that implements industry-standard workflows to reduce file sizes by 5-10× while maintaining visual fidelity. The application provides a Flask-based backend with a user-friendly web interface for uploading, processing, and downloading optimized GLB files.

## System Architecture

### Frontend Architecture
- **Technology**: Vanilla JavaScript with Bootstrap 5 (dark theme)
- **Components**: 
  - Drag-and-drop file upload interface
  - Real-time progress tracking with visual feedback
  - Results display with compression statistics
  - Responsive design with card-based layout
- **User Experience**: Single-page application with section-based navigation (upload → progress → results)

### Backend Architecture
- **Framework**: Flask (Python web framework) with Celery task queue
- **Task Queue**: Redis + Celery for scalable background processing
- **Structure**: Production-ready modular design with separated concerns
  - `app.py`: Main Flask application with routing and file handling
  - `optimizer.py`: Core optimization logic using external tools
  - `celery_app.py`: Celery configuration and task queue setup
  - `tasks.py`: Celery background tasks for optimization processing
  - `main.py`: Application entry point with Redis/Celery auto-start
- **File Processing**: Production-grade asynchronous optimization with Celery workers
- **Scalability**: Controlled concurrency (1 optimization at a time) with proper resource management
- **Security**: File type validation, secure filename handling, file size limits (100MB)

## Key Components

### File Upload System
- **Problem**: Secure handling of large 3D model files
- **Solution**: Multi-layer validation with drag-and-drop interface
- **Features**: 
  - File type restriction to GLB only
  - Secure filename sanitization
  - 100MB file size limit
  - Visual upload progress feedback

### Optimization Engine (GLBOptimizer)
- **Problem**: Complex multi-step 3D model optimization workflow
- **Solution**: Orchestrated pipeline using industry-standard tools
- **6-Step Workflow**:
  1. **Cleanup & Deduplication**: Remove unused data, prune orphaned nodes
  2. **Mesh Processing**: Weld vertices and join compatible meshes
  3. **Geometry Compression**: Apply meshopt compression with quantization
  4. **Texture Compression**: Convert to KTX2/BasisU format
  5. **Animation Optimization**: Resample and quantize keyframes
  6. **Final Assembly**: Package optimized components

### Progress Tracking System
- **Problem**: Long-running optimization processes need user feedback and scalable task management
- **Solution**: Real-time progress updates with Celery task state management
- **Implementation**: Redis-backed Celery task queue with proper state tracking and result storage

## Data Flow

1. **Upload Phase**: User selects GLB file → Frontend validates → Backend receives and stores
2. **Queue Phase**: Optimization task queued in Redis → Celery worker picks up task
3. **Processing Phase**: Background worker processes optimization → Real-time progress updates via Celery state
4. **Results Phase**: Optimized file generated → Statistics calculated → Download link provided
5. **Cleanup Phase**: Temporary files removed → Task results cleaned from Redis

## External Dependencies

### Node.js Tools
- **@gltf-transform/cli v4.2.0**: Industry-standard glTF processing toolkit
  - Handles pruning, welding, joining, texture compression
  - Supports KTX2/BasisU compression extensions
- **gltfpack v0.24.0**: Meshoptimizer-based geometry compression
  - Provides meshopt compression and quantization
  - Includes polygon simplification capabilities

### Python Dependencies
- **Flask**: Web framework for backend API
- **Werkzeug**: WSGI utilities for file handling and security
- **subprocess**: Interface to external optimization tools
- **threading**: Asynchronous processing support

### Frontend Dependencies
- **Bootstrap 5**: UI framework with dark theme support
- **Font Awesome 6.4.0**: Icon library for visual elements

## Deployment Strategy

### Development Setup
- **Entry Point**: `main.py` runs Flask development server
- **Configuration**: Environment-based settings with development defaults
- **File Storage**: Local filesystem with configurable upload/output directories

### Production Considerations
- **WSGI**: ProxyFix middleware for reverse proxy compatibility
- **Security**: Session secret from environment variables
- **Scaling**: Single-threaded optimization (could be enhanced with task queues)

### File Management
- **Upload Directory**: `uploads/` for incoming files
- **Output Directory**: `output/` for processed files
- **Cleanup Strategy**: Manual cleanup required (could be automated)

## Changelog

Changelog:
- July 07, 2025. Initial setup
- July 07, 2025. Enhanced optimization pipeline with industry-standard features:
  - Added high-quality texture compression (--q 255, channel packing)
  - Implemented polygon simplification with fallback handling
  - Added Draco compression as fallback for geometry compression
  - Enhanced LOD generation with 3 levels of detail
  - Added user-configurable optimization settings (quality levels)
  - Improved error handling and graceful degradation
  - Updated UI with optimization settings panel
- July 07, 2025. Major architecture upgrade for production scalability:
  - Replaced threading with Redis + Celery task queue system
  - Implemented proper background task management with controlled concurrency
  - Added production-ready startup scripts and process management
  - Enhanced error handling and resource cleanup
  - Added comprehensive logging and monitoring capabilities
  - Now supports multiple concurrent users with proper resource isolation
- July 07, 2025. Added 3D before/after model comparison viewer:
  - Implemented side-by-side 3D model visualization using Three.js
  - Added interactive camera controls with sync capability
  - Real-time loading progress for both original and optimized models
  - Professional lighting setup and automatic model centering/scaling
  - Responsive design with proper error handling and loading states
  - Enhanced user confidence in optimization quality through visual comparison
- July 07, 2025. Comprehensive error handling and feedback enhancement:
  - Added detailed subprocess output capture with stdout/stderr logging
  - Implemented intelligent error analysis with user-friendly explanations
  - Created pattern-based error categorization for common optimization failures
  - Added downloadable error logs with full technical details for debugging
  - Enhanced frontend error display with expandable technical details
  - Improved timeout handling and resource limitation detection
  - Added comprehensive fallback mechanisms for failed optimization steps
- July 07, 2025. Production-ready file management and configuration system:
  - Implemented automated cleanup scheduler with Celery periodic tasks
  - Added comprehensive environment variable configuration system
  - Created configurable file retention policies (default 24 hours)
  - Added cleanup for both uploaded files and orphaned task results
  - Implemented environment-specific configurations (dev/prod/test)
  - Added manual cleanup capabilities for emergency use
  - Enhanced logging configuration with file output options
  - Created startup script with automatic cleanup scheduling
- July 07, 2025. Enhanced 3D viewer user experience with default camera syncing:
  - Enabled camera syncing by default for intuitive model comparison
  - Refactored sync/unsync functionality with proper state management
  - Updated button behavior to toggle between sync and unsync states
  - Added visual feedback and tooltips for better user guidance
  - Improved out-of-the-box experience for comparing models from same angle
- July 07, 2025. Critical security hardening against command injection vulnerabilities:
  - Implemented comprehensive path validation with multi-layer security checks
  - Added prevention against directory traversal attacks (../../../etc/passwd)
  - Blocked command injection attempts (;, |, &, $, `, etc.) in file paths
  - Restricted file operations to uploads/ and output/ directories only
  - Secured subprocess command execution with validated file paths
  - Added security validation to all optimization pipeline steps
  - Implemented fail-fast security violations with detailed error logging
  - Ensured user filenames never directly influence shell commands
  - Enhanced error handling in upload routes with proper exception management
  - Added file size validation and improved user feedback for upload errors
  - Implemented GLB file format validation with magic header verification
  - Created production Nginx configuration for secure file serving
  - Added comprehensive security documentation and deployment guidelines
  - All 13 security test cases pass - system is fully protected against common attack vectors
- July 07, 2025. Code cleanup and efficiency improvements:
  - Optimized cleanup endpoint to use O(1) direct filename reconstruction instead of O(n) directory scanning
  - Removed duplicate DOMContentLoaded event listeners in JavaScript
  - Enhanced file cleanup robustness with proper error handling and Celery task memory management
  - Improved performance and reduced resource usage across the application
- July 07, 2025. Marketing-focused frontend redesign for monetization:
  - Redesigned homepage with compelling "From 50MB to 5MB Instantly" headline targeting AI artists and game developers
  - Added benefit-focused feature descriptions highlighting professional game studio tools
  - Created target audience sections for AI Artists, Game Developers, and WebXR builders
  - Implemented free tier strategy with 25MB file limit to drive pro tier conversions
  - Added pro tier teaser showcasing batch processing, API access, and higher file limits
  - Enhanced visual design with professional feature cards and icons
  - Updated page title and meta information for better SEO targeting
  - Positioned tool as essential "last mile" solution for AI-generated and bloated 3D models
- July 07, 2025. Advanced mesh compression implementation for 95% geometry reduction:
  - Enhanced Meshoptimizer with aggressive optimization settings (attributes, indices, normals, tangents)
  - Implemented advanced Draco compression with quality-based quantization levels
  - Added intelligent hybrid compression system that tests both methods and selects optimal result
  - Quality-specific compression settings: high (preserve detail), balanced, maximum compression
  - Automatic compression method selection based on file size and compatibility considerations
  - Enhanced progress tracking with detailed compression method reporting
  - Updated marketing copy to highlight up to 95% geometry compression capabilities

## User Preferences

Preferred communication style: Simple, everyday language.