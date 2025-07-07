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
- **Framework**: Flask (Python web framework)
- **Structure**: Modular design with separated concerns
  - `app.py`: Main Flask application with routing and file handling
  - `optimizer.py`: Core optimization logic using external tools
  - `main.py`: Application entry point
- **File Processing**: Asynchronous optimization with progress tracking
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
- **Problem**: Long-running optimization processes need user feedback
- **Solution**: Real-time progress updates with detailed step information
- **Implementation**: Thread-safe progress dictionary with polling mechanism

## Data Flow

1. **Upload Phase**: User selects GLB file → Frontend validates → Backend receives and stores
2. **Processing Phase**: Optimization starts in background thread → Progress updates sent to frontend
3. **Results Phase**: Optimized file generated → Statistics calculated → Download link provided
4. **Cleanup Phase**: Temporary files removed → User can start new optimization

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

## User Preferences

Preferred communication style: Simple, everyday language.