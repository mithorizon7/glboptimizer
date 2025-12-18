# GLB Optimizer

## Overview
This project is a web-based GLB (3D model) file optimization tool designed to significantly reduce file sizes (5-10x) while preserving visual quality. It targets AI artists, game developers, and WebXR builders, offering a professional-grade solution for optimizing 3D models for web and real-time applications. The tool provides a user-friendly interface for uploading, processing, and downloading optimized GLB files, aiming to be the "last mile" solution for AI-generated and bloated 3D models.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend
The frontend uses Vanilla JavaScript with Bootstrap 5 (dark theme) to provide a responsive single-page application. It features a drag-and-drop upload, real-time progress tracking, and a results display with compression statistics. A key feature is a side-by-side 3D model comparison viewer using Three.js (r178) with interactive controls and support for advanced compression decoders (Meshopt, DRACO, KTX2/Basis Universal, WebP).

### Backend
The backend is built with Flask and uses Celery (backed by Redis or PostgreSQL) for asynchronous background task processing. It employs a modular design with separated concerns for routing, optimization logic, and task management. The core optimization engine utilizes a 7-stage modular pipeline (inspect, prune, weld, geometry, textures, animations, finalize) with intelligent model analysis for conditional stage execution and per-stage error recovery. Security is a priority, with multi-layer file validation, secure filename handling, file size limits (up to 100MB), and comprehensive protection against command injection and TOCTOU attacks. Atomic file operations and robust temporary file management ensure data integrity and cleanup.

### Key Architectural Patterns (Dec 2025)
- **Single Celery Factory**: `celery_factory.py` is the sole source of truth for Celery initialization with graceful degradation (Redis → Synchronous execution)
- **Centralized Configuration**: `config.py` contains all configuration defaults; no `os.environ.get()` with defaults elsewhere
- **Database Session Management**: `database.py` provides `db_session()` context manager for automatic session cleanup and rollback on errors
- **Synchronous Fallback**: When Redis is unavailable, tasks execute synchronously instead of queuing to Celery. This ensures file uploads always work regardless of message broker availability.
- **Database-Based Task Tracking**: Task progress is tracked via the OptimizationTask database model, avoiding dependency on Celery's result backend. The `/progress/<task_id>` endpoint queries the database directly.
- **No Celery Result Backend Dependency**: When using database broker mode, the result backend is disabled (`result_backend=None`) to avoid Redis fallback issues. All task state is stored in PostgreSQL.

### UI/UX Decisions
The application prioritizes a clean, dark-themed interface with clear navigation and visual feedback. User guidance is provided through interactive tooltips and expandable help sections explaining optimization techniques in simple language. The 3D viewer is designed for intuitive comparison, with default camera syncing and enhanced lighting. Marketing-focused design elements highlight the tool's benefits and encourage pro-tier conversions.

### Technical Implementations
- **Optimization Pipeline**: Orchestrated 6-step workflow (Cleanup, Mesh Processing, Geometry Compression, Texture Compression, Animation Optimization, Final Assembly) using industry-standard tools.
- **Parallel Processing**: Utilizes `ProcessPoolExecutor` for true parallel compression, intelligently selecting methods (meshopt, draco, hybrid) and managing timeouts.
- **Configuration**: Centralized, environment-based configuration via `GLB_*` environment variables and optional JSON files, allowing dynamic adjustment of quality presets and thresholds.
- **Logging**: Structured logging with detailed error categorization, security violation reporting, and JSON export for API integration.
- **Path Handling**: Achieved 100% `pathlib.Path` consistency for robust, cross-platform file operations with enhanced security against path traversal and symlink attacks.
- **GLB Validation**: Memory-efficient GLB header and format validation reading only necessary bytes for large files.
- **Resource Management**: Temporary files are managed with context managers and `atexit` registration for guaranteed cleanup.

## External Dependencies

- **Node.js Tools**:
    - **@gltf-transform/cli v4.2.0**: For pruning, welding, joining, texture compression (KTX2/BasisU).
    - **gltfpack v0.24.0**: For Meshoptimizer-based geometry compression and polygon simplification.
    - **ktx-tools**: For KTX2/Basis Universal texture compression.
    - **webp**: For WebP texture compression.

- **Python Libraries**:
    - **Flask**: Web framework.
    - **Celery**: Asynchronous task queue.
    - **Redis**: Celery broker/backend.
    - **SQLAlchemy**: ORM for database interaction (PostgreSQL).
    - **Werkzeug**: WSGI utilities.
    - **subprocess**: For executing external tools.
    - **pathlib**: For robust path manipulation.

- **Frontend Libraries**:
    - **Bootstrap 5**: CSS framework (dark theme).
    - **Font Awesome 6.4.0**: Icon library.
    - **Three.js r178**: 3D rendering library.
    - **Three.js GLTFLoader and Decoders**: For displaying GLB models with compression (Meshopt, DRACO, KTX2/Basis Universal).

- **Databases**:
    - **PostgreSQL**: Primary database for task tracking, performance metrics, user sessions, and system analytics.
    - **Redis**: Used as a Celery broker/backend (with PostgreSQL fallback).

- **Object Storage**:
    - **AWS S3, Google Cloud Storage, Azure Blob Storage**: Multi-provider support with local filesystem fallback for storing original and optimized GLB files.