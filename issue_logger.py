"""
Simple but comprehensive issue logging system for GLB Optimizer
Tracks user problems, errors, and site issues for debugging and improvements
"""

import logging
import json
import traceback
from datetime import datetime, timezone
from functools import wraps
from flask import request, session
import os

# Configure structured logging
logger = logging.getLogger('issue_tracker')

class IssueLogger:
    """Simple but effective issue logging for user problems and site monitoring"""
    
    def __init__(self):
        self.log_file = os.path.join(os.getcwd(), 'user_issues.log')
        self.ensure_log_file()
    
    def ensure_log_file(self):
        """Ensure log file exists"""
        try:
            if not os.path.exists(self.log_file):
                with open(self.log_file, 'w') as f:
                    f.write('')
        except Exception as e:
            logger.error(f"Failed to create log file: {e}")
    
    def log_issue(self, issue_type, component, message, severity='medium', 
                  error_details=None, user_context=None, file_info=None):
        """Log a user issue with comprehensive details"""
        
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            
            # Get request context safely
            request_info = {}
            if request:
                request_info = {
                    'method': request.method,
                    'endpoint': request.endpoint,
                    'url': request.url,
                    'user_agent': request.headers.get('User-Agent', ''),
                    'ip_address': request.remote_addr
                }
            
            # Get session context safely
            session_info = {}
            if session:
                session_info = {
                    'session_id': session.get('session_id', ''),
                    'user_id': session.get('user_id', '')
                }
            
            # Create comprehensive log entry
            log_entry = {
                'timestamp': timestamp,
                'issue_type': issue_type,  # 'error', 'warning', 'performance', 'user_action'
                'component': component,    # 'upload', '3d_viewer', 'optimization', 'download'
                'severity': severity,      # 'low', 'medium', 'high', 'critical'
                'message': message,
                'request_info': request_info,
                'session_info': session_info,
                'error_details': error_details,
                'user_context': user_context or {},
                'file_info': file_info or {}
            }
            
            # Write to log file
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')
            
            # Also log to Python logger for console output
            log_level = {
                'low': logging.INFO,
                'medium': logging.WARNING,
                'high': logging.ERROR,
                'critical': logging.CRITICAL
            }.get(severity, logging.INFO)
            
            logger.log(log_level, f"[{component}] {message}")
            
        except Exception as e:
            # Fallback logging
            logger.error(f"Failed to log issue: {e}")
            try:
                with open(self.log_file, 'a') as f:
                    f.write(f"LOGGING_ERROR: {timestamp} - {message}\n")
            except:
                pass
    
    def log_user_action(self, action, details=None, duration_ms=None):
        """Log user actions for behavior analysis"""
        self.log_issue(
            issue_type='user_action',
            component='user_behavior',
            message=f"User action: {action}",
            severity='low',
            user_context={
                'action': action,
                'details': details or {},
                'duration_ms': duration_ms
            }
        )
    
    def log_error(self, component, error, context=None):
        """Log an error with full traceback"""
        self.log_issue(
            issue_type='error',
            component=component,
            message=str(error),
            severity='high',
            error_details={
                'error_type': type(error).__name__,
                'traceback': traceback.format_exc()
            },
            user_context=context
        )
    
    def log_performance_issue(self, component, operation, duration_ms, threshold_ms=1000):
        """Log performance issues"""
        if duration_ms > threshold_ms:
            self.log_issue(
                issue_type='performance',
                component=component,
                message=f"Slow operation: {operation} took {duration_ms:.2f}ms",
                severity='medium' if duration_ms < threshold_ms * 2 else 'high',
                user_context={
                    'operation': operation,
                    'duration_ms': duration_ms,
                    'threshold_ms': threshold_ms
                }
            )
    
    def log_file_operation(self, operation, filename, file_size=None, success=True, error=None):
        """Log file operations for debugging upload/download issues"""
        severity = 'low' if success else 'high'
        message = f"File {operation}: {filename} ({'success' if success else 'failed'})"
        
        self.log_issue(
            issue_type='error' if not success else 'user_action',
            component='file_operations',
            message=message,
            severity=severity,
            error_details={'error': str(error)} if error else None,
            file_info={
                'operation': operation,
                'filename': filename,
                'file_size': file_size,
                'success': success
            }
        )
    
    def log_optimization_result(self, task_id, original_size, optimized_size, success, error=None):
        """Log optimization results for monitoring"""
        compression_ratio = ((original_size - optimized_size) / original_size * 100) if success else 0
        
        self.log_issue(
            issue_type='user_action' if success else 'error',
            component='optimization',
            message=f"Optimization {'completed' if success else 'failed'}: {compression_ratio:.1f}% compression",
            severity='low' if success else 'high',
            error_details={'error': str(error)} if error else None,
            user_context={
                'task_id': task_id,
                'original_size': original_size,
                'optimized_size': optimized_size,
                'compression_ratio': compression_ratio,
                'success': success
            }
        )
    
    def get_recent_issues(self, hours=24, severity=None, component=None):
        """Get recent issues for monitoring dashboard"""
        try:
            from datetime import timedelta
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            issues = []
            
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        entry_time = datetime.fromisoformat(entry['timestamp'])
                        
                        if entry_time >= cutoff_time:
                            if severity and entry.get('severity') != severity:
                                continue
                            if component and entry.get('component') != component:
                                continue
                            issues.append(entry)
                    except:
                        continue
            
            return sorted(issues, key=lambda x: x['timestamp'], reverse=True)
        
        except Exception as e:
            logger.error(f"Failed to read issues: {e}")
            return []
    
    def get_issue_summary(self, hours=24):
        """Get summary statistics for dashboard"""
        try:
            issues = self.get_recent_issues(hours)
            
            severity_counts = {}
            component_counts = {}
            
            for issue in issues:
                severity = issue.get('severity', 'unknown')
                component = issue.get('component', 'unknown')
                
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
                component_counts[component] = component_counts.get(component, 0) + 1
            
            return {
                'total_issues': len(issues),
                'severity_breakdown': severity_counts,
                'component_breakdown': component_counts,
                'recent_critical': [i for i in issues if i.get('severity') == 'critical'][:5]
            }
        
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return {'total_issues': 0, 'severity_breakdown': {}, 'component_breakdown': {}}

# Global instance
issue_logger = IssueLogger()

def track_errors(component):
    """Decorator to automatically track errors"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            try:
                result = func(*args, **kwargs)
                
                # Log successful completion
                duration = (datetime.now() - start_time).total_seconds() * 1000
                issue_logger.log_user_action(
                    f"{component}_{func.__name__}_success",
                    {'duration_ms': duration}
                )
                
                return result
                
            except Exception as e:
                # Log the error
                duration = (datetime.now() - start_time).total_seconds() * 1000
                issue_logger.log_error(
                    component,
                    e,
                    context={
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
            
            issue_logger.log_performance_issue(
                component, 
                func.__name__, 
                duration, 
                threshold_ms
            )
            
            return result
        return wrapper
    return decorator