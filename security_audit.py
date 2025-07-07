#!/usr/bin/env python3
"""
Production Security Audit Tool for GLB Optimizer
Validates all security requirements before production deployment
"""

import os
import sys
import subprocess
import json
import pkg_resources
from config import get_config
from pathlib import Path

def check_production_config():
    """Validate production configuration security"""
    print("🔍 CHECKING PRODUCTION CONFIGURATION...")
    
    config = get_config()
    issues = []
    
    # Check environment
    env = os.environ.get('FLASK_ENV', 'development')
    if env != 'production':
        issues.append(f"FLASK_ENV should be 'production', currently: {env}")
    
    # Validate configuration
    config_issues = config.validate_config()
    issues.extend(config_issues)
    
    # Check critical environment variables
    critical_vars = [
        'SESSION_SECRET',
        'REDIS_URL',
        'CELERY_BROKER_URL'
    ]
    
    for var in critical_vars:
        if not os.environ.get(var):
            issues.append(f"Missing critical environment variable: {var}")
    
    return issues

def check_debug_mode():
    """Ensure debug mode is disabled"""
    print("🚫 CHECKING DEBUG MODE...")
    
    issues = []
    config = get_config()
    
    if config.DEBUG:
        issues.append("CRITICAL: Debug mode is enabled - must be disabled in production")
    
    # Check Flask app debug setting
    debug_env = os.environ.get('FLASK_DEBUG', 'False').lower()
    if debug_env in ['true', '1', 'yes']:
        issues.append("CRITICAL: FLASK_DEBUG environment variable is enabled")
    
    return issues

def check_secret_key():
    """Validate secret key strength"""
    print("🔑 CHECKING SECRET KEY...")
    
    issues = []
    secret = os.environ.get('SESSION_SECRET', '')
    
    if not secret:
        issues.append("CRITICAL: SESSION_SECRET environment variable not set")
    elif secret == 'dev_secret_key_change_in_production':
        issues.append("CRITICAL: Using default development secret key")
    elif len(secret) < 32:
        issues.append("CRITICAL: SECRET_KEY must be at least 32 characters long")
    elif secret.isalnum():
        issues.append("WARNING: SECRET_KEY should contain special characters for better security")
    
    return issues

def check_dependencies():
    """Check for vulnerable dependencies"""
    print("📦 CHECKING PYTHON DEPENDENCIES...")
    
    issues = []
    
    try:
        # Run pip-audit if available
        result = subprocess.run(
            ['pip-audit', '--format=json', '--quiet'],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            audit_data = json.loads(result.stdout)
            if audit_data.get('vulnerabilities'):
                for vuln in audit_data['vulnerabilities']:
                    package = vuln.get('package', 'unknown')
                    version = vuln.get('installed_version', 'unknown')
                    advisory = vuln.get('advisory', 'No details')
                    issues.append(f"VULNERABILITY: {package} {version} - {advisory}")
        else:
            issues.append("INFO: pip-audit not available, install with: pip install pip-audit")
    
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        issues.append("INFO: Could not run dependency security scan")
    
    return issues

def check_node_dependencies():
    """Check Node.js dependencies for vulnerabilities"""
    print("📦 CHECKING NODE.JS DEPENDENCIES...")
    
    issues = []
    
    if os.path.exists('package.json'):
        try:
            result = subprocess.run(
                ['npm', 'audit', '--json'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            audit_data = json.loads(result.stdout)
            vulnerabilities = audit_data.get('vulnerabilities', {})
            
            if vulnerabilities:
                high_count = sum(1 for v in vulnerabilities.values() if v.get('severity') == 'high')
                critical_count = sum(1 for v in vulnerabilities.values() if v.get('severity') == 'critical')
                
                if critical_count > 0:
                    issues.append(f"CRITICAL: {critical_count} critical vulnerabilities in Node.js dependencies")
                if high_count > 0:
                    issues.append(f"WARNING: {high_count} high-severity vulnerabilities in Node.js dependencies")
        
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
            issues.append("INFO: Could not run npm audit")
    else:
        issues.append("INFO: No package.json found, skipping Node.js dependency check")
    
    return issues

def check_file_permissions():
    """Check file and directory permissions"""
    print("🔒 CHECKING FILE PERMISSIONS...")
    
    issues = []
    config = get_config()
    
    # Check upload/output directory permissions
    for folder in [config.UPLOAD_FOLDER, config.OUTPUT_FOLDER]:
        if os.path.exists(folder):
            stat = os.stat(folder)
            perms = oct(stat.st_mode)[-3:]
            
            # Should not be world-writable
            if perms.endswith('7') or perms.endswith('6'):
                issues.append(f"WARNING: {folder} is world-writable (permissions: {perms})")
    
    # Check for sensitive files with wrong permissions
    sensitive_files = ['.env', 'config.py', 'app.py']
    for filename in sensitive_files:
        if os.path.exists(filename):
            stat = os.stat(filename)
            perms = oct(stat.st_mode)[-3:]
            
            # Should not be world-readable for sensitive files
            if perms[2] in ['4', '5', '6', '7']:
                issues.append(f"WARNING: {filename} is world-readable (permissions: {perms})")
    
    return issues

def check_https_configuration():
    """Check HTTPS and SSL configuration"""
    print("🔐 CHECKING HTTPS CONFIGURATION...")
    
    issues = []
    
    https_enabled = os.environ.get('HTTPS_ENABLED', 'false').lower()
    if https_enabled not in ['true', '1', 'yes']:
        issues.append("WARNING: HTTPS not enabled (set HTTPS_ENABLED=true for production)")
    
    # Check for SSL certificate paths
    ssl_cert = os.environ.get('SSL_CERT_PATH')
    ssl_key = os.environ.get('SSL_KEY_PATH')
    
    if https_enabled in ['true', '1', 'yes']:
        if not ssl_cert or not ssl_key:
            issues.append("WARNING: HTTPS enabled but SSL_CERT_PATH/SSL_KEY_PATH not configured")
        elif ssl_cert and not os.path.exists(ssl_cert):
            issues.append(f"ERROR: SSL certificate not found: {ssl_cert}")
        elif ssl_key and not os.path.exists(ssl_key):
            issues.append(f"ERROR: SSL private key not found: {ssl_key}")
    
    return issues

def check_server_configuration():
    """Check production server configuration"""
    print("🖥️  CHECKING SERVER CONFIGURATION...")
    
    issues = []
    
    # Check if running with development server
    if 'werkzeug' in sys.modules:
        issues.append("WARNING: Running with Flask development server - use Gunicorn for production")
    
    # Check Gunicorn configuration
    if not os.path.exists('gunicorn.conf.py'):
        issues.append("INFO: Consider creating gunicorn.conf.py for production settings")
    
    # Check reverse proxy configuration
    if not os.path.exists('nginx.conf.example'):
        issues.append("INFO: nginx.conf.example should be configured for reverse proxy")
    
    return issues

def generate_strong_secret():
    """Generate a strong secret key"""
    import secrets
    import string
    
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(64))

def main():
    """Run complete security audit"""
    print("🛡️  GLB OPTIMIZER PRODUCTION SECURITY AUDIT")
    print("=" * 50)
    
    all_issues = []
    
    # Run all security checks
    checks = [
        check_production_config,
        check_debug_mode,
        check_secret_key,
        check_dependencies,
        check_node_dependencies,
        check_file_permissions,
        check_https_configuration,
        check_server_configuration
    ]
    
    for check in checks:
        issues = check()
        all_issues.extend(issues)
    
    print("\n" + "=" * 50)
    print("📋 AUDIT RESULTS")
    print("=" * 50)
    
    critical_issues = [i for i in all_issues if i.startswith('CRITICAL')]
    warning_issues = [i for i in all_issues if i.startswith('WARNING')]
    info_issues = [i for i in all_issues if i.startswith('INFO')]
    error_issues = [i for i in all_issues if i.startswith('ERROR')]
    
    if critical_issues:
        print("\n🚨 CRITICAL ISSUES (MUST FIX BEFORE PRODUCTION):")
        for issue in critical_issues:
            print(f"   {issue}")
    
    if error_issues:
        print("\n❌ ERRORS:")
        for issue in error_issues:
            print(f"   {issue}")
    
    if warning_issues:
        print("\n⚠️  WARNINGS:")
        for issue in warning_issues:
            print(f"   {issue}")
    
    if info_issues:
        print("\n💡 INFORMATION:")
        for issue in info_issues:
            print(f"   {issue}")
    
    if not all_issues:
        print("\n✅ NO SECURITY ISSUES FOUND!")
    
    print(f"\n📊 SUMMARY:")
    print(f"   Critical: {len(critical_issues)}")
    print(f"   Errors: {len(error_issues)}")
    print(f"   Warnings: {len(warning_issues)}")
    print(f"   Info: {len(info_issues)}")
    
    if critical_issues or error_issues:
        print("\n❌ PRODUCTION READINESS: FAILED")
        print("Fix critical issues and errors before deploying to production.")
        
        if any('SESSION_SECRET' in issue for issue in critical_issues):
            print(f"\n💡 QUICK FIX - Generate strong secret key:")
            print(f"export SESSION_SECRET='{generate_strong_secret()}'")
        
        return 1
    else:
        print("\n✅ PRODUCTION READINESS: PASSED")
        print("Application is ready for production deployment.")
        return 0

if __name__ == "__main__":
    sys.exit(main())