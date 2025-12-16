# GLB Optimizer - Production Docker Image
# Multi-stage build for optimized image size

FROM python:3.11-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20.x (required for gltf-transform)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install gltf-transform and gltfpack globally
RUN npm install -g @gltf-transform/cli

# Install gltfpack (meshoptimizer) - download pre-built binary
RUN curl -L https://github.com/zeux/meshoptimizer/releases/download/v0.21/gltfpack-linux-x64 -o /usr/local/bin/gltfpack \
    && chmod +x /usr/local/bin/gltfpack

# Set working directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml ./

# Install Python dependencies using pip with pyproject.toml
RUN pip install --no-cache-dir .

# Copy application code
COPY . .

# Create required directories
RUN mkdir -p uploads output logs

# Set proper permissions
RUN chmod 755 uploads output logs

# Environment variables
ENV FLASK_APP=wsgi:app
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Expose port
EXPOSE 5000

# Default command - run with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "300", "wsgi:app"]
