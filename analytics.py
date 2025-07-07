"""
Analytics module for GLB Optimizer
Provides database-driven insights and performance monitoring
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy import func, desc
from database import SessionLocal
from models import OptimizationTask, PerformanceMetric, UserSession, SystemMetric

class AnalyticsManager:
    """Analytics and reporting for GLB optimization service"""
    
    def __init__(self):
        self.db = SessionLocal()
    
    def close(self):
        """Close database connection"""
        self.db.close()
    
    def get_summary_stats(self, days=30):
        """Get high-level summary statistics"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Total tasks processed
        total_tasks = self.db.query(OptimizationTask).filter(
            OptimizationTask.created_at >= cutoff_date
        ).count()
        
        # Successful optimizations
        successful_tasks = self.db.query(OptimizationTask).filter(
            OptimizationTask.created_at >= cutoff_date,
            OptimizationTask.status == 'completed'
        ).count()
        
        # Total file size savings
        size_savings = self.db.query(
            func.sum(OptimizationTask.original_size - OptimizationTask.compressed_size)
        ).filter(
            OptimizationTask.created_at >= cutoff_date,
            OptimizationTask.status == 'completed'
        ).scalar() or 0
        
        # Average compression ratio
        avg_compression = self.db.query(
            func.avg(OptimizationTask.compression_ratio)
        ).filter(
            OptimizationTask.created_at >= cutoff_date,
            OptimizationTask.status == 'completed'
        ).scalar() or 0
        
        # Average processing time
        avg_processing_time = self.db.query(
            func.avg(OptimizationTask.processing_time)
        ).filter(
            OptimizationTask.created_at >= cutoff_date,
            OptimizationTask.status == 'completed'
        ).scalar() or 0
        
        return {
            'total_tasks': total_tasks,
            'successful_tasks': successful_tasks,
            'success_rate': (successful_tasks / total_tasks * 100) if total_tasks > 0 else 0,
            'total_size_savings_mb': size_savings / (1024 * 1024) if size_savings else 0,
            'average_compression_ratio': float(avg_compression) if avg_compression else 0,
            'average_processing_time': float(avg_processing_time) if avg_processing_time else 0,
            'period_days': days
        }
    
    def get_quality_level_distribution(self, days=30):
        """Get distribution of quality levels used"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        quality_stats = self.db.query(
            OptimizationTask.quality_level,
            func.count(OptimizationTask.id).label('count'),
            func.avg(OptimizationTask.compression_ratio).label('avg_compression')
        ).filter(
            OptimizationTask.created_at >= cutoff_date,
            OptimizationTask.status == 'completed'
        ).group_by(OptimizationTask.quality_level).all()
        
        return [
            {
                'quality_level': stat.quality_level,
                'count': stat.count,
                'avg_compression_ratio': float(stat.avg_compression) if stat.avg_compression else 0
            }
            for stat in quality_stats
        ]
    
    def get_recent_performance_trends(self, days=7):
        """Get performance trends over recent days"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        daily_stats = self.db.query(
            func.date(OptimizationTask.created_at).label('date'),
            func.count(OptimizationTask.id).label('total_tasks'),
            func.count(
                func.nullif(OptimizationTask.status != 'completed', True)
            ).label('completed_tasks'),
            func.avg(OptimizationTask.compression_ratio).label('avg_compression'),
            func.avg(OptimizationTask.processing_time).label('avg_processing_time')
        ).filter(
            OptimizationTask.created_at >= cutoff_date
        ).group_by(
            func.date(OptimizationTask.created_at)
        ).order_by(func.date(OptimizationTask.created_at)).all()
        
        return [
            {
                'date': stat.date.isoformat() if stat.date else None,
                'total_tasks': stat.total_tasks,
                'completed_tasks': stat.completed_tasks or 0,
                'success_rate': (stat.completed_tasks / stat.total_tasks * 100) if stat.total_tasks > 0 else 0,
                'avg_compression_ratio': float(stat.avg_compression) if stat.avg_compression else 0,
                'avg_processing_time': float(stat.avg_processing_time) if stat.avg_processing_time else 0
            }
            for stat in daily_stats
        ]
    
    def get_web_game_readiness_stats(self, days=30):
        """Get web game readiness statistics"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Get web game readiness statistics with proper boolean handling
        total_count = self.db.query(PerformanceMetric).filter(PerformanceMetric.created_at >= cutoff_date).count()
        mobile_count = self.db.query(PerformanceMetric).filter(
            PerformanceMetric.created_at >= cutoff_date,
            PerformanceMetric.mobile_friendly == True
        ).count()
        web_count = self.db.query(PerformanceMetric).filter(
            PerformanceMetric.created_at >= cutoff_date,
            PerformanceMetric.web_optimized == True
        ).count()
        streaming_count = self.db.query(PerformanceMetric).filter(
            PerformanceMetric.created_at >= cutoff_date,
            PerformanceMetric.streaming_ready == True
        ).count()
        
        readiness_stats = {
            'total': total_count,
            'mobile_friendly': mobile_count,
            'web_optimized': web_count,
            'streaming_ready': streaming_count
        }
        
        if not readiness_stats or readiness_stats['total'] == 0:
            return {
                'mobile_friendly_rate': 0,
                'web_optimized_rate': 0,
                'streaming_ready_rate': 0,
                'total_analyzed': 0
            }
        
        return {
            'mobile_friendly_rate': (readiness_stats['mobile_friendly'] / readiness_stats['total'] * 100),
            'web_optimized_rate': (readiness_stats['web_optimized'] / readiness_stats['total'] * 100),
            'streaming_ready_rate': (readiness_stats['streaming_ready'] / readiness_stats['total'] * 100),
            'total_analyzed': readiness_stats['total']
        }
    
    def get_user_activity_summary(self, days=30):
        """Get user activity summary"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Active users (users who uploaded in the period)
        active_users = self.db.query(UserSession).filter(
            UserSession.last_upload_at >= cutoff_date
        ).count()
        
        # Total sessions
        total_sessions = self.db.query(UserSession).count()
        
        # Average uploads per user
        avg_uploads = self.db.query(
            func.avg(UserSession.total_uploads)
        ).scalar() or 0
        
        return {
            'active_users': active_users,
            'total_sessions': total_sessions,
            'average_uploads_per_user': float(avg_uploads),
            'period_days': days
        }
    
    def generate_comprehensive_report(self):
        """Generate a comprehensive analytics report"""
        try:
            report = {
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'summary_stats': self.get_summary_stats(30),
                'quality_distribution': self.get_quality_level_distribution(30),
                'performance_trends': self.get_recent_performance_trends(7),
                'web_game_readiness': self.get_web_game_readiness_stats(30),
                'user_activity': self.get_user_activity_summary(30)
            }
            return report
        except Exception as e:
            return {'error': f'Failed to generate report: {str(e)}'}
        finally:
            self.close()

def get_analytics_dashboard_data():
    """Helper function to get dashboard data"""
    analytics = AnalyticsManager()
    return analytics.generate_comprehensive_report()