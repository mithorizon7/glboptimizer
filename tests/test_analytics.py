# tests/test_analytics.py
"""
Unit tests for analytics functionality
Tests data analysis and reporting features
"""
import pytest
from datetime import datetime, timezone, timedelta
from analytics import AnalyticsManager
from models import OptimizationTask, PerformanceMetric, UserSession, SystemMetric

class TestAnalyticsManager:
    """Test suite for AnalyticsManager"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.analytics = AnalyticsManager()
    
    def teardown_method(self):
        """Clean up after tests"""
        self.analytics.close()
    
    def test_get_summary_stats_with_data(self, db_session):
        """Test summary statistics calculation with sample data"""
        # Create sample optimization tasks
        now = datetime.now(timezone.utc)
        tasks = [
            OptimizationTask(
                id=f'task_{i}',
                original_filename=f'model_{i}.glb',
                secure_filename=f'model_{i}_secure.glb',
                original_size=1000000 + i * 100000,
                compressed_size=400000 + i * 50000,
                compression_ratio=0.6 - i * 0.05,
                quality_level='high',
                status='completed',
                progress=100,
                processing_time=30.0 + i * 5,
                created_at=now - timedelta(days=i)
            )
            for i in range(5)
        ]
        
        for task in tasks:
            db_session.add(task)
        db_session.commit()
        
        # Get summary stats
        stats = self.analytics.get_summary_stats(days=30)
        
        # Verify calculations
        assert stats['total_tasks'] == 5
        assert stats['completed_tasks'] == 5
        assert stats['success_rate'] == 100.0
        assert stats['total_original_size_mb'] > 0
        assert stats['total_compressed_size_mb'] > 0
        assert stats['average_compression_ratio'] > 0
        assert stats['average_processing_time'] > 0
    
    def test_get_summary_stats_empty_database(self, db_session):
        """Test summary statistics with empty database"""
        stats = self.analytics.get_summary_stats(days=30)
        
        # Verify default values for empty database
        assert stats['total_tasks'] == 0
        assert stats['completed_tasks'] == 0
        assert stats['success_rate'] == 0.0
        assert stats['total_original_size_mb'] == 0.0
        assert stats['total_compressed_size_mb'] == 0.0
        assert stats['average_compression_ratio'] == 0.0
        assert stats['average_processing_time'] == 0.0
    
    def test_get_quality_level_distribution(self, db_session):
        """Test quality level distribution analysis"""
        # Create tasks with different quality levels
        quality_data = [
            ('high', 10),
            ('balanced', 15),
            ('maximum_compression', 5)
        ]
        
        task_id = 0
        for quality, count in quality_data:
            for i in range(count):
                task = OptimizationTask(
                    id=f'quality_task_{task_id}',
                    original_filename=f'model_{task_id}.glb',
                    secure_filename=f'model_{task_id}_secure.glb',
                    quality_level=quality,
                    status='completed'
                )
                db_session.add(task)
                task_id += 1
        
        db_session.commit()
        
        # Get quality distribution
        distribution = self.analytics.get_quality_level_distribution(days=30)
        
        # Verify distribution calculations
        total_tasks = sum(count for _, count in quality_data)
        
        for quality, expected_count in quality_data:
            assert quality in distribution
            assert distribution[quality]['count'] == expected_count
            expected_percentage = (expected_count / total_tasks) * 100
            assert abs(distribution[quality]['percentage'] - expected_percentage) < 0.1
    
    def test_get_recent_performance_trends(self, db_session):
        """Test performance trends analysis"""
        # Create tasks over multiple days
        base_date = datetime.now(timezone.utc) - timedelta(days=7)
        
        for day in range(7):
            task_date = base_date + timedelta(days=day)
            
            # Create 2-3 tasks per day with varying performance
            for i in range(2 + day % 2):
                task = OptimizationTask(
                    id=f'trend_task_{day}_{i}',
                    original_filename=f'model_{day}_{i}.glb',
                    secure_filename=f'model_{day}_{i}_secure.glb',
                    original_size=1000000,
                    compressed_size=400000 + day * 10000,  # Varying compression
                    compression_ratio=0.6 - day * 0.01,   # Decreasing ratio
                    processing_time=30.0 + day * 2,       # Increasing time
                    status='completed',
                    created_at=task_date
                )
                db_session.add(task)
        
        db_session.commit()
        
        # Get performance trends
        trends = self.analytics.get_recent_performance_trends(days=7)
        
        # Verify trends data structure
        assert len(trends) <= 7  # Should have at most 7 days of data
        
        for day_data in trends:
            assert 'date' in day_data
            assert 'total_tasks' in day_data
            assert 'completed_tasks' in day_data
            assert 'success_rate' in day_data
            assert 'avg_compression_ratio' in day_data
            assert 'avg_processing_time' in day_data
            
            # Verify data consistency
            assert day_data['total_tasks'] >= day_data['completed_tasks']
            assert 0 <= day_data['success_rate'] <= 100
    
    def test_get_web_game_readiness_stats(self, db_session):
        """Test web game readiness statistics"""
        # Create performance metrics with different readiness indicators
        metrics_data = [
            (True, True, True),   # Mobile, web, streaming ready
            (True, True, False),  # Mobile and web ready
            (False, True, True),  # Web and streaming ready
            (True, False, False), # Only mobile ready
            (False, False, False) # Not ready for any
        ]
        
        for i, (mobile, web, streaming) in enumerate(metrics_data):
            task = OptimizationTask(
                id=f'readiness_task_{i}',
                original_filename=f'model_{i}.glb',
                secure_filename=f'model_{i}_secure.glb',
                status='completed'
            )
            db_session.add(task)
            
            metric = PerformanceMetric(
                task_id=f'readiness_task_{i}',
                original_size_mb=10.0,
                compressed_size_mb=4.0,
                compression_ratio=60.0,
                processing_time_seconds=30.0,
                quality_level='high',
                mobile_friendly=mobile,
                web_optimized=web,
                streaming_ready=streaming,
                optimization_successful=True
            )
            db_session.add(metric)
        
        db_session.commit()
        
        # Get readiness stats
        stats = self.analytics.get_web_game_readiness_stats(days=30)
        
        # Verify readiness calculations
        total_metrics = len(metrics_data)
        
        mobile_ready = sum(1 for mobile, _, _ in metrics_data if mobile)
        web_ready = sum(1 for _, web, _ in metrics_data if web)
        streaming_ready = sum(1 for _, _, streaming in metrics_data if streaming)
        
        assert stats['mobile_friendly_count'] == mobile_ready
        assert stats['web_optimized_count'] == web_ready
        assert stats['streaming_ready_count'] == streaming_ready
        
        # Verify percentages
        assert abs(stats['mobile_friendly_percentage'] - (mobile_ready / total_metrics * 100)) < 0.1
        assert abs(stats['web_optimized_percentage'] - (web_ready / total_metrics * 100)) < 0.1
        assert abs(stats['streaming_ready_percentage'] - (streaming_ready / total_metrics * 100)) < 0.1
    
    def test_get_user_activity_summary(self, db_session):
        """Test user activity summary analysis"""
        # Create sample user sessions
        sessions = [
            UserSession(
                session_id=f'user_session_{i}',
                total_uploads=5 + i,
                total_optimizations=4 + i,
                total_downloads=3 + i,
                total_original_size=5000000 + i * 1000000,
                total_compressed_size=2000000 + i * 400000,
                total_savings=3000000 + i * 600000,
                created_at=datetime.now(timezone.utc) - timedelta(days=i)
            )
            for i in range(3)
        ]
        
        for session in sessions:
            db_session.add(session)
        db_session.commit()
        
        # Get user activity summary
        summary = self.analytics.get_user_activity_summary(days=30)
        
        # Verify summary calculations
        assert summary['total_users'] == 3
        assert summary['total_uploads'] == sum(s.total_uploads for s in sessions)
        assert summary['total_optimizations'] == sum(s.total_optimizations for s in sessions)
        assert summary['total_downloads'] == sum(s.total_downloads for s in sessions)
        assert summary['average_uploads_per_user'] > 0
        assert summary['average_optimizations_per_user'] > 0
        assert summary['total_data_processed_mb'] > 0
        assert summary['total_savings_mb'] > 0
    
    def test_generate_comprehensive_report(self, db_session):
        """Test comprehensive analytics report generation"""
        # Create minimal sample data
        task = OptimizationTask(
            id='report_task_1',
            original_filename='report_model.glb',
            secure_filename='report_model_secure.glb',
            original_size=2000000,
            compressed_size=800000,
            compression_ratio=0.6,
            quality_level='high',
            status='completed',
            processing_time=25.5
        )
        db_session.add(task)
        
        user_session = UserSession(
            session_id='report_user_1',
            total_uploads=3,
            total_optimizations=2,
            total_downloads=2
        )
        db_session.add(user_session)
        
        db_session.commit()
        
        # Generate comprehensive report
        report = self.analytics.generate_comprehensive_report()
        
        # Verify report structure
        required_sections = [
            'summary_stats',
            'quality_distribution',
            'performance_trends',
            'web_game_readiness',
            'user_activity',
            'report_metadata'
        ]
        
        for section in required_sections:
            assert section in report
        
        # Verify metadata
        assert 'generated_at' in report['report_metadata']
        assert 'total_data_points' in report['report_metadata']
        assert report['report_metadata']['total_data_points'] > 0
    
    def test_analytics_with_date_filtering(self, db_session):
        """Test analytics respect date filtering"""
        # Create tasks from different time periods
        now = datetime.now(timezone.utc)
        
        # Recent task (within 7 days)
        recent_task = OptimizationTask(
            id='recent_task',
            original_filename='recent_model.glb',
            secure_filename='recent_model_secure.glb',
            status='completed',
            created_at=now - timedelta(days=3)
        )
        db_session.add(recent_task)
        
        # Old task (beyond 7 days)
        old_task = OptimizationTask(
            id='old_task',
            original_filename='old_model.glb',
            secure_filename='old_model_secure.glb',
            status='completed',
            created_at=now - timedelta(days=15)
        )
        db_session.add(old_task)
        
        db_session.commit()
        
        # Test with 7-day filter
        stats_7_days = self.analytics.get_summary_stats(days=7)
        stats_30_days = self.analytics.get_summary_stats(days=30)
        
        # 7-day stats should only include recent task
        assert stats_7_days['total_tasks'] == 1
        
        # 30-day stats should include both tasks
        assert stats_30_days['total_tasks'] == 2