import os
import subprocess
import tempfile
import time
import logging
import shutil
import json
import re
import fcntl
import stat
import hashlib
import atexit
import struct
import concurrent.futures
import multiprocessing
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any, Optional, Set, Union
import threading
from config import Config, OptimizationConfig, GLBConstants, OptimizationThresholds

# Type hint for path-like objects
PathLike = Union[str, Path]

# Path utility functions for consistent pathlib.Path usage
def ensure_path(path_like: PathLike) -> Path:
    """Convert string or Path-like object to pathlib.Path consistently"""
    return Path(path_like)

def path_exists(path_like: PathLike) -> bool:
    """Check if path exists using pathlib.Path"""
    return ensure_path(path_like).exists()

def path_size(path_like: PathLike) -> int:
    """Get file size using pathlib.Path"""
    return ensure_path(path_like).stat().st_size

def path_basename(path_like: PathLike) -> str:
    """Get basename using pathlib.Path"""
    return ensure_path(path_like).name

def path_dirname(path_like: PathLike) -> Path:
    """Get directory using pathlib.Path"""
    return ensure_path(path_like).parent

def path_join(*parts: PathLike) -> Path:
    """Join path parts using pathlib.Path"""
    if not parts:
        return Path()
    result = ensure_path(parts[0])
    for part in parts[1:]:
        result = result / ensure_path(part)
    return result

def path_resolve(path_like: PathLike) -> Path:
    """Resolve path to absolute form using pathlib.Path"""
    return ensure_path(path_like).resolve()

def path_is_symlink(path_like: PathLike) -> bool:
    """Check if path is a symlink using pathlib.Path"""
    return ensure_path(path_like).is_symlink()

# Global standalone functions for parallel processing
def run_gltfpack_geometry_parallel(input_path, output_path):
    """Standalone function for parallel gltfpack geometry compression using hardened subprocess wrapper"""
    try:
        # Use a temporary GLBOptimizer instance for secure subprocess execution
        with GLBOptimizer('high') as optimizer:
            cmd = [
                'gltfpack',
                '-i', input_path,
                '-o', output_path,
                '-cc',  # Aggressive compression
                '-cf'   # No fallback compression
            ]
            
            # Route through hardened subprocess wrapper with sanitized environment
            result = optimizer._run_subprocess(
                cmd,
                step_name='parallel_gltfpack_geometry',
                description='Parallel GLTFPack geometry compression',
                timeout=optimizer.config.SUBPROCESS_TIMEOUT
            )
            
            # Check output using pathlib.Path operations
            if result['success'] and path_exists(output_path) and path_size(output_path) > 0:
                return {'success': True}
            else:
                return {
                    'success': False, 
                    'error': result.get('error', 'gltfpack failed'),
                    'detailed_error': result.get('detailed_error', '')
                }
                
    except Exception as e:
        return {'success': False, 'error': str(e)}

def run_draco_compression_parallel(input_path, output_path):
    """Standalone function for parallel Draco compression using hardened subprocess wrapper"""
    try:
        # Use a temporary GLBOptimizer instance for secure subprocess execution
        with GLBOptimizer('high') as optimizer:
            cmd = [
                'npx', 'gltf-transform', 'draco',
                input_path, output_path,
                '--method', 'edgebreaker',
                '--quantize-position', '14',
                '--quantize-normal', '10',
                '--quantize-color', '8',
                '--quantize-texcoord', '12'
            ]
            
            # Route through hardened subprocess wrapper with sanitized environment
            result = optimizer._run_subprocess(
                cmd,
                step_name='parallel_draco_compression',
                description='Parallel Draco geometry compression',
                timeout=optimizer.config.SUBPROCESS_TIMEOUT
            )
            
            # Check output using standard os operations
            if result['success'] and path_exists(output_path) and path_size(output_path) > 0:
                return {'success': True}
            else:
                return {
                    'success': False, 
                    'error': result.get('error', 'Draco compression failed'),
                    'detailed_error': result.get('detailed_error', '')
                }
                
    except Exception as e:
        return {'success': False, 'error': str(e)}

def run_gltf_transform_optimize_parallel(input_path, output_path):
    """Standalone function for parallel gltf-transform optimize using hardened subprocess wrapper"""
    try:
        # Use a temporary GLBOptimizer instance for secure subprocess execution
        with GLBOptimizer('high') as optimizer:
            cmd = [
                'npx', 'gltf-transform', 'optimize',
                input_path, output_path,
                '--compress', 'meshopt',
                '--instance',
                '--simplify', str(OptimizationThresholds.SIMPLIFY_RATIOS['high']),
                '--weld', '0.0001'
            ]
            
            # Route through hardened subprocess wrapper with sanitized environment
            result = optimizer._run_subprocess(
                cmd,
                step_name='parallel_gltf_transform_optimize',
                description='Parallel gltf-transform optimization',
                timeout=optimizer.config.SUBPROCESS_TIMEOUT
            )
            
            # Check output using standard os operations
            if result['success'] and path_exists(output_path) and path_size(output_path) > 0:
                return {'success': True}
            else:
                return {
                    'success': False, 
                    'error': result.get('error', 'gltf-transform optimize failed'),
                    'detailed_error': result.get('detailed_error', '')
                }
                
    except Exception as e:
        return {'success': False, 'error': str(e)}

class GLBOptimizer:
    def __init__(self, quality_level='high'):
        """
        Initialize GLB Optimizer with enhanced security and performance
        quality_level: 'high' (default), 'balanced', or 'maximum_compression'
        """
        self.logger = logging.getLogger(__name__)
        
        # Load centralized configuration
        self.config = OptimizationConfig.from_env()
        self.quality_level = quality_level
        self.quality_settings = self.config.get_quality_settings(quality_level)
        self.detailed_logs = []  # Store detailed error logs for user download
        
        # Log configuration summary
        self.logger.info(f"GLBOptimizer initialized with config: {self.config.to_dict()}")
        self.logger.info(f"Quality level '{quality_level}': {self.quality_settings['description']}")
        
        # Security: Define allowed base directories for file operations
        # Only allow uploads and output directories for security
        self.allowed_dirs = {
            str(path_resolve('uploads')),
            str(path_resolve('output'))
        }
        
        # Security: Track temporary files for cleanup
        self._temp_files: Set[str] = set()
        self._secure_temp_dir: Optional[str] = None
        self._file_locks: Dict[str, threading.Lock] = {}
        self._cleanup_registered = False
        
        # Performance: Cache for path validations
        self._path_cache: Dict[str, str] = {}
        
        # Security: Validate environment on initialization
        self._validate_environment()
    
    def __enter__(self):
        """Context manager entry"""
        if not self._cleanup_registered:
            atexit.register(self.cleanup_temp_files)
            self._cleanup_registered = True
        
        # Initialize secure temp directory for context manager usage
        if self._secure_temp_dir is None:
            self._secure_temp_dir = tempfile.mkdtemp(prefix='glb_secure_')
            self._temp_files.add(self._secure_temp_dir)
            self.logger.debug(f"Created secure temp directory: {self._secure_temp_dir}")
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - guaranteed cleanup without masking original exceptions"""
        try:
            self.cleanup_temp_files()
        except Exception as cleanup_error:
            # Log cleanup error but don't let it override the original exception
            self.logger.error(f"Cleanup error during context manager exit: {cleanup_error}")
        finally:
            return False  # Always re-raise any original exceptions from the with block
    
    def _validate_environment(self):
        """Security: Validate environment and required tools"""
        # Ensure allowed directories exist and are secure
        for allowed_dir in self.allowed_dirs:
            if not path_exists(allowed_dir):
                ensure_path(allowed_dir).mkdir(mode=0o755, parents=True, exist_ok=True)
            
            # Security: Check directory permissions
            dir_stat = ensure_path(allowed_dir).stat()
            if stat.S_IMODE(dir_stat.st_mode) & 0o022:  # Check for world/group write
                self.logger.warning(f"Directory {allowed_dir} has overly permissive permissions")
        
        # Check for required tools availability
        self._check_required_tools()
    
    def _check_required_tools(self):
        """Check if required optimization tools are available"""
        tools_status = {}
        
        # Check gltf-transform
        try:
            result = subprocess.run(['npx', 'gltf-transform', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                tools_status['gltf-transform'] = 'available'
                self.logger.info(f"gltf-transform available: {result.stdout.strip()}")
            else:
                tools_status['gltf-transform'] = 'failed'
                self.logger.warning(f"gltf-transform check failed: {result.stderr}")
        except Exception as e:
            tools_status['gltf-transform'] = 'missing'
            self.logger.error(f"gltf-transform not available: {e}")
        
        # Check gltfpack
        try:
            result = subprocess.run(['gltfpack', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                tools_status['gltfpack'] = 'available'
                self.logger.info(f"gltfpack available: {result.stdout.strip()}")
            else:
                tools_status['gltfpack'] = 'failed'
                self.logger.warning(f"gltfpack check failed: {result.stderr}")
        except Exception as e:
            tools_status['gltfpack'] = 'missing'
            self.logger.error(f"gltfpack not available: {e}")
        
        # Store tool status for later use
        self.tools_status = tools_status
        
        # Log overall status
        available_tools = [tool for tool, status in tools_status.items() if status == 'available']
        if available_tools:
            self.logger.info(f"Available optimization tools: {', '.join(available_tools)}")
        else:
            self.logger.warning("No optimization tools detected - basic GLB processing only")
    
    def _validate_path(self, file_path: str, allow_temp: bool = False) -> str:
        """
        Security: Validate and sanitize file paths with TOCTOU protection
        Returns: Validated absolute path or raises ValueError
        """
        # Performance: Check cache first with normalized path key (but still re-validate at operation time)
        # Normalize the path before using as cache key to ensure functionally identical paths
        # (e.g., ./model.glb, models/../model.glb) use the same cache entry
        try:
            normalized_path = str(path_resolve(file_path))
        except (OSError, ValueError):
            # If path cannot be resolved, use the original path for cache key
            normalized_path = file_path
        
        cache_key = f"{normalized_path}:{allow_temp}"
        if cache_key in self._path_cache:
            cached_path = self._path_cache[cache_key]
            # Still perform immediate re-validation for TOCTOU protection
            return self._immediate_path_validation(cached_path, allow_temp)
        
        try:
            # Security: Initial validation - resolve symlinks and get real path
            abs_path = str(path_resolve(file_path))
            validated_path = self._immediate_path_validation(abs_path, allow_temp)
            
            # Cache successful validation using normalized path key
            self._path_cache[cache_key] = validated_path
            return validated_path
            
        except Exception as e:
            self.logger.error(f"Path validation failed for {file_path}: {e}")
            raise ValueError(f"Invalid or unsafe file path: {file_path}")
    
    def _immediate_path_validation(self, abs_path: str, allow_temp: bool = False) -> str:
        """
        Security: Immediate path validation with TOCTOU protection
        Performs real-time validation immediately before file operations
        """
        # CRITICAL: Re-resolve symlinks immediately before use (TOCTOU protection)
        abs_path = str(path_resolve(abs_path))
        
        # IMPROVEMENT: Skip extension validation for directories
        if ensure_path(abs_path).is_dir() or abs_path.endswith('/') or abs_path.endswith('\\'):
            # Directory paths don't need extension validation
            pass
        elif allow_temp:
            # Security: Enhanced extension validation for temporary files
            # Whitelist of allowed extensions for temporary files
            allowed_temp_extensions = ['.glb', '.tmp', '.ktx2', '.webp', '.png', '.jpg', '.jpeg']
            
            # Check if the file has an allowed extension
            has_valid_extension = any(abs_path.lower().endswith(ext) for ext in allowed_temp_extensions)
            
            # Also allow compound extensions for GLB temp files
            glb_temp_patterns = ['.glb.tmp', '.gltfpack_temp.glb', '.ktx2.tmp', '.webp.tmp']
            is_glb_temp = any(pattern in abs_path.lower() for pattern in glb_temp_patterns)
            
            # Allow gltfpack temporary files (multiple patterns supported)
            # Pattern 1: .tmp.#### where #### is process ID (e.g., file.tmp.5938)
            # Pattern 2: _optimized.tmp.#### for output files (e.g., filename_optimized.tmp.5938)
            # Pattern 3: .glb.tmp.#### for GLB temp files
            gltfpack_patterns = [
                r'\.tmp\.\d+$',                    # Standard .tmp.XXXX
                r'_optimized\.tmp\.\d+$',          # Output temp files
                r'\.glb\.tmp\.\d+$',               # GLB temp files
                r'\.ktx2\.tmp\.\d+$',              # KTX2 temp files
                r'\.webp\.tmp\.\d+$'               # WebP temp files
            ]
            is_gltfpack_temp = any(re.search(pattern, abs_path.lower()) for pattern in gltfpack_patterns)
            
            if not (has_valid_extension or is_glb_temp or is_gltfpack_temp):
                raise ValueError(f"Temporary file has disallowed extension: {abs_path}")
        else:
            # Non-temp files must be .glb
            if not abs_path.lower().endswith('.glb'):
                raise ValueError(f"Path must be a .glb file: {abs_path}")
        
        # Security: Ensure path doesn't contain dangerous characters
        dangerous_chars = [';', '|', '&', '$', '`', '>', '<', '\n', '\r', '\0']
        if any(char in abs_path for char in dangerous_chars):
            raise ValueError(f"Path contains dangerous characters: {abs_path}")
        
        # Security: Check against allowed directories
        path_allowed = False
        allowed_directories = []
        
        # Add configured allowed directories
        for allowed_dir in self.allowed_dirs:
            allowed_real = str(path_resolve(allowed_dir))
            allowed_directories.append(allowed_real)
            try:
                if str(ensure_path(abs_path).relative_to(ensure_path(allowed_real))):
                    path_allowed = True
                    break
            except ValueError:
                # Different drives on Windows
                continue
        
        # Add secure temp directory if initialized
        if hasattr(self, '_secure_temp_dir') and self._secure_temp_dir:
            secure_temp_real = str(path_resolve(self._secure_temp_dir))
            allowed_directories.append(secure_temp_real)
            try:
                if str(ensure_path(abs_path).relative_to(ensure_path(secure_temp_real))):
                    path_allowed = True
            except ValueError:
                pass
        
        # Allow system temp directory for temp files only
        if allow_temp and not path_allowed:
            temp_dir = tempfile.gettempdir()
            temp_real = str(path_resolve(temp_dir))
            allowed_directories.append(temp_real)
            try:
                if str(ensure_path(abs_path).relative_to(ensure_path(temp_real))):
                    path_allowed = True
            except ValueError:
                pass
        
        if not path_allowed:
            # IMPROVEMENT: Check if this is a directory path instead of a file path
            # Directories shouldn't be validated as files with extensions
            if ensure_path(abs_path).is_dir() or abs_path.endswith('/') or abs_path.endswith('\\'):
                self.logger.warning(f"Directory path validation attempted (skipping): {abs_path}")
                return abs_path  # Allow directory paths to pass through
            
            self.logger.error(f"Path validation failed - Path outside allowed directories: {abs_path}")
            self.logger.error(f"Allowed directories: {allowed_directories}")
            self.logger.error(f"allow_temp flag: {allow_temp}")
            # Add detailed debug info for temp file validation
            if allow_temp and '.tmp.' in abs_path:
                self.logger.error(f"This appears to be a temp file that should be allowed. Checking patterns...")
                gltfpack_patterns = [r'\.tmp\.\d+$', r'_optimized\.tmp\.\d+$', r'\.glb\.tmp\.\d+$']
                for pattern in gltfpack_patterns:
                    if re.search(pattern, abs_path.lower()):
                        self.logger.error(f"File matches gltfpack pattern {pattern} but still rejected")
            raise ValueError(f"Path outside allowed directories: {abs_path}")
        
        # Security: Additional symlink check after path resolution
        if path_is_symlink(abs_path):
            raise ValueError(f"TOCTOU attack detected: Symlink still present after resolution: {abs_path}")
        
        return abs_path
    
    def _safe_file_operation(self, filepath: str, operation: str, *args, **kwargs):
        """Security: Perform file operations with enhanced TOCTOU protection"""
        # Initial path validation
        validated_path = self._validate_path(filepath, allow_temp=True)
        
        # Get or create file lock for thread safety
        if validated_path not in self._file_locks:
            self._file_locks[validated_path] = threading.Lock()
        
        with self._file_locks[validated_path]:
            # CRITICAL: Immediate re-validation before every file operation (TOCTOU protection)
            # This is the key enhancement - re-realpath and re-check before each operation
            final_validated_path = self._immediate_path_validation(validated_path, allow_temp=True)
            
            # Structured logging for diagnostics and security monitoring
            operation_start_time = time.time()
            operation_success = False
            
            try:
                # Perform the actual operation with final path validation
                if operation == 'read':
                    # Final existence check before opening
                    if not path_exists(final_validated_path):
                        raise FileNotFoundError(f"File does not exist: {filepath}")
                    with open(final_validated_path, 'rb') as f:
                        result = f.read()
                        operation_success = True
                        return result
                elif operation == 'read_bytes':
                    # Read only specified number of bytes from start of file (memory efficient)
                    if not path_exists(final_validated_path):
                        raise FileNotFoundError(f"File does not exist: {filepath}")
                    num_bytes = args[0] if args else 12  # Default to 12 bytes for GLB header
                    with open(final_validated_path, 'rb') as f:
                        result = f.read(num_bytes)
                        operation_success = True
                        return result
                elif operation == 'write':
                    with open(final_validated_path, 'wb') as f:
                        result = f.write(args[0])
                        operation_success = True
                        return result
                elif operation == 'copy':
                    # Re-validate destination path immediately before copy
                    dest_path = self._immediate_path_validation(args[0], allow_temp=True)
                    # Re-validate source exists before copy
                    if not path_exists(final_validated_path):
                        raise FileNotFoundError(f"Source file does not exist: {filepath}")
                    result = ensure_path(dest_path).write_bytes(ensure_path(final_validated_path).read_bytes())
                    operation_success = True
                    return result
                elif operation == 'exists':
                    result = path_exists(final_validated_path)
                    operation_success = True
                    return result
                elif operation == 'size':
                    if not path_exists(final_validated_path):
                        raise FileNotFoundError(f"File does not exist: {filepath}")
                    result = path_size(final_validated_path)
                    operation_success = True
                    return result
                elif operation == 'remove':
                    if path_exists(final_validated_path):
                        ensure_path(final_validated_path).unlink()
                        result = True
                    else:
                        result = True  # Already removed
                    operation_success = True
                    return result
                elif operation == 'makedirs':
                    mode = kwargs.get('mode', 0o755)
                    exist_ok = kwargs.get('exist_ok', True)
                    ensure_path(final_validated_path).mkdir(mode=mode, parents=True, exist_ok=exist_ok)
                    result = True
                    operation_success = True
                    return result
                elif operation == 'read_text':
                    # Final existence check before opening
                    if not path_exists(final_validated_path):
                        raise FileNotFoundError(f"File does not exist: {filepath}")
                    with open(final_validated_path, 'r', encoding='utf-8') as f:
                        result = f.read()
                        operation_success = True
                        return result
                elif operation == 'write_text':
                    with open(final_validated_path, 'w', encoding='utf-8') as f:
                        result = f.write(args[0])
                        operation_success = True
                        return result
                else:
                    raise ValueError(f"Unknown operation: {operation}")
                    
            except Exception as e:
                operation_success = False
                raise
            finally:
                # Structured logging for diagnostics and security monitoring
                operation_duration = time.time() - operation_start_time
                self.logger.info(
                    f"FILE_OPERATION source={path_basename(filepath)} "
                    f"action={operation} "
                    f"path={final_validated_path} "
                    f"success={operation_success} "
                    f"duration={operation_duration:.3f}s"
                )
    
    def _get_safe_environment(self):
        """Create a minimal safe environment for subprocesses with dynamic PATH construction"""
        # Build PATH dynamically for cross-environment compatibility
        path_components = []
        
        # 1. Add project node_modules/.bin if it exists (for local npm packages)
        project_node_bin = path_join(Path.cwd(), 'node_modules', '.bin')
        if project_node_bin.is_dir():
            path_components.append(str(project_node_bin))
            self.logger.debug(f"Added project node_modules/.bin to PATH: {project_node_bin}")
        
        # 2. Extract Node.js/NPX paths from current environment if available (for Nix/containerized environments)
        current_path = os.environ.get('PATH', '')
        if current_path:
            for path_dir in current_path.split(':'):
                path_obj = Path(path_dir)
                if path_obj.is_dir():
                    # Include directories that contain Node.js tools or are Node.js-related
                    contains_node_tools = any(tool in path_dir.lower() for tool in ['node', 'npm', 'npx'])
                    # Also include directories that contain gltf-transform or gltfpack
                    has_gltf_tools = (path_obj / 'gltf-transform').exists() or (path_obj / 'gltfpack').exists()
                    
                    if (contains_node_tools or has_gltf_tools) and path_dir not in path_components:
                        path_components.append(path_dir)
                        self.logger.debug(f"Added tool path from environment: {path_dir} (node_tools: {contains_node_tools}, gltf_tools: {has_gltf_tools})")
        
        # 3. Add standard system directories (always present)
        standard_paths = ['/usr/local/bin', '/usr/bin', '/bin']
        for std_path in standard_paths:
            if std_path not in path_components and Path(std_path).is_dir():
                path_components.append(std_path)
        
        # Construct final PATH
        safe_path = ':'.join(path_components)
        self.logger.info(f"Dynamic PATH constructed: {safe_path}")
        
        safe_env = {
            'PATH': safe_path,
            'HOME': os.environ.get('HOME', '/tmp'),
            'USER': os.environ.get('USER', 'nobody'),
            'LOGNAME': os.environ.get('LOGNAME', 'nobody'),
            'LANG': 'en_US.UTF-8',
            'LC_ALL': 'en_US.UTF-8',
            'TMPDIR': tempfile.gettempdir()
        }
        
        # Add essential variables for Node/NPM tools (filtered for security)
        essential_vars = ['NODE_PATH', 'NPM_CONFIG_PREFIX', 'PKG_CONFIG_PATH', 'NPM_CONFIG_CACHE', 
                         'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME']
        for var in essential_vars:
            if var in os.environ:
                safe_env[var] = os.environ[var]
        
        # Set defaults for XDG variables if not present
        if 'XDG_CONFIG_HOME' not in safe_env:
            safe_env['XDG_CONFIG_HOME'] = str(path_join(safe_env['HOME'], '.config'))
        if 'XDG_DATA_HOME' not in safe_env:
            safe_env['XDG_DATA_HOME'] = str(path_join(safe_env['HOME'], '.local', 'share'))
        if 'XDG_CACHE_HOME' not in safe_env:
            safe_env['XDG_CACHE_HOME'] = str(path_join(safe_env['HOME'], '.cache'))
        
        # Add Replit-specific environment variables if present
        replit_vars = ['REPLIT_DOMAINS', 'REPL_ID', 'REPLIT_DB_URL']
        for var in replit_vars:
            if var in os.environ:
                safe_env[var] = os.environ[var]
        
        return safe_env
    
    def _validate_file_size(self, file_path: str) -> Dict[str, Any]:
        """
        Validate file size to prevent DoS attacks and handle edge cases
        """
        try:
            # Check if file exists
            if not self._safe_file_operation(file_path, 'exists'):
                return {
                    'success': False,
                    'error': 'Input file does not exist',
                    'user_message': 'The uploaded file could not be found.',
                    'category': 'File System Error'
                }
            
            # Get file size safely
            try:
                file_size = self._safe_file_operation(file_path, 'size')
            except OSError as e:
                return {
                    'success': False,
                    'error': f'Cannot read file size: {str(e)}',
                    'user_message': 'Unable to read the uploaded file.',
                    'category': 'File System Error'
                }
            
            # Check for empty files
            if file_size <= 0:
                return {
                    'success': False,
                    'error': 'File is empty or has invalid size',
                    'user_message': 'The uploaded file appears to be empty.',
                    'category': 'File Size Error'
                }
            
            # Check for suspiciously small files using centralized config
            if file_size < self.config.MIN_FILE_SIZE:
                return {
                    'success': False,
                    'error': f'File too small: {file_size} bytes',
                    'user_message': f'The file is too small (minimum {self.config.MIN_FILE_SIZE} bytes required).',
                    'category': 'File Size Error'
                }
            
            # Check for files that are too large (DoS protection) using centralized config
            if file_size > self.config.MAX_FILE_SIZE:
                size_mb = file_size / (1024 * 1024)
                max_size_mb = self.config.MAX_FILE_SIZE / (1024 * 1024)
                return {
                    'success': False,
                    'error': f'File too large: {size_mb:.1f}MB',
                    'user_message': f'The file is too large ({size_mb:.1f}MB). Maximum size is {max_size_mb:.0f}MB.',
                    'category': 'File Size Error'
                }
            
            # Additional check for files that might be corrupted or truncated
            if file_size < Config.EMPTY_FILE_THRESHOLD:
                self.logger.warning(f"File is very small ({file_size} bytes), may be corrupted")
            
            # Basic GLB format validation
            format_validation = self._validate_glb_format(file_path)
            if not format_validation['success']:
                return format_validation
            
            # Log file size for monitoring
            size_mb = file_size / (1024 * 1024)
            self.logger.info(f"File size validation passed: {size_mb:.2f}MB")
            
            return {
                'success': True,
                'file_size': file_size,
                'size_mb': size_mb
            }
            
        except Exception as e:
            self.logger.error(f"File size validation failed: {str(e)}")
            return {
                'success': False,
                'error': f'File validation error: {str(e)}',
                'user_message': 'Unable to validate the uploaded file.',
                'category': 'Validation Error'
            }
    
    def validate_glb(self, file_path: str, mode: str = "header") -> Dict[str, Any]:
        """
        Unified GLB file validation supporting different validation levels
        
        Args:
            file_path: Path to GLB file to validate
            mode: Validation mode - "header" for basic format validation, "full" for comprehensive validation
                 
        Returns:
            Dictionary with validation results and metadata
        """
        try:
            # Mode-specific preliminary checks
            if mode == "full":
                # For output validation, check file existence first
                if not self._safe_file_operation(file_path, 'exists'):
                    return {
                        'success': False,
                        'error': 'File does not exist',
                        'user_message': 'The output file was not created.',
                        'category': 'File System Error'
                    }
                
                file_size = self._safe_file_operation(file_path, 'size')
                if file_size == 0:
                    return {
                        'success': False,
                        'error': 'File is empty',
                        'user_message': 'The optimization produced an empty file.',
                        'category': 'Output Error'
                    }
            else:
                # For input validation, get file size for later use
                file_size = self._safe_file_operation(file_path, 'size')
            
            # Common validation: minimum header size
            if file_size < 12:
                error_context = "The optimization produced a corrupted file." if mode == "full" else "This does not appear to be a valid GLB file."
                category = "Output Error" if mode == "full" else "Format Error"
                return {
                    'success': False,
                    'error': 'File too small for GLB header',
                    'user_message': error_context,
                    'category': category
                }
            
            # Memory efficient: read only GLB header bytes instead of entire file
            header_data = self._safe_file_operation(file_path, 'read_bytes', GLBConstants.HEADER_LENGTH)
            
            if len(header_data) < GLBConstants.HEADER_LENGTH:
                error_context = "The optimization produced a corrupted file." if mode == "full" else "This does not appear to be a valid GLB file."
                category = "Output Error" if mode == "full" else "Format Error"
                return {
                    'success': False,
                    'error': 'Cannot read GLB header',
                    'user_message': error_context,
                    'category': category
                }
            
            # Validate magic number (bytes 0-3)
            magic = header_data[0:4]
            if magic != GLBConstants.MAGIC_NUMBER:
                if mode == "full":
                    error_msg = 'The optimization produced an invalid GLB file.'
                    category = 'Output Error'
                else:
                    error_msg = 'This file is not a valid GLB format.'
                    category = 'Format Error'
                return {
                    'success': False,
                    'error': f'Invalid GLB magic number: {magic}',
                    'user_message': error_msg,
                    'category': category
                }
            
            # Validate version (bytes 4-7) - use struct.unpack for consistency
            version = struct.unpack('<I', header_data[GLBConstants.VERSION_OFFSET:GLBConstants.VERSION_OFFSET+4])[0]
            if version != GLBConstants.SUPPORTED_VERSION:
                if mode == "full":
                    error_msg = f'The optimization produced GLB version {version}, but only version 2 is supported.'
                    category = 'Output Error'
                else:
                    error_msg = f'GLB version {version} is not supported. Please use GLB version 2.'
                    category = 'Format Error'
                return {
                    'success': False,
                    'error': f'Unsupported GLB version: {version}',
                    'user_message': error_msg,
                    'category': category
                }
            
            # Validate file length consistency (bytes 8-11)
            stated_length = struct.unpack('<I', header_data[GLBConstants.LENGTH_OFFSET:GLBConstants.LENGTH_OFFSET+4])[0]
            
            if stated_length != file_size:
                self.logger.warning(f"GLB length mismatch: header says {stated_length}, file is {file_size}")
                # Don't fail on length mismatch as some files have padding
            
            # Mode-specific advanced validation
            if mode == "full":
                # Additional validation for output files: check chunk structure
                if file_size < GLBConstants.MIN_FILE_WITH_CHUNK:  # 12 bytes header + 8 bytes minimum chunk header
                    return {
                        'success': False,
                        'error': 'GLB file has no chunks',
                        'user_message': 'The optimization produced an incomplete GLB file.',
                        'category': 'Output Error'
                    }
                
                # Memory efficient: read first chunk header (8 bytes at offset 12)
                # Read total 20 bytes (12 header + 8 chunk header) instead of entire file
                header_and_chunk_data = self._safe_file_operation(file_path, 'read_bytes', GLBConstants.MIN_FILE_WITH_CHUNK)
                chunk_header = header_and_chunk_data[GLBConstants.HEADER_LENGTH:GLBConstants.MIN_FILE_WITH_CHUNK]
                if len(chunk_header) < GLBConstants.CHUNK_HEADER_LENGTH:
                    return {
                        'success': False,
                        'error': 'Cannot read first chunk header',
                        'user_message': 'The optimization produced a corrupted GLB file.',
                        'category': 'Output Error'
                    }
                
                chunk_length = struct.unpack('<I', chunk_header[GLBConstants.CHUNK_LENGTH_OFFSET:GLBConstants.CHUNK_LENGTH_OFFSET+4])[0]
                chunk_type = chunk_header[GLBConstants.CHUNK_TYPE_OFFSET:GLBConstants.CHUNK_TYPE_OFFSET+4]
                
                # First chunk should be JSON
                if chunk_type != GLBConstants.JSON_CHUNK_TYPE:
                    return {
                        'success': False,
                        'error': f'First chunk is not JSON: {chunk_type}',
                        'user_message': 'The optimization produced an invalid GLB file structure.',
                        'category': 'Output Error'
                    }
                
                # Basic sanity check on chunk length
                if chunk_length == 0 or chunk_length > file_size:
                    return {
                        'success': False,
                        'error': f'Invalid chunk length: {chunk_length}',
                        'user_message': 'The optimization produced a corrupted GLB file.',
                        'category': 'Output Error'
                    }
                
                self.logger.info(f"GLB validation passed: version {version}, length {stated_length}, first chunk length {chunk_length}")
                return {
                    'success': True,
                    'version': version,
                    'file_size': file_size,
                    'chunk_length': chunk_length
                }
            else:
                # Header-only validation successful
                self.logger.info(f"GLB format validation passed: version {version}, length {stated_length}")
                return {
                    'success': True,
                    'version': version,
                    'file_size': file_size
                }
                
        except Exception as e:
            if mode == "full":
                error_msg = 'Unable to validate the optimization output.'
                category = 'Output Error'
            else:
                error_msg = 'Unable to validate the GLB file format.'
                category = 'Format Error'
                
            self.logger.error(f"GLB validation failed: {str(e)}")
            return {
                'success': False,
                'error': f'GLB validation error: {str(e)}',
                'user_message': error_msg,
                'category': category
            }

    def _validate_glb_format(self, file_path: str) -> Dict[str, Any]:
        """Legacy wrapper for header-mode validation - use validate_glb() instead"""
        return self.validate_glb(file_path, mode="header")
    
    def _validate_glb_file(self, filepath: str) -> Dict[str, Any]:
        """Legacy wrapper for full-mode validation - use validate_glb() instead"""
        try:
            result = self.validate_glb(filepath, mode="full")
            return result if result is not None else {
                'success': False,
                'error': 'Validation returned None',
                'user_message': 'File validation failed unexpectedly.',
                'category': 'Validation Error'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Validation exception: {str(e)}',
                'user_message': 'File validation failed unexpectedly.',
                'category': 'Validation Error'
            }
    
    def _atomic_write(self, temp_path: str, final_path: str) -> Dict[str, Any]:
        """
        Atomically move temporary file to final destination with validation
        """
        try:
            # Validate the temporary file before moving
            validation_result = self._validate_glb_file(temp_path)
            if not validation_result['success']:
                return validation_result
            
            # Ensure target directory exists
            target_dir = str(path_dirname(final_path))
            try:
                self._safe_file_operation(target_dir, 'makedirs', mode=0o755, exist_ok=True)
            except ValueError:
                # Directory might be outside safe paths during testing
                ensure_path(target_dir).mkdir(mode=0o755, parents=True, exist_ok=True)
            
            # Atomic move (POSIX) or rename (Windows)
            if os.name == 'posix':
                # On POSIX systems, replace() is atomic
                ensure_path(temp_path).replace(final_path)
            else:
                # On Windows, need to remove target first
                try:
                    if self._safe_file_operation(final_path, 'exists'):
                        self._safe_file_operation(final_path, 'remove')
                except ValueError:
                    # Path might be outside safe directories during testing
                    if path_exists(final_path):
                        ensure_path(final_path).unlink()
                ensure_path(temp_path).rename(final_path)
            
            # Remove from temp tracking since it's now the final file
            self._temp_files.discard(temp_path)
            
            # Final validation of moved file
            final_validation = self._validate_glb_file(final_path)
            if not final_validation:
                return {
                    'success': False,
                    'error': 'Final validation returned None',
                    'user_message': 'The optimization produced an invalid output file.',
                    'category': 'Validation Error'
                }
            if not final_validation.get('success'):
                error_msg = final_validation.get('error', 'Unknown validation error')
                return {
                    'success': False,
                    'error': f'Final validation failed: {error_msg}',
                    'user_message': 'The optimization produced an invalid output file.',
                    'category': 'Validation Error'
                }
            
            self.logger.info(f"Atomic write successful: {temp_path} -> {final_path}")
            return {
                'success': True,
                'final_path': final_path,
                'file_size': final_validation.get('file_size', 0)
            }
            
        except Exception as e:
            self.logger.error(f"Atomic write failed: {str(e)}")
            return {
                'success': False,
                'error': f'Atomic write failed: {str(e)}',
                'user_message': 'Failed to finalize the optimization output.',
                'category': 'File System Error'
            }

    def cleanup_temp_files(self):
        """Security: Clean up temporary files and directories"""
        for temp_path in list(self._temp_files):
            try:
                if ensure_path(temp_path).is_file():
                    try:
                        self._safe_file_operation(temp_path, 'remove')
                    except ValueError:
                        # Temp path might be outside safe directories
                        ensure_path(temp_path).unlink()
                elif ensure_path(temp_path).is_dir():
                    import shutil; shutil.rmtree(temp_path)  # pathlib doesn't have rmtree equivalent
                self._temp_files.discard(temp_path)
            except Exception as e:
                self.logger.warning(f"Failed to clean up temp file {temp_path}: {e}")
        
        # Clear caches
        self._path_cache.clear()
        self._file_locks.clear()
    
    def cleanup(self):
        """Explicit cleanup method for non-context-manager usage"""
        self.cleanup_temp_files()
        
    def _run_subprocess(self, cmd: list, step_name: str, description: str, timeout: int = None) -> Dict[str, Any]:
        """
        Run subprocess with comprehensive error handling and enhanced security
        Security: All file paths in commands are validated before execution
        """
        # Use centralized configuration for timeout if not specified
        if timeout is None:
            timeout = self.config.SUBPROCESS_TIMEOUT
            
        try:
            # Security: Validate all file paths in the command
            validated_cmd = []
            for arg in cmd:
                if arg.endswith('.glb') and '/' in arg:
                    # This looks like a file path - validate it
                    try:
                        # Allow temp paths for intermediate processing files
                        validated_path = self._validate_path(arg, allow_temp=True)
                        validated_cmd.append(validated_path)
                    except ValueError as e:
                        # If validation fails, reject the command
                        self.logger.error(f"Security: Blocked potentially dangerous path in command: {arg}")
                        raise ValueError(f"Command contains invalid file path: {arg}")
                else:
                    validated_cmd.append(arg)
            
            self.logger.info(f"Running {step_name}: {' '.join(validated_cmd)}")
            
            # Enhanced subprocess execution with security controls
            # Create minimal, safe environment for subprocesses
            safe_env = self._get_safe_environment()
            
            result = subprocess.run(
                validated_cmd, 
                capture_output=True, 
                text=True, 
                timeout=timeout,
                cwd=str(Path.cwd()),
                env=safe_env,
                shell=False  # Explicitly disable shell for security
            )
            
            # Log all output for debugging
            if result.stdout:
                self.logger.debug(f"{step_name} stdout: {result.stdout}")
                
            if result.stderr:
                self.logger.debug(f"{step_name} stderr: {result.stderr}")
                
            if result.returncode == 0:
                return {
                    'success': True,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'step': step_name
                }
            else:
                error_details = self._analyze_error(result.stderr, result.stdout, step_name)
                detailed_log = {
                    'step': step_name,
                    'description': description,
                    'command': ' '.join(validated_cmd),  # Log the validated command, not original
                    'exit_code': result.returncode,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'analysis': error_details,
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                self.detailed_logs.append(detailed_log)
                
                return {
                    'success': False,
                    'error': error_details['user_message'],
                    'detailed_error': error_details['technical_details'],
                    'step': step_name,
                    'logs': detailed_log
                }
                
        except subprocess.TimeoutExpired:
            timeout_minutes = timeout // 60
            error_msg = f"{step_name} timed out after {timeout_minutes} minutes"
            self.logger.error(error_msg)
            return {
                'success': False,
                'error': f"{description} took too long and was stopped after {timeout_minutes} minutes. This usually indicates a very complex model or insufficient system resources.",
                'detailed_error': error_msg,
                'step': step_name
            }
            
        except FileNotFoundError:
            error_msg = f"Required tool not found for {step_name}: {validated_cmd[0]}"
            self.logger.error(error_msg)
            self.logger.error(f"Current PATH for tool detection: {safe_env.get('PATH', 'N/A')}")
            # Try to detect if the tool exists anywhere in the system
            tool_name = validated_cmd[0]
            tool_found = None
            for path_dir in safe_env.get('PATH', '').split(':'):
                potential_tool = Path(path_dir) / tool_name
                if potential_tool.exists():
                    tool_found = str(potential_tool)
                    self.logger.error(f"Tool found at {tool_found} but not accessible")
                    break
            
            error_details = f"Tool '{tool_name}' not found in PATH. "
            if tool_found:
                error_details += f"Tool exists at {tool_found} but is not accessible."
            else:
                error_details += "Tool not installed or not in PATH."
                
            return {
                'success': False,
                'error': "Required optimization tool is not installed. Please contact support.",
                'detailed_error': error_details,
                'step': step_name
            }
            
        except Exception as e:
            error_msg = f"Unexpected error in {step_name}: {str(e)}"
            self.logger.error(error_msg)
            return {
                'success': False,
                'error': f"An unexpected error occurred during {description.lower()}.",
                'detailed_error': error_msg,
                'step': step_name
            }
    
    def _analyze_error(self, stderr: str, stdout: str, step_name: str) -> Dict[str, str]:
        """
        Analyze error output and provide user-friendly explanations
        """
        combined_output = (stderr + stdout).lower()
        
        # Common error patterns and user-friendly explanations
        error_patterns = {
            'out of memory': {
                'user_message': 'The model is too large for available memory. Try using "Maximum Compression" quality level or reduce the model complexity.',
                'category': 'Resource Limitation'
            },
            'unsupported format': {
                'user_message': 'The GLB file contains unsupported features or corrupted data. Please verify the file is a valid GLB.',
                'category': 'File Format Error'
            },
            'texture compression failed': {
                'user_message': 'Texture optimization failed, possibly due to unsupported image formats. The model may contain non-standard textures.',
                'category': 'Texture Processing Error'
            },
            'mesh optimization failed': {
                'user_message': 'Geometry optimization failed. The model may have invalid mesh data or unsupported mesh features.',
                'category': 'Geometry Processing Error'
            },
            'animation compression failed': {
                'user_message': 'Animation optimization failed. The model may contain complex or corrupted animation data.',
                'category': 'Animation Processing Error'
            },
            'draco': {
                'user_message': 'Draco compression failed. Trying alternative compression method.',
                'category': 'Compression Error'
            },
            'ktx2': {
                'user_message': 'Advanced texture compression failed. Falling back to standard compression.',
                'category': 'Texture Compression Error'
            },
            'basis': {
                'user_message': 'Basis Universal texture compression failed. Using fallback compression.',
                'category': 'Texture Compression Error'
            },
            'file not found': {
                'user_message': 'Required file was not found during processing. This may indicate file corruption.',
                'category': 'File System Error'
            },
            'permission denied': {
                'user_message': 'File access permission denied. Please try uploading the file again.',
                'category': 'File System Error'
            },
            'invalid gltf': {
                'user_message': 'The GLB file is corrupted or invalid. Please verify the file is properly exported.',
                'category': 'File Format Error'
            },
            'node.js': {
                'user_message': 'JavaScript optimization tool error. This is usually a temporary issue.',
                'category': 'Tool Error'
            }
        }
        
        # Find matching error pattern
        for pattern, info in error_patterns.items():
            if pattern in combined_output:
                return {
                    'user_message': info['user_message'],
                    'category': info['category'],
                    'technical_details': f"{step_name} failed: {stderr[:500]}..." if len(stderr) > 500 else stderr
                }
        
        # Generic error handling
        if stderr:
            return {
                'user_message': f'Optimization step "{step_name}" failed. This may be due to complex model features or file corruption.',
                'category': 'Processing Error',
                'technical_details': f"{step_name} error: {stderr[:500]}..." if len(stderr) > 500 else stderr
            }
        
        return {
            'user_message': f'Optimization step "{step_name}" failed for an unknown reason.',
            'category': 'Unknown Error',
            'technical_details': f"No error details available for {step_name}"
        }
    
    def get_detailed_logs(self) -> str:
        """
        Get formatted detailed logs for user download
        """
        if not self.detailed_logs:
            return "No detailed error logs available."
            
        log_content = []
        log_content.append("GLB Optimization Error Report")
        log_content.append("=" * 40)
        log_content.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        log_content.append("")
        
        for i, log in enumerate(self.detailed_logs, 1):
            log_content.append(f"Error #{i}: {log['step']}")
            log_content.append("-" * 30)
            log_content.append(f"Description: {log['description']}")
            log_content.append(f"Command: {log['command']}")
            log_content.append(f"Exit Code: {log['exit_code']}")
            log_content.append(f"Timestamp: {log['timestamp']}")
            log_content.append("")
            log_content.append("Error Analysis:")
            log_content.append(f"  Category: {log['analysis']['category']}")
            log_content.append(f"  User Message: {log['analysis']['user_message']}")
            log_content.append("")
            log_content.append("Technical Details:")
            if log['stdout']:
                log_content.append("STDOUT:")
                log_content.append(log['stdout'])
                log_content.append("")
            if log['stderr']:
                log_content.append("STDERR:")
                log_content.append(log['stderr'])
                log_content.append("")
            log_content.append("=" * 40)
            log_content.append("")
            
        return "\n".join(log_content)
    
    def get_detailed_logs_json(self) -> dict:
        """
        Get detailed logs in JSON format for debugging and API responses
        """
        if not self.detailed_logs:
            return {"logs": [], "message": "No detailed logs available"}
            
        return {
            "optimization_logs": self.detailed_logs,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "quality_level": self.quality_level,
            "log_count": len(self.detailed_logs)
        }
    
    def optimize(self, input_path, output_path, progress_callback=None):
        """
        Optimize a GLB file using the industry-standard 6-step workflow with atomic output
        """
        start_time = time.time()
        temp_output = None
        
        try:
            # Initialize secure temp directory at start of optimization if not already set
            if self._secure_temp_dir is None:
                self._secure_temp_dir = tempfile.mkdtemp(prefix='glb_secure_')
                self._temp_files.add(self._secure_temp_dir)
            
            # Security: Validate all file paths before any operations
            validated_input = self._validate_path(input_path)
            validated_output = self._validate_path(output_path)
            
            self.logger.info(f"Starting optimization with validated paths: {validated_input} -> {validated_output}")
            
            # File size validation for security and performance
            file_validation = self._validate_file_size(validated_input)
            if not file_validation['success']:
                return file_validation
            
            # Create temporary output file for atomic operation
            temp_output = str(ensure_path(validated_output).with_suffix(f'.tmp.{os.getpid()}'))
            self._temp_files.add(temp_output)
            
            # Additional security: Ensure paths are within expected directories
            expected_upload_dir = str(path_resolve('uploads'))
            expected_output_dir = str(path_resolve('output'))
            
            if not (validated_input.startswith(expected_upload_dir) or validated_input.startswith(expected_output_dir)):
                self.logger.error(f"Security violation: Input path outside allowed directories: {validated_input}")
                return {
                    'success': False,
                    'error': 'Security violation: Invalid input path',
                    'user_message': 'File access denied for security reasons.',
                    'category': 'Security Error'
                }
            
            if not validated_output.startswith(expected_output_dir):
                self.logger.error(f"Security violation: Output path outside allowed directories: {validated_output}")
                return {
                    'success': False,
                    'error': 'Security violation: Invalid output path',
                    'user_message': 'File access denied for security reasons.',
                    'category': 'Security Error'
                }
            # Create secure temporary directory for intermediate files
            with tempfile.TemporaryDirectory(prefix='glb_opt_') as temp_dir:
                # Set secure permissions and add to tracking
                self._temp_files.add(temp_dir)
                
                # Step 1: Strip the fat first (cleanup & deduplication)
                if progress_callback:
                    progress_callback("Step 1: Cleanup & Deduplication", 10, "Pruning unused data...")
                
                step1_output = self._validate_path(str(path_join(temp_dir, "step1_pruned.glb")), allow_temp=True)
                result = self._run_gltf_transform_prune(validated_input, step1_output)
                if not result['success']:
                    return result
                
                # Step 2: Weld and join meshes
                if progress_callback:
                    progress_callback("Step 1: Cleanup & Deduplication", 20, "Welding and joining meshes...")
                
                step2_output = self._validate_path(str(path_join(temp_dir, "step2_welded.glb")), allow_temp=True)
                result = self._run_gltf_transform_weld(step1_output, step2_output)
                if not result['success']:
                    # Continue with step1 result if welding fails
                    self.logger.warning("Welding failed, continuing with step 1 result")
                    step2_output = step1_output
                
                # Step 3: Advanced geometry compression with intelligent method selection
                if progress_callback:
                    progress_callback("Step 2: Geometry Compression", 40, "Analyzing model for optimal compression...")
                
                step3_output = self._validate_path(str(path_join(temp_dir, "step3_compressed.glb")), allow_temp=True)
                result = self._run_advanced_geometry_compression(step2_output, step3_output, progress_callback)
                if not result['success']:
                    # Continue with step2 result if compression fails
                    self.logger.warning("Geometry compression failed, continuing with step 2 result")
                    step3_output = step2_output
                
                # Step 4: Advanced texture compression (MOST IMPORTANT for 50MB→5MB reduction)
                if progress_callback:
                    progress_callback("Step 3: Texture Compression", 60, "Applying advanced texture compression...")
                
                step4_output = self._validate_path(str(path_join(temp_dir, "step4_textures.glb")), allow_temp=True)
                result = self._run_gltf_transform_textures(step3_output, step4_output)
                if not result['success']:
                    # Continue with step3 result if texture compression fails
                    self.logger.warning("Texture compression failed, continuing with step 3 result")
                    step4_output = step3_output
                
                # Step 5: Optimize animations (if any)
                if progress_callback:
                    progress_callback("Step 4: Animation Optimization", 75, "Optimizing animations...")
                
                step5_output = self._validate_path(str(path_join(temp_dir, "step5_animations.glb")), allow_temp=True)
                result = self._run_gltf_transform_animations(step4_output, step5_output)
                if not result['success']:
                    # Continue with step4 result if animation optimization fails
                    self.logger.warning("Animation optimization failed, continuing with step 4 result")
                    step5_output = step4_output
                
                # Step 6: Final bundle and minify (only for high quality)
                if progress_callback:
                    progress_callback("Step 5: Final Optimization", 90, "Final bundling and minification...")
                
                best_result = step5_output
                # Run gltfpack final optimization for all quality levels
                result = self._run_gltfpack_final(step5_output, temp_output)
                if result['success']:
                    best_result = temp_output
                else:
                    # If final optimization fails, use step 5 result
                    self.logger.warning("Final optimization failed, using step 5 result")
                    best_result = step5_output
                
                # Ensure we have a valid result, find best fallback if needed
                if not self._safe_file_operation(best_result, 'exists') or self._safe_file_operation(best_result, 'size') == 0:
                    best_file = None
                    best_size = 0
                    
                    for temp_file in [step5_output, step4_output, step3_output, step2_output, step1_output]:
                        if self._safe_file_operation(temp_file, 'exists') and self._safe_file_operation(temp_file, 'size') > best_size:
                            best_file = temp_file
                            best_size = self._safe_file_operation(temp_file, 'size')
                    
                    if best_file:
                        self.logger.warning(f"Using best intermediate result: {best_file} ({best_size} bytes)")
                        best_result = best_file
                    else:
                        # Last resort: copy the original file
                        self.logger.error("No valid optimization results, copying original")
                        self._safe_file_operation(validated_input, 'copy', temp_output)
                        best_result = temp_output
                
                # If best result is not temp_output, copy it there
                if best_result != temp_output:
                    self._safe_file_operation(best_result, 'copy', temp_output)
                
                if progress_callback:
                    progress_callback("Step 6: Finalizing", 98, "Validating and finalizing output...")
                
                # Atomic write with comprehensive validation
                atomic_result = self._atomic_write(temp_output, validated_output)
                if not atomic_result['success']:
                    return atomic_result
                
                if progress_callback:
                    progress_callback("Step 6: Completed", 100, "Optimization completed successfully!")
                
                # Calculate comprehensive performance metrics
                processing_time = time.time() - start_time
                original_size = self._safe_file_operation(validated_input, 'size')
                final_size = atomic_result['file_size']
                compression_ratio = (1 - final_size / original_size) * 100
                
                # Estimate GPU memory usage (approximate)
                estimated_memory_reduction = self._estimate_gpu_memory_savings(original_size, final_size)
                
                # Generate performance report
                performance_metrics = self._generate_performance_report(validated_input, validated_output, processing_time)
                
                self.logger.info(f"Optimization completed: {original_size} → {final_size} bytes ({compression_ratio:.1f}% reduction)")
                self.logger.info(f"Estimated GPU memory savings: {estimated_memory_reduction:.1f}%")
                
                return {
                    'success': True,
                    'processing_time': processing_time,
                    'original_size': original_size,
                    'compressed_size': final_size,
                    'compression_ratio': compression_ratio,
                    'savings_bytes': original_size - final_size,
                    'estimated_memory_savings': estimated_memory_reduction,
                    'performance_metrics': performance_metrics,
                    'optimization_quality': self.quality_level,
                    'message': 'Optimization completed successfully'
                }
        
        except Exception as e:
            self.logger.error(f"Optimization failed: {str(e)}")
            return {
                'success': False,
                'error': f'Optimization failed: {str(e)}'
            }
        finally:
            # Clean up temporary output file if it exists
            if temp_output and path_exists(temp_output):
                try:
                    ensure_path(temp_output).unlink()
                    self._temp_files.discard(temp_output)
                except Exception as cleanup_error:
                    self.logger.warning(f"Failed to cleanup temp file {temp_output}: {cleanup_error}")
    
    def _run_gltf_transform_prune(self, input_path, output_path):
        """Step 1: Prune unused data"""
        try:
            cmd = ['npx', 'gltf-transform', 'prune', input_path, output_path]
            result = self._run_subprocess(cmd, "Prune Unused Data", "Removing unused data and orphaned nodes")
            
            # Check if output file was created and has reasonable size
            if result['success'] and self._safe_file_operation(output_path, 'exists'):
                output_size = self._safe_file_operation(output_path, 'size')
                if output_size == 0:
                    # If prune resulted in empty file, just copy the original
                    self.logger.warning("Prune operation resulted in empty file, copying original")
                    self._safe_file_operation(input_path, 'copy', output_path)
                return {'success': True}
            elif result['success']:
                # If the command succeeded but no output file, copy original
                self.logger.warning("Prune succeeded but no output file, copying original")
                ensure_path(output_path).write_bytes(ensure_path(input_path).read_bytes())
                return {'success': True}
            else:
                return result
        except Exception as e:
            # Fallback: just copy the original file
            self.logger.warning(f"Prune failed with exception, copying original: {e}")
            ensure_path(output_path).write_bytes(ensure_path(input_path).read_bytes())
            return {'success': True}
    
    def _run_gltf_transform_weld(self, input_path, output_path):
        """Step 2: Weld vertices and join meshes"""
        try:
            # First weld vertices
            temp_welded = input_path + '.welded.glb'
            self._temp_files.add(temp_welded)
            
            cmd = ['npx', 'gltf-transform', 'weld', '--tolerance', '0.0001', input_path, temp_welded]
            result = self._run_subprocess(cmd, "Weld Vertices", "Welding duplicate vertices")
            
            if not result['success']:
                self.logger.warning(f"Welding failed, continuing: {result.get('error', '')}")
                ensure_path(output_path).write_bytes(ensure_path(input_path).read_bytes())
                return {'success': True}
            
            # Then join meshes
            cmd = ['npx', 'gltf-transform', 'join', temp_welded, output_path]
            result = self._run_subprocess(cmd, "Join Meshes", "Joining compatible meshes")
            
            if not result['success']:
                self.logger.warning(f"Joining failed, using welded version: {result.get('error', '')}")
                ensure_path(output_path).write_bytes(ensure_path(temp_welded).read_bytes())
            
            return {'success': True}
            
        except Exception as e:
            return {'success': False, 'error': f'Welding/joining failed: {str(e)}'}
    
    def _run_gltfpack_geometry(self, input_path, output_path):
        """Step 3: Advanced geometry compression with meshopt and aggressive optimization"""
        # Quality-based simplification levels
        simplify_ratio = {
            'high': str(OptimizationThresholds.SIMPLIFY_RATIOS['high']),  # 80% triangle count (preserve quality)
            'balanced': str(OptimizationThresholds.SIMPLIFY_RATIOS['balanced']),  # 60% triangle count (balance quality/size)
            'maximum_compression': str(OptimizationThresholds.SIMPLIFY_RATIOS['maximum_compression'])  # 40% triangle count (maximum compression)
        }.get(self.quality_level, '0.7')
        
        # Advanced meshopt compression with aggressive settings
        cmd = [
            'gltfpack',
            '-i', input_path,
            '-o', output_path,
            '--meshopt',  # Enable meshopt compression
            '--quantize',  # Quantize vertex attributes
            '--simplify', simplify_ratio,  # Polygon simplification
            '--simplify-error', str(OptimizationThresholds.SIMPLIFY_ERROR_THRESHOLD),  # Low error threshold for quality
            '--attributes',  # Optimize vertex attributes
            '--indices',  # Optimize index buffers
            '--normals',  # Optimize normal vectors
            '--tangents',  # Optimize tangent vectors
            '--join',  # Join compatible meshes
            '--dedup',  # Remove duplicate vertices
            '--reorder',  # Reorder primitives for GPU efficiency
            '--sparse',  # Use sparse accessors when beneficial
        ]
        
        # Add quality-specific options
        if self.quality_level == 'maximum_compression':
            cmd.extend([
                '--simplify-aggressive',  # More aggressive simplification
                '--simplify-lock-border',  # Preserve mesh borders
            ])
        
        result = self._run_subprocess(cmd, "Advanced Geometry Compression", "Applying meshopt with aggressive optimization")
        
        if not result['success']:
            self.logger.warning(f"Advanced geometry compression failed, trying basic meshopt: {result.get('error', 'Unknown error')}")
            # Fallback to basic meshopt compression
            cmd_fallback = [
                'gltfpack',
                '-i', input_path,
                '-o', output_path,
                '--meshopt',
                '--quantize'
            ]
            fallback_result = self._run_subprocess(cmd_fallback, "Basic Geometry Compression", "Applying basic meshopt compression")
            return fallback_result
        
        return result
    
    def _run_draco_compression(self, input_path, output_path):
        """Advanced Draco geometry compression for maximum compression"""
        # Use centralized Draco compression settings from config
        quality_settings = self.config.get_quality_settings(self.quality_level)
        draco_quantization = quality_settings['draco_quantization_bits']
        compression_level = quality_settings['draco_compression_level']
        
        try:
            # Use gltf-transform with advanced Draco settings
            cmd = [
                'npx', 'gltf-transform', 'draco',
                '--method', 'edgebreaker',  # Best compression method
                '--encodeSpeed', '0',       # Favor compression over speed
                '--decodeSpeed', '5',       # Balance decode speed
                '--quantizePosition', str(draco_quantization['position']),
                '--quantizeNormal', str(draco_quantization['normal']),
                '--quantizeColor', str(draco_quantization['color']),
                '--quantizeTexcoord', str(draco_quantization['tex_coord']),
                '--compressionLevel', str(compression_level),
                '--unifiedQuantization',    # Better compression
                input_path, output_path
            ]
            
            result = self._run_subprocess(cmd, "Draco Compression", "Applying advanced Draco compression", timeout=600)
            
            if not result['success']:
                self.logger.error(f"Advanced Draco compression failed: {result.get('detailed_error', 'Unknown error')}")
                # Try basic Draco compression as fallback
                cmd_fallback = [
                    'npx', 'gltf-transform', 'draco',
                    '--method', 'edgebreaker',
                    input_path, output_path
                ]
                fallback_result = self._run_subprocess(cmd_fallback, "Draco Compression", "Applying basic Draco compression fallback", timeout=600)
                
                if not fallback_result['success']:
                    return {
                        'success': False,
                        'error': f'Draco compression failed: {fallback_result.get("detailed_error", "Unknown error")}'
                    }
            
            return {'success': True}
        
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Draco compression timed out'}
        except Exception as e:
            return {'success': False, 'error': f'Draco compression failed: {str(e)}'}
    
    def _run_advanced_geometry_compression(self, input_path, output_path, progress_callback=None):
        """Process-based parallel compression testing for maximum performance"""
        
        # Analyze the model to determine optimal compression strategy
        if progress_callback:
            progress_callback("Step 2: Geometry Compression", 40, "Analyzing model complexity...")
        
        model_analysis = self._analyze_model_complexity(input_path)
        methods_to_test = self._select_compression_methods(model_analysis)
        
        # If only one method, run sequentially to avoid overhead
        if len(methods_to_test) == 1:
            method = methods_to_test[0]
            if progress_callback:
                progress_callback("Step 2: Geometry Compression", 45, f"Running {method} compression...")
            
            if method == 'meshopt':
                return self._run_gltfpack_geometry(input_path, output_path)
            elif method == 'draco':
                return self._run_draco_compression(input_path, output_path)
            elif method == 'hybrid':
                return self._run_gltf_transform_optimize(input_path, output_path)
        
        # Parallel compression testing for multiple methods
        if progress_callback:
            progress_callback("Step 2: Geometry Compression", 42, f"Testing {len(methods_to_test)} compression methods in parallel...")
        
        # Determine optimal worker count (cap at available cores and method count)
        available_cores = multiprocessing.cpu_count()
        max_parallel_workers = getattr(Config, 'MAX_PARALLEL_WORKERS', 3)  # Fallback to 3 workers
        max_workers = min(available_cores, len(methods_to_test), max_parallel_workers)
        
        self.logger.info(f"Running parallel compression with {max_workers} workers for methods: {methods_to_test}")
        
        results = {}
        file_sizes = {}
        temp_files = []
        future_to_method = {}
        
        try:
            with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
                
                # Submit tasks with unique temporary files
                for method in methods_to_test:
                    temp_output = str(path_join(self._secure_temp_dir, f"test_{method}_{os.getpid()}_{time.time():.0f}.glb"))
                    temp_files.append(temp_output)
                    self._temp_files.add(temp_output)
                    
                    if method == 'meshopt':
                        future = executor.submit(run_gltfpack_geometry_parallel, input_path, temp_output)
                    elif method == 'draco':
                        future = executor.submit(run_draco_compression_parallel, input_path, temp_output)
                    elif method == 'hybrid':
                        future = executor.submit(run_gltf_transform_optimize_parallel, input_path, temp_output)
                    
                    future_to_method[future] = (method, temp_output)
                
                # Collect results with timeout
                completed_methods = 0
                parallel_timeout = getattr(Config, 'PARALLEL_TIMEOUT', 120)  # Fallback to 120 seconds
                for future in concurrent.futures.as_completed(future_to_method, timeout=parallel_timeout):
                    method, temp_output = future_to_method[future]
                    completed_methods += 1
                    
                    try:
                        result = future.result(timeout=5)  # Quick timeout since task is done
                        results[method] = result
                        
                        if result['success'] and path_exists(temp_output) and path_size(temp_output) > 0:
                            file_sizes[method] = path_size(temp_output)
                            self.logger.info(f"Parallel {method}: {file_sizes[method]} bytes")
                        
                        if progress_callback:
                            progress = 42 + (completed_methods / len(methods_to_test)) * 6
                            progress_callback("Step 2: Geometry Compression", int(progress), 
                                            f"Completed {completed_methods}/{len(methods_to_test)} compression tests...")
                                            
                    except concurrent.futures.TimeoutError:
                        self.logger.error(f"Compression timeout for {method}")
                        results[method] = {'success': False, 'error': 'Timeout'}
                    except Exception as e:
                        self.logger.error(f"Compression failed for {method}: {e}")
                        results[method] = {'success': False, 'error': str(e)}
        
        except concurrent.futures.TimeoutError:
            self.logger.error("Overall parallel compression timeout - using fallback")
            return self._run_gltfpack_geometry(input_path, output_path)
        except Exception as e:
            self.logger.error(f"Parallel compression failed: {e} - using fallback")
            return self._run_gltfpack_geometry(input_path, output_path)
        
        # Find the best compression method
        successful_methods = {method: size for method, size in file_sizes.items() 
                            if results[method]['success']}
        
        if not successful_methods:
            self.logger.error("All parallel compression methods failed - using fallback")
            return self._run_gltfpack_geometry(input_path, output_path)
        
        # Select method with smallest file size
        best_method_name, best_size = min(successful_methods.items(), key=lambda x: x[1])
        
        self.logger.info(f"Best parallel compression: {best_method_name} ({best_size} bytes)")
        
        # Copy best result to output
        best_temp_file = next(temp_file for method, temp_file in future_to_method.values() 
                             if method == best_method_name)
        
        try:
            if progress_callback:
                progress_callback("Step 2: Geometry Compression", 48, "Finalizing best compression result...")
            
            ensure_path(output_path).write_bytes(ensure_path(best_temp_file).read_bytes())
            
            # Calculate metrics
            input_size = path_size(input_path)
            output_size = path_size(output_path)
            compression_ratio = (1 - output_size / input_size) * 100
            
            self.logger.info(f"Parallel geometry compression ({best_method_name}): {input_size} → {output_size} bytes ({compression_ratio:.1f}% reduction)")
            
            return {
                'success': True,
                'method': best_method_name,
                'compression_ratio': compression_ratio,
                'input_size': input_size,
                'output_size': output_size
            }
            
        except Exception as e:
            self.logger.error(f"Failed to copy best parallel result: {e}")
            return {'success': False, 'error': f'Failed to finalize parallel compression: {str(e)}'}
        
        finally:
            # Clean up all temporary files
            for temp_file in temp_files:
                try:
                    if path_exists(temp_file):
                        ensure_path(temp_file).unlink()
                        self._temp_files.discard(temp_file)
                except Exception as cleanup_error:
                    self.logger.warning(f"Failed to cleanup temp file {temp_file}: {cleanup_error}")


    
    def _run_gltf_transform_optimize(self, input_path, output_path):
        """Hybrid optimization using gltf-transform's comprehensive optimize command"""
        # Quality-based optimization settings
        quality_settings = {
            'high': {
                'compress': 'meshopt',  # Use meshopt for better compatibility
                'instance': True,       # Instance repeated geometry
                'simplify': str(OptimizationThresholds.SIMPLIFY_RATIOS['high']),      # Light simplification
                'weld': '0.0001'        # Precise vertex welding
            },
            'balanced': {
                'compress': 'draco',    # Use Draco for better compression
                'instance': True,
                'simplify': str(OptimizationThresholds.SIMPLIFY_RATIOS['balanced']),      # Moderate simplification  
                'weld': '0.001'         # Moderate vertex welding
            },
            'maximum_compression': {
                'compress': 'draco',    # Use Draco for maximum compression
                'instance': True,
                'simplify': str(OptimizationThresholds.SIMPLIFY_RATIOS['maximum_compression']),      # Aggressive simplification
                'weld': str(OptimizationThresholds.SIMPLIFY_ERROR_THRESHOLD),         # Aggressive vertex welding
                'quantize': '16'        # Quantize positions
            }
        }
        
        settings = quality_settings.get(self.quality_level, quality_settings['balanced'])
        
        try:
            # Build gltf-transform optimize command
            cmd = [
                'npx', 'gltf-transform', 'optimize',
                input_path, output_path,
                '--compress', settings['compress']
            ]
            
            # Add conditional parameters
            if settings.get('instance'):
                cmd.append('--instance')
            
            if settings.get('simplify'):
                cmd.extend(['--simplify', settings['simplify']])
            
            if settings.get('weld'):
                cmd.extend(['--weld', settings['weld']])
            
            if settings.get('quantize'):
                cmd.extend(['--quantize', settings['quantize']])
            
            # Add additional optimization flags
            cmd.extend([
                '--join',       # Join compatible primitives
                '--palette',    # Optimize texture palettes
                '--sparse'      # Use sparse accessors when beneficial
            ])
            
            result = self._run_subprocess(cmd, "GLB Optimization", "Applying gltf-transform optimizations", timeout=600)
            
            if not result['success']:
                self.logger.error(f"gltf-transform optimize failed: {result.get('detailed_error', 'Unknown error')}")
                return {
                    'success': False,
                    'error': f'Hybrid optimization failed: {result.get("detailed_error", "Unknown error")}'
                }
            
            return {'success': True}
            
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Hybrid optimization timed out'}
        except Exception as e:
            return {'success': False, 'error': f'Hybrid optimization failed: {str(e)}'}
    
    def _analyze_model_complexity(self, input_path):
        """Analyze model characteristics to determine optimal compression strategy"""
        try:
            # Use gltf-transform inspect to analyze the model
            cmd = ['npx', 'gltf-transform', 'inspect', input_path, '--format', 'json']
            result = self._run_subprocess(cmd, "Model Analysis", "Inspecting GLB model structure", timeout=60)
            
            if result['success']:
                try:
                    analysis = json.loads(result.get('stdout', '{}'))
                    return {
                        'vertices': analysis.get('scenes', [{}])[0].get('vertices', 0),
                        'primitives': analysis.get('scenes', [{}])[0].get('primitives', 0),
                        'materials': len(analysis.get('materials', [])),
                        'textures': len(analysis.get('textures', [])),
                        'animations': len(analysis.get('animations', [])),
                        'complexity': 'unknown'
                    }
                except json.JSONDecodeError:
                    pass
            
            # Fallback: simple file size-based analysis
            file_size = path_size(input_path)
            return {
                'file_size': file_size,
                'complexity': 'high' if file_size > 10_000_000 else 'medium' if file_size > 1_000_000 else 'low'
            }
            
        except Exception as e:
            self.logger.warning(f"Model analysis failed: {str(e)}")
            return {'complexity': 'unknown'}
    
    def _select_compression_methods(self, analysis):
        """Select optimal compression methods based on model analysis"""
        methods = set()  # Use set to automatically eliminate duplicates
        complexity = analysis.get('complexity', 'unknown')
        vertex_count = analysis.get('vertices', 0)
        
        # Always test meshopt as baseline
        methods.add('meshopt')
        
        # For high-complexity or high-vertex models, Draco often performs better
        if (complexity in ['high', 'unknown'] or 
            vertex_count > OptimizationThresholds.HIGH_VERTEX_COUNT_THRESHOLD or 
            self.quality_level == 'maximum_compression'):
            methods.add('draco')
        
        # Test hybrid approach for complex models or when maximum compression is needed
        if (complexity == 'high' or 
            vertex_count > OptimizationThresholds.VERY_HIGH_VERTEX_COUNT or 
            analysis.get('file_size', 0) > OptimizationThresholds.LARGE_FILE_SIZE_THRESHOLD or
            self.quality_level in ['balanced', 'maximum_compression']):
            methods.add('hybrid')
        
        # Convert set back to list with deterministic order for consistent behavior
        methods_list = ['meshopt', 'draco', 'hybrid']
        selected_methods = [method for method in methods_list if method in methods]
        
        self.logger.info(f"Selected compression methods based on analysis: {selected_methods}")
        return selected_methods
    
    def _compress_with_ktx2(self, input_path, output_path):
        """Compress textures using KTX2/Basis Universal compression"""
        settings = self.quality_settings
        
        try:
            self.logger.info("Attempting KTX2/Basis Universal compression...")
            
            # Check if KTX-Software is available with timeout protection
            ktx_available = False
            try:
                test_result = self._run_subprocess(['which', 'ktx'], "Tool Check", "Checking for KTX-Software availability", timeout=5)
                ktx_available = test_result['success']
                if ktx_available:
                    self.logger.info(f"KTX-Software detected at: {test_result.get('stdout', 'unknown location').strip()}")
                else:
                    self.logger.info("KTX-Software not found in PATH")
            except Exception as e:
                self.logger.info(f"KTX detection error: {e}")
                ktx_available = False
            
            if not ktx_available:
                self.logger.info("KTX-Software not available")
                return {'success': False, 'error': 'KTX-Software not installed'}
            
            # Build compression command based on mode
            if settings['uastc_mode']:
                # UASTC mode for high quality
                self.logger.info("Using UASTC mode for high quality compression")
                ktx2_cmd = [
                    'npx', 'gltf-transform', 'uastc',
                    input_path, output_path,
                    '--level', '1',     # Fast compression level
                    '--rdo', '1.0',     # Minimal rate-distortion optimization
                    '--zstd', '6'       # Fast Zstandard compression
                ]
            else:
                # ETC1S mode for better compression ratio
                self.logger.info("Using ETC1S mode for balanced compression")
                ktx2_cmd = [
                    'npx', 'gltf-transform', 'etc1s',
                    input_path, output_path,
                    '--quality', settings['ktx2_quality'],
                    '--slots', '4'      # Optimize texture slots
                ]
            
            result = self._run_subprocess(ktx2_cmd, "KTX2 Compression", "Advanced texture compression with KTX2", timeout=60)
            
            if result['success'] and path_exists(output_path):
                file_size = path_size(output_path)
                self.logger.info(f"KTX2 compression successful: {file_size} bytes")
                return {'success': True, 'size': file_size}
            else:
                return {'success': False, 'error': result.get('error', 'Compression failed')}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _compress_with_webp(self, input_path, output_path):
        """Compress textures using WebP compression"""
        settings = self.quality_settings
        
        try:
            self.logger.info("Testing WebP compression...")
            webp_cmd = [
                'npx', 'gltf-transform', 'webp',
                input_path, output_path,
                '--quality', settings['webp_quality']
            ]
            
            result = self._run_subprocess(webp_cmd, "WebP Compression", "WebP texture compression", timeout=600)
            
            if result["success"] and path_exists(output_path):
                file_size = path_size(output_path)
                self.logger.info(f"WebP compression successful: {file_size} bytes")
                return {'success': True, 'size': file_size}
            else:
                return {'success': False, 'error': result.get('error', 'Compression failed')}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _select_best_texture_result(self, results, temp_files):
        """Select the best compression result and handle cleanup"""
        successful_methods = {method: result['size'] for method, result in results.items() 
                            if result['success']}
        
        if not successful_methods:
            self.logger.warning("All texture compression methods failed")
            return None, None
        
        # Prefer KTX2 for compatibility, but select smallest if significantly better
        if 'ktx2' in successful_methods and 'webp' in successful_methods:
            ktx2_size = successful_methods['ktx2']
            webp_size = successful_methods['webp']
            
            # Use KTX2 unless WebP is significantly smaller (>20% difference)
            if webp_size < ktx2_size * OptimizationThresholds.WEBP_SIZE_ADVANTAGE_THRESHOLD:
                selected_method = 'webp'
                self.logger.info(f"Selected WebP (significantly smaller): {webp_size} vs {ktx2_size}")
            else:
                selected_method = 'ktx2'
                self.logger.info(f"Selected KTX2 (preferred format): {ktx2_size} vs {webp_size}")
        elif 'ktx2' in successful_methods:
            selected_method = 'ktx2'
        else:
            selected_method = 'webp'
        
        selected_size = successful_methods[selected_method]
        return selected_method, selected_size

    def _cleanup_temp_texture_files(self, temp_files):
        """Clean up temporary texture compression files"""
        for temp_file in temp_files:
            try:
                if path_exists(temp_file):
                    ensure_path(temp_file).unlink()
            except:
                pass

    def _run_gltf_transform_textures(self, input_path, output_path):
        """Step 4: Advanced texture compression with KTX2/BasisU and WebP fallback"""
        # Setup temp files for testing different compression methods
        temp_dir = str(path_dirname(output_path))
        ktx2_output = str(path_join(temp_dir, "test_ktx2.glb"))
        webp_output = str(path_join(temp_dir, "test_webp.glb"))
        temp_files = [ktx2_output, webp_output]
        
        # Attempt both compression methods
        results = {}
        results['ktx2'] = self._compress_with_ktx2(input_path, ktx2_output)
        results['webp'] = self._compress_with_webp(input_path, webp_output)
        
        # Select the best result
        selected_method, selected_size = self._select_best_texture_result(results, temp_files)
        
        if not selected_method:
            # All methods failed, copy original
            ensure_path(output_path).write_bytes(ensure_path(input_path).read_bytes())
            self._cleanup_temp_texture_files(temp_files)
            return {'success': True}
        
        # Move selected file to final output
        selected_file = ktx2_output if selected_method == 'ktx2' else webp_output
        input_size = path_size(input_path)
        compression_ratio = (1 - selected_size / input_size) * 100
        
        shutil.move(selected_file, output_path)
        self._cleanup_temp_texture_files(temp_files)
        
        self.logger.info(f"Texture compression ({selected_method}): {input_size} → {selected_size} bytes ({compression_ratio:.1f}% reduction)")
        
        return {
            'success': True,
            'method': selected_method,
            'compression_ratio': compression_ratio,
            'input_size': input_size,
            'output_size': selected_size
        }

    def _run_gltf_transform_animations(self, input_path, output_path):
        """Step 5: Optimize animations"""
        try:
            # First try to resample animations
            temp_resampled = input_path + '.resampled.glb'
            cmd = ['npx', 'gltf-transform', 'resample', '--fps', '30', input_path, temp_resampled]
            result = self._run_subprocess(cmd, "Animation Resampling", "Resampling animation frames", timeout=300)
            
            if not result['success']:
                self.logger.warning(f"Animation resampling failed, skipping: {result.get('detailed_error', 'Unknown error')}")
                ensure_path(output_path).write_bytes(ensure_path(input_path).read_bytes())
                return {'success': True}
            
            # Then compress animations
            cmd = ['npx', 'gltf-transform', 'compress-animation', '--quantize', '16', temp_resampled, output_path]
            result = self._run_subprocess(cmd, "Animation Compression", "Compressing animation data", timeout=300)
            
            # Clean up temp file
            try:
                ensure_path(temp_resampled).unlink()
            except:
                pass
            
            if not result['success']:
                self.logger.warning(f"Animation compression failed, using resampled version: {result.get('detailed_error', 'Unknown error')}")
                ensure_path(output_path).write_bytes(ensure_path(temp_resampled).read_bytes())
                return {'success': True}
            
            return {'success': True}
        
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Animation optimization timed out'}
        except Exception as e:
            self.logger.warning(f"Animation optimization failed, skipping: {str(e)}")
            ensure_path(output_path).write_bytes(ensure_path(input_path).read_bytes())
            return {'success': True}
    
    def _run_gltfpack_final(self, input_path, output_path):
        """Step 6: Final bundle and minify with gltfpack for all quality levels"""
        try:
            self.logger.info("Running final gltfpack optimization for all quality levels")
            
            # Create a proper temporary file with .glb extension for gltfpack
            temp_glb = output_path + ".gltfpack_temp.glb"
            
            # First try with aggressive compression (-cc)
            cmd = [
                'gltfpack',
                '-i', input_path,
                '-o', temp_glb,  # Use .glb extension for gltfpack
                '-cc'  # Aggressive compression first
            ]
            result = self._run_subprocess(cmd, "Final Optimization", "Applying final gltfpack compression", timeout=120)
            
            # If aggressive compression fails, fallback to basic compression (-c)
            if not result['success']:
                self.logger.info("Aggressive compression failed, trying basic compression")
                cmd[-1] = '-c'  # swap -cc -> -c
                result = self._run_subprocess(cmd, "Final Optimization Fallback", "Applying basic gltfpack compression", timeout=120)
            
            if result['success']:
                # Copy the successful result to the final destination
                self._safe_file_operation(temp_glb, 'copy', output_path)
                # Clean up the temporary gltfpack file
                try:
                    if path_exists(temp_glb):
                        ensure_path(temp_glb).unlink()
                except:
                    pass  # Cleanup failure is not critical
                self.logger.info("Final gltfpack optimization completed successfully")
                return {'success': True}
            else:
                self.logger.warning(f"gltfpack failed: {result.get('detailed_error', 'Unknown error')}")
                # Fallback: copy the input file
                self._safe_file_operation(input_path, 'copy', output_path)
                return {'success': True}
        
        except Exception as e:
            self.logger.warning(f"gltfpack failed with exception: {e}")
            # Fallback: copy the input file
            try:
                self._safe_file_operation(input_path, 'copy', output_path)
            except:
                # Last resort fallback
                ensure_path(output_path).write_bytes(ensure_path(input_path).read_bytes())
            return {'success': True, 'fallback': True}

    def _estimate_gpu_memory_savings(self, original_size: int, compressed_size: int) -> float:
        """Estimate GPU memory savings from optimization"""
        if original_size == 0:
            return 0.0
        
        # Base memory savings from file size reduction
        base_savings = (1.0 - compressed_size / original_size) * 100
        
        # GPU memory multiplier (textures typically expand 2-4x in GPU memory)
        # Compressed textures (KTX2) stay compressed in GPU memory
        estimated_gpu_savings = min(base_savings * 1.2, 95.0)
        
        return estimated_gpu_savings

    def _generate_performance_report(self, input_path: str, output_path: str, processing_time: float) -> dict:
        """
        Generate comprehensive performance metrics report
        """
        try:
            original_size = path_size(input_path)
            compressed_size = path_size(output_path)
            compression_ratio = (1 - compressed_size / original_size) * 100
            
            # Estimate performance improvements for web games
            performance_metrics = {
                'file_size_reduction': {
                    'original_mb': round(original_size / 1024 / 1024, 2),
                    'compressed_mb': round(compressed_size / 1024 / 1024, 2),
                    'savings_mb': round((original_size - compressed_size) / 1024 / 1024, 2),
                    'compression_ratio': round(compression_ratio, 1)
                },
                'estimated_performance_gains': {
                    'load_time_improvement': f"{min(compression_ratio * OptimizationThresholds.LOAD_TIME_COMPRESSION_FACTOR, OptimizationThresholds.MAX_LOAD_TIME_IMPROVEMENT):.0f}%",
                    'bandwidth_savings': f"{compression_ratio:.0f}%",
                    'gpu_memory_savings': f"{self._estimate_gpu_memory_savings(original_size, compressed_size):.0f}%"
                },
                'processing_stats': {
                    'optimization_time': f"{processing_time:.2f}s",
                    'quality_level': self.quality_level,
                    'methods_used': self._get_optimization_methods_used()
                },
                'web_game_readiness': {
                    'mobile_friendly': compressed_size < 10 * 1024 * 1024,  # Under 10MB
                    'web_optimized': compressed_size < 25 * 1024 * 1024,   # Under 25MB
                    'ready_for_streaming': compressed_size < 5 * 1024 * 1024  # Under 5MB
                }
            }
            
            return performance_metrics
            
        except Exception as e:
            self.logger.error(f"Failed to generate performance report: {e}")
            return {'error': 'Performance report generation failed'}

    def _get_optimization_methods_used(self) -> list:
        """
        Get list of optimization methods used based on quality level and analysis
        """
        methods = ['Geometry Pruning', 'Vertex Welding']
        
        if self.quality_level == 'maximum_compression':
            methods.extend(['Draco Compression', 'KTX2 ETC1S', 'Aggressive Quantization'])
        elif self.quality_level == 'balanced':
            methods.extend(['Meshoptimizer', 'KTX2 UASTC', 'Balanced Quantization'])
        else:  # high quality
            methods.extend(['Hybrid Compression', 'KTX2 UASTC', 'Conservative Quantization'])
        
        methods.extend(['Animation Optimization', 'Final Bundling'])
        return methods
