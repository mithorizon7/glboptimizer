"""
Enhanced Error Logging System for Production Deployment
Catches EVERY possible error that could occur in the GLB Optimizer
"""

import sys
import logging
import traceback
import functools
from flask import Flask, request, current_app
from issue_logger import issue_logger

class GlobalErrorHandler:
    """Comprehensive error handler that catches all unhandled exceptions"""
    
    def __init__(self, app: Flask = None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize error handling for Flask app"""
        # Set up global exception handler
        app.errorhandler(Exception)(self.handle_exception)
        
        # Set up HTTP error handlers
        for code in [400, 401, 403, 404, 405, 500, 502, 503]:
            app.errorhandler(code)(self.handle_http_error)
        
        # Set up Python-level exception handler
        sys.excepthook = self.handle_uncaught_exception
        
        # Set up teardown handlers
        app.teardown_appcontext(self.handle_teardown_error)
        app.teardown_request(self.handle_request_teardown)
    
    def handle_exception(self, error):
        """Handle all unhandled Flask exceptions"""
        try:
            # Log the full error details
            issue_logger.log_issue(
                issue_type='error',
                component='flask_app',
                message=f"Unhandled Flask exception: {str(error)}",
                severity='critical',
                error_details={
                    'error_type': type(error).__name__,
                    'traceback': traceback.format_exc(),
                    'endpoint': request.endpoint if request else None,
                    'url': request.url if request else None,
                    'method': request.method if request else None
                }
            )
            
            # Return appropriate error response
            if hasattr(error, 'code') and error.code:
                return {'error': 'An error occurred', 'code': error.code}, error.code
            else:
                return {'error': 'Internal server error'}, 500
                
        except Exception as logging_error:
            # Fallback logging if even our error handler fails
            print(f"CRITICAL: Error handler failed: {logging_error}")
            return {'error': 'Critical system error'}, 500
    
    def handle_http_error(self, error):
        """Handle HTTP errors (404, 500, etc.)"""
        try:
            severity = 'high' if error.code >= 500 else 'medium'
            
            issue_logger.log_issue(
                issue_type='error',
                component='http_error',
                message=f"HTTP {error.code}: {error.description}",
                severity=severity,
                error_details={
                    'status_code': error.code,
                    'description': error.description,
                    'endpoint': request.endpoint if request else None,
                    'url': request.url if request else None
                }
            )
            
            return {'error': error.description, 'code': error.code}, error.code
            
        except Exception as logging_error:
            print(f"CRITICAL: HTTP error handler failed: {logging_error}")
            return {'error': 'Error handling failed'}, 500
    
    def handle_uncaught_exception(self, exc_type, exc_value, exc_traceback):
        """Handle uncaught Python exceptions (outside Flask context)"""
        try:
            if issubclass(exc_type, KeyboardInterrupt):
                # Don't log keyboard interrupts
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
                
            issue_logger.log_issue(
                issue_type='error',
                component='python_runtime',
                message=f"Uncaught Python exception: {exc_value}",
                severity='critical',
                error_details={
                    'error_type': exc_type.__name__,
                    'traceback': ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
                    'in_flask_context': False
                }
            )
            
        except Exception as logging_error:
            print(f"CRITICAL: Uncaught exception handler failed: {logging_error}")
        
        # Call the default handler
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
    
    def handle_teardown_error(self, exception):
        """Handle errors during app context teardown"""
        if exception:
            try:
                issue_logger.log_issue(
                    issue_type='error',
                    component='app_teardown',
                    message=f"App teardown error: {str(exception)}",
                    severity='high',
                    error_details={
                        'error_type': type(exception).__name__,
                        'traceback': traceback.format_exc()
                    }
                )
            except:
                print(f"CRITICAL: Teardown error handler failed: {exception}")
    
    def handle_request_teardown(self, exception):
        """Handle errors during request teardown"""
        if exception:
            try:
                issue_logger.log_issue(
                    issue_type='error',
                    component='request_teardown',
                    message=f"Request teardown error: {str(exception)}",
                    severity='medium',
                    error_details={
                        'error_type': type(exception).__name__,
                        'traceback': traceback.format_exc()
                    }
                )
            except:
                print(f"CRITICAL: Request teardown error handler failed: {exception}")

def catch_all_errors(component_name):
    """Enhanced decorator that catches ALL possible errors in a function"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = None
            try:
                import time
                start_time = time.time()
                
                # Execute the function
                result = func(*args, **kwargs)
                
                # Log successful completion
                duration = (time.time() - start_time) * 1000 if start_time else 0
                issue_logger.log_user_action(
                    f"{component_name}_{func.__name__}_success",
                    {'duration_ms': duration}
                )
                
                return result
                
            except Exception as e:
                # Log the error with full context
                duration = (time.time() - start_time) * 1000 if start_time else 0
                
                issue_logger.log_issue(
                    issue_type='error',
                    component=component_name,
                    message=f"Function {func.__name__} failed: {str(e)}",
                    severity='high',
                    error_details={
                        'function': func.__name__,
                        'error_type': type(e).__name__,
                        'traceback': traceback.format_exc(),
                        'duration_ms': duration,
                        'args_count': len(args),
                        'kwargs_keys': list(kwargs.keys())
                    }
                )
                
                # Re-raise the exception to maintain normal error flow
                raise
                
        return wrapper
    return decorator

def log_database_errors(func):
    """Special decorator for database operations"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            issue_logger.log_issue(
                issue_type='error',
                component='database',
                message=f"Database operation failed: {str(e)}",
                severity='high',
                error_details={
                    'function': func.__name__,
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc(),
                    'database_error': True
                }
            )
            raise
    return wrapper

def log_file_operations(func):
    """Special decorator for file operations"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            issue_logger.log_issue(
                issue_type='error',
                component='file_operations',
                message=f"File operation failed: {str(e)}",
                severity='high',
                error_details={
                    'function': func.__name__,
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc(),
                    'file_operation': True
                }
            )
            raise
    return wrapper

def log_optimization_errors(func):
    """Special decorator for optimization operations"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            issue_logger.log_issue(
                issue_type='error',
                component='optimization',
                message=f"Optimization operation failed: {str(e)}",
                severity='critical',
                error_details={
                    'function': func.__name__,
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc(),
                    'optimization_error': True
                }
            )
            raise
    return wrapper

# Global error handler instance
global_error_handler = GlobalErrorHandler()