from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class OptimizationTask(Base):
    """Track GLB optimization tasks and their progress"""
    __tablename__ = 'optimization_tasks'
    
    id = Column(String, primary_key=True)  # Celery task ID
    original_filename = Column(String(255), nullable=False)
    secure_filename = Column(String(255), nullable=False)
    
    # File information
    original_size = Column(Integer, nullable=True)
    compressed_size = Column(Integer, nullable=True)
    compression_ratio = Column(Float, nullable=True)
    
    # Optimization settings
    quality_level = Column(String(50), nullable=False, default='high')
    enable_lod = Column(Boolean, nullable=False, default=True)
    enable_simplification = Column(Boolean, nullable=False, default=True)
    
    # Task status
    status = Column(String(50), nullable=False, default='pending')  # pending, processing, completed, failed
    progress = Column(Integer, nullable=False, default=0)
    current_step = Column(String(100), nullable=True)
    
    # Performance metrics
    processing_time = Column(Float, nullable=True)
    estimated_memory_savings = Column(Float, nullable=True)
    performance_metrics = Column(JSON, nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    error_logs = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # File cleanup
    files_cleaned = Column(Boolean, nullable=False, default=False)
    cleanup_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f'<OptimizationTask {self.id}: {self.original_filename} ({self.status})>'


class PerformanceMetric(Base):
    """Track performance metrics for analytics and improvement"""
    __tablename__ = 'performance_metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey('optimization_tasks.id'), nullable=False)
    
    # File characteristics
    original_size_mb = Column(Float, nullable=False)
    compressed_size_mb = Column(Float, nullable=False)
    compression_ratio = Column(Float, nullable=False)
    
    # Performance gains
    load_time_improvement = Column(Float, nullable=True)
    bandwidth_savings = Column(Float, nullable=True)
    gpu_memory_savings = Column(Float, nullable=True)
    
    # Processing performance
    processing_time_seconds = Column(Float, nullable=False)
    quality_level = Column(String(50), nullable=False)
    optimization_methods = Column(JSON, nullable=True)
    
    # Web game readiness
    mobile_friendly = Column(Boolean, nullable=False, default=False)
    web_optimized = Column(Boolean, nullable=False, default=False)
    streaming_ready = Column(Boolean, nullable=False, default=False)
    
    # Success metrics
    optimization_successful = Column(Boolean, nullable=False, default=False)
    user_downloaded = Column(Boolean, nullable=False, default=False)
    
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    
    # Relationship
    task = relationship("OptimizationTask", backref="metrics")
    
    def __repr__(self):
        return f'<PerformanceMetric {self.id}: {self.original_size_mb}MB → {self.compressed_size_mb}MB>'


class UserSession(Base):
    """Track user sessions for analytics and rate limiting"""
    __tablename__ = 'user_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), nullable=False, unique=True)
    
    # Usage tracking
    total_uploads = Column(Integer, nullable=False, default=0)
    total_optimizations = Column(Integer, nullable=False, default=0)
    total_downloads = Column(Integer, nullable=False, default=0)
    
    # File size tracking
    total_original_size = Column(Integer, nullable=False, default=0)
    total_compressed_size = Column(Integer, nullable=False, default=0)
    total_savings = Column(Integer, nullable=False, default=0)
    
    # Rate limiting
    last_upload_at = Column(DateTime, nullable=True)
    uploads_today = Column(Integer, nullable=False, default=0)
    last_reset_date = Column(DateTime, nullable=True)
    
    # User experience
    preferred_quality = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<UserSession {self.session_id}: {self.total_optimizations} optimizations>'


class SystemMetric(Base):
    """Track system-wide metrics for monitoring and scaling"""
    __tablename__ = 'system_metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Performance tracking
    total_tasks_processed = Column(Integer, nullable=False, default=0)
    total_files_optimized = Column(Integer, nullable=False, default=0)
    total_size_savings_mb = Column(Float, nullable=False, default=0.0)
    
    # System health
    average_processing_time = Column(Float, nullable=True)
    success_rate = Column(Float, nullable=True)
    error_rate = Column(Float, nullable=True)
    
    # Resource usage
    peak_memory_usage = Column(Integer, nullable=True)
    disk_usage_mb = Column(Float, nullable=True)
    active_tasks = Column(Integer, nullable=False, default=0)
    
    # Quality distribution
    high_quality_tasks = Column(Integer, nullable=False, default=0)
    balanced_tasks = Column(Integer, nullable=False, default=0)
    max_compression_tasks = Column(Integer, nullable=False, default=0)
    
    recorded_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<SystemMetric {self.recorded_at}: {self.total_tasks_processed} tasks>'