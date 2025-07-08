"""
User Analytics and Issue Tracking System
Comprehensive logging for user issues, site problems, and system monitoring
"""

import logging
import json
import traceback
from datetime import datetime, timezone
from functools import wraps
from flask import request, session, g
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, JSON, create_engine
from sqlalchemy.ext.declarative import declarative_base
from database import SessionLocal
import os

# Create base for our new models
Base = declarative_base()

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class UserIssueLog(Base):
    """Track user issues and problems encountered during site usage"""
    __tablename__ = 'user_issue_logs'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # User context
    session_id = Column(String(255), index=True)
    user_agent = Column(Text)
    ip_address = Column(String(45))  # IPv6 compatible
    
    # Issue details
    issue_type = Column(String(50), index=True)  # 'error', 'warning', 'performance', 'user_action'
    severity = Column(String(20), default='medium')  # 'low', 'medium', 'high', 'critical'
    component = Column(String(100), index=True)  # 'upload', '3d_viewer', 'optimization', 'download'
    
    # Error details
    error_message = Column(Text)
    error_code = Column(String(50))
    stack_trace = Column(Text)
    
    # Request context
    endpoint = Column(String(200))
    method = Column(String(10))
    url = Column(Text)
    
    # File processing context
    file_name = Column(String(255))
    file_size = Column(Integer)
    task_id = Column(String(255), index=True)
    
    # Performance metrics
    response_time_ms = Column(Float)
    memory_usage_mb = Column(Float)
    
    # Additional context
    browser_info = Column(JSON)
    form_data = Column(JSON)
    custom_data = Column(JSON)
    
    # Resolution tracking
    resolved = Column(Boolean, default=False)
    resolution_notes = Column(Text)

class UserSessionActivity(Base):
    """Track user session activity for pattern analysis"""
    __tablename__ = 'user_session_activity'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    session_id = Column(String(255), index=True)
    action = Column(String(100), index=True)  # 'page_view', 'file_upload', 'optimization_start', etc.
    details = Column(JSON)
    duration_ms = Column(Float)

class SystemHealthLog(Base):
    """Track system health and performance metrics"""
    __tablename__ = 'system_health_logs'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    metric_type = Column(String(50), index=True)  # 'cpu', 'memory', 'disk', 'database'
    value = Column(Float)
    unit = Column(String(20))
    status = Column(String(20))  # 'normal', 'warning', 'critical'
    details = Column(JSON)

class IssueTracker:
    """Centralized issue tracking and analytics"""
    
    def __init__(self):
        self.logger = logging.getLogger('user_analytics')
    
    def log_user_issue(self, issue_type, component, error_message=None, 
                      severity='medium', error_code=None, stack_trace=None,
                      file_name=None, file_size=None, task_id=None,
                      custom_data=None):
        """Log a user issue with comprehensive context"""
        try:
            # Get request context
            user_agent = request.headers.get('User-Agent', '') if request else ''
            ip_address = request.remote_addr if request else ''
            endpoint = request.endpoint if request else ''
            method = request.method if request else ''
            url = request.url if request else ''
            
            # Get session context
            session_id = session.get('session_id', '') if session else ''
            
            # Browser info extraction
            browser_info = self._extract_browser_info(user_agent)
            
            # Form data (sanitized)
            form_data = dict(request.form) if request and request.form else {}
            # Remove sensitive data
            sensitive_keys = ['password', 'secret', 'key', 'token']
            form_data = {k: '***REDACTED***' if any(sens in k.lower() for sens in sensitive_keys) else v 
                        for k, v in form_data.items()}
            
            # Create log entry
            issue_log = UserIssueLog(
                session_id=session_id,
                user_agent=user_agent,
                ip_address=ip_address,
                issue_type=issue_type,
                severity=severity,
                component=component,
                error_message=error_message,
                error_code=error_code,
                stack_trace=stack_trace,
                endpoint=endpoint,
                method=method,
                url=url,
                file_name=file_name,
                file_size=file_size,
                task_id=task_id,
                browser_info=browser_info,
                form_data=form_data,
                custom_data=custom_data or {}
            )
            
            # Create database session
            session_db = SessionLocal()
            try:
                session_db.add(issue_log)
                session_db.commit()
            except Exception as db_error:
                session_db.rollback()
                self.logger.error(f"Database commit failed: {str(db_error)}")
            finally:
                session_db.close()
            
            # Also log to file for backup
            self._log_to_file({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'issue_type': issue_type,
                'component': component,
                'severity': severity,
                'error_message': error_message,
                'session_id': session_id,
                'endpoint': endpoint,
                'file_name': file_name,
                'custom_data': custom_data
            })
            
        except Exception as e:
            # Fallback logging if database fails
            self.logger.error(f"Failed to log user issue: {str(e)}")
            self._log_to_file({
                'error': 'Failed to log to database',
                'original_issue': error_message,
                'database_error': str(e)
            })
    
    def log_user_action(self, action, details=None, duration_ms=None):
        """Log user actions for behavior analysis"""
        try:
            session_id = session.get('session_id', '') if session else ''
            
            activity = UserSessionActivity(
                session_id=session_id,
                action=action,
                details=details or {},
                duration_ms=duration_ms
            )
            
            session_db = SessionLocal()
            try:
                session_db.add(activity)
                session_db.commit()
            except Exception as db_error:
                session_db.rollback()
                self.logger.error(f"Database commit failed: {str(db_error)}")
            finally:
                session_db.close()
            
        except Exception as e:
            self.logger.error(f"Failed to log user action: {str(e)}")
    
    def log_system_health(self, metric_type, value, unit, status='normal', details=None):
        """Log system health metrics"""
        try:
            health_log = SystemHealthLog(
                metric_type=metric_type,
                value=value,
                unit=unit,
                status=status,
                details=details or {}
            )
            
            session_db = SessionLocal()
            try:
                session_db.add(health_log)
                session_db.commit()
            except Exception as db_error:
                session_db.rollback()
                self.logger.error(f"Database commit failed: {str(db_error)}")
            finally:
                session_db.close()
            
        except Exception as e:
            self.logger.error(f"Failed to log system health: {str(e)}")
    
    def _extract_browser_info(self, user_agent):
        """Extract browser information from user agent"""
        info = {'user_agent': user_agent}
        
        if 'Chrome' in user_agent:
            info['browser'] = 'Chrome'
        elif 'Firefox' in user_agent:
            info['browser'] = 'Firefox'
        elif 'Safari' in user_agent:
            info['browser'] = 'Safari'
        elif 'Edge' in user_agent:
            info['browser'] = 'Edge'
        else:
            info['browser'] = 'Unknown'
        
        if 'Mobile' in user_agent or 'iPhone' in user_agent or 'Android' in user_agent:
            info['device_type'] = 'mobile'
        elif 'Tablet' in user_agent or 'iPad' in user_agent:
            info['device_type'] = 'tablet'
        else:
            info['device_type'] = 'desktop'
        
        return info
    
    def _log_to_file(self, data):
        """Backup logging to file"""
        try:
            log_file = os.path.join(os.getcwd(), 'user_issues.log')
            with open(log_file, 'a') as f:
                f.write(json.dumps(data) + '\n')
        except Exception as e:
            self.logger.error(f"Failed to log to file: {str(e)}")
    
    def get_recent_issues(self, hours=24, severity=None, component=None):
        """Get recent issues for monitoring"""
        from datetime import timedelta
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        session_db = SessionLocal()
        try:
            query = session_db.query(UserIssueLog).filter(UserIssueLog.timestamp >= cutoff_time)
            
            if severity:
                query = query.filter(UserIssueLog.severity == severity)
            if component:
                query = query.filter(UserIssueLog.component == component)
            
            return query.order_by(UserIssueLog.timestamp.desc()).all()
        finally:
            session_db.close()
    
    def get_issue_summary(self, hours=24):
        """Get summary of issues for dashboard"""
        from sqlalchemy import func
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        session_db = SessionLocal()
        try:
            # Count by severity
            severity_counts = session_db.query(
                UserIssueLog.severity,
                func.count(UserIssueLog.id).label('count')
            ).filter(
                UserIssueLog.timestamp >= cutoff_time
            ).group_by(UserIssueLog.severity).all()
            
            # Count by component
            component_counts = session_db.query(
                UserIssueLog.component,
                func.count(UserIssueLog.id).label('count')
            ).filter(
                UserIssueLog.timestamp >= cutoff_time
            ).group_by(UserIssueLog.component).all()
        finally:
            session_db.close()
        
        return {
            'severity_breakdown': {item.severity: item.count for item in severity_counts},
            'component_breakdown': {item.component: item.count for item in component_counts},
            'total_issues': sum(item.count for item in severity_counts)
        }

# Global issue tracker instance
issue_tracker = IssueTracker()

def track_errors(component):
    """Decorator to automatically track errors in functions"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            try:
                result = func(*args, **kwargs)
                
                # Log successful completion
                duration = (datetime.now() - start_time).total_seconds() * 1000
                issue_tracker.log_user_action(
                    action=f"{component}_{func.__name__}_success",
                    duration_ms=duration
                )
                
                return result
                
            except Exception as e:
                # Log the error
                duration = (datetime.now() - start_time).total_seconds() * 1000
                issue_tracker.log_user_issue(
                    issue_type='error',
                    component=component,
                    error_message=str(e),
                    severity='high',
                    stack_trace=traceback.format_exc(),
                    custom_data={
                        'function': func.__name__,
                        'duration_ms': duration
                    }
                )
                raise
        return wrapper
    return decorator

def track_performance(component, threshold_ms=1000):
    """Decorator to track performance issues"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            result = func(*args, **kwargs)
            duration = (datetime.now() - start_time).total_seconds() * 1000
            
            if duration > threshold_ms:
                issue_tracker.log_user_issue(
                    issue_type='performance',
                    component=component,
                    error_message=f"Slow performance: {duration:.2f}ms (threshold: {threshold_ms}ms)",
                    severity='medium',
                    custom_data={
                        'function': func.__name__,
                        'duration_ms': duration,
                        'threshold_ms': threshold_ms
                    }
                )
            
            return result
        return wrapper
    return decorator