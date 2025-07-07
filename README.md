# GLB Optimizer - Production-Ready GLB File Optimization

A scalable web application for optimizing GLB (3D model) files using industry-standard tools and workflows. Achieves 5-10× compression while maintaining visual fidelity.

## Features

### Core Optimization Pipeline
- **6-Step Industry-Standard Workflow**: Cleanup → Geometry Compression → Texture Compression → Animation Optimization → LOD Generation → Final Assembly
- **Advanced Compression**: EXT_meshopt_compression, KTX2/BasisU textures, Draco fallback
- **Smart Fallbacks**: Graceful degradation when advanced features aren't supported
- **Quality Settings**: High Quality, Balanced, and Maximum Compression modes

### Production Architecture
- **Scalable Task Queue**: Redis + Celery for handling multiple concurrent optimizations
- **Resource Management**: Controlled concurrency to prevent server overload
- **Real-time Progress**: Live optimization progress updates via WebSocket-like polling
- **Automatic Cleanup**: Smart file and task cleanup to prevent storage bloat

### User Experience
- **Drag & Drop Interface**: Modern, intuitive file upload
- **Configuration Panel**: User-controllable optimization settings
- **Progress Tracking**: Real-time feedback with detailed step information
- **Statistics Dashboard**: Compression ratios, processing times, file size comparisons

## Technical Stack

### Backend
- **Flask**: Web framework with RESTful API design
- **Celery**: Distributed task queue for background processing
- **Redis**: Message broker and result backend
- **gltf-transform v4.2.0**: Industry-standard GLB processing toolkit
- **gltfpack v0.24.0**: Meshoptimizer-based compression

### Frontend
- **Vanilla JavaScript**: Lightweight, framework-free implementation
- **Bootstrap 5**: Responsive dark theme UI
- **Font Awesome**: Professional iconography

## Quick Start

### Standard Mode (Replit)
The application automatically starts Redis and Celery worker:

```bash
# Run the application (starts everything automatically)
python main.py
```

### Production Mode
For production deployments with full control:

```bash
# Start all services with monitoring
python run_production.py
```

### Manual Setup
If you need to start services individually:

```bash
# 1. Start Redis
redis-server --port 6379 --daemonize yes

# 2. Start Celery worker
celery -A celery_app worker --loglevel=info --concurrency=1 --queues=optimization

# 3. Start Flask application
gunicorn --bind 0.0.0.0:5000 main:app
```

## Architecture Overview

### Task Queue Design
```
User Upload → Flask API → Redis Queue → Celery Worker → Optimization Pipeline
     ↓             ↓           ↓            ↓               ↓
File Storage → Task Created → Task Queued → Processing → Results Stored
     ↓             ↓           ↓            ↓               ↓
Progress UI ← Status API ← Task State ← Progress Updates ← File Output
```

### Resource Management
- **Concurrency Control**: Only 1 optimization at a time to prevent resource exhaustion
- **Memory Management**: Worker restarts after 10 tasks to prevent memory leaks
- **Storage Cleanup**: Automatic cleanup of temporary and result files
- **Task Expiration**: Results expire after 1 hour to prevent Redis bloat

## Optimization Workflow

### Step 1: Cleanup & Deduplication
- Prune unused meshes, nodes, and vertex attributes
- Weld vertices with tolerance-based merging
- Join compatible meshes to reduce draw calls

### Step 2: Geometry Compression
- Primary: EXT_meshopt_compression with 8/10-bit quantization
- Fallback: Draco compression with edgebreaker method
- Optional: Polygon simplification (user-configurable)

### Step 3: Texture Compression
- High-quality KTX2/BasisU compression (--q 255)
- UASTC for normal maps, ETC1S for albedo/ORM
- Channel packing for roughness/metallic/occlusion

### Step 4: Animation Optimization
- Resample to 30fps for consistency
- 16-bit quantization for keyframes
- Remove redundant animation data

### Step 5: LOD Generation
- 3 levels of detail with 50% scaling per level
- Progressive delivery support
- Distance-based mesh selection

### Step 6: Final Assembly
- Embed all textures
- Apply final minification
- Generate progressive delivery metadata

## Configuration

### Environment Variables
```bash
REDIS_URL=redis://localhost:6379/0  # Redis connection string
SESSION_SECRET=your-secret-key       # Flask session secret
```

### Quality Levels
- **High Quality**: Maximum visual fidelity with efficient compression
- **Balanced**: Good balance between quality and file size
- **Maximum Compression**: Prioritizes smallest possible file size

## Monitoring & Troubleshooting

### Task Monitoring
```bash
# Monitor Celery worker status
celery -A celery_app inspect active

# Check Redis task queue
redis-cli LLEN optimization

# View worker logs
celery -A celery_app events
```

### Common Issues
1. **Redis Connection**: Ensure Redis is running on port 6379
2. **Worker Not Starting**: Check Celery configuration and Redis connectivity
3. **Optimization Failures**: Verify gltf-transform and gltfpack are installed
4. **Memory Issues**: Monitor worker memory usage, consider reducing concurrency

## Scaling Considerations

### Horizontal Scaling
- Add more Celery workers on separate machines
- Use Redis Cluster for high availability
- Load balance Flask instances behind nginx

### Vertical Scaling
- Increase worker concurrency for more parallel optimizations
- Add more memory for larger GLB file processing
- Use faster storage for temporary file operations

## Security

### File Upload Security
- GLB file type validation
- 100MB file size limit
- Secure filename sanitization
- Temporary file cleanup

### Production Hardening
- Use environment variables for secrets
- Enable HTTPS in production
- Implement rate limiting
- Add authentication if needed

## License

This project implements industry-standard GLB optimization workflows based on:
- [glTF Transform](https://gltf-transform.dev/) - Apache 2.0
- [meshoptimizer](https://meshoptimizer.org/) - MIT License
- [KTX-Software](https://github.com/KhronosGroup/KTX-Software) - Various licenses

## Support

For technical issues or optimization questions:
1. Check the troubleshooting section above
2. Review Celery and Redis logs
3. Verify GLB file format compatibility
4. Test with smaller files first