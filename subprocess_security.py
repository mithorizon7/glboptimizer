"""
Secure subprocess execution module.
Provides hardened subprocess management with environment sanitization,
path validation, and timeout handling.
"""

import os
import subprocess
import tempfile
import logging
import time
import stat
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from config import Config, OptimizationConfig

logger = logging.getLogger(__name__)


class SubprocessSecurityManager:
    """Manages secure subprocess execution with environment hardening"""
    
    def __init__(self, allowed_dirs: Optional[Set[str]] = None, config: Optional[OptimizationConfig] = None):
        self.config = config or OptimizationConfig.from_env()
        self.allowed_dirs = allowed_dirs or {
            str(Path('uploads').resolve()),
            str(Path('output').resolve())
        }
        self._temp_files: Set[str] = set()
        self._file_locks: Dict[str, threading.Lock] = {}
        self._path_cache: Dict[str, str] = {}
        self._secure_temp_dir: Optional[str] = None
    
    def get_safe_environment(self) -> Dict[str, str]:
        """Create a minimal safe environment for subprocesses"""
        path_components = []
        
        project_node_bin = Path.cwd() / 'node_modules' / '.bin'
        if project_node_bin.is_dir():
            path_components.append(str(project_node_bin))
        
        current_path = os.environ.get('PATH', '')
        if current_path:
            for path_dir in current_path.split(':'):
                path_obj = Path(path_dir)
                if path_obj.is_dir():
                    contains_node_tools = any(tool in path_dir.lower() for tool in ['node', 'npm', 'npx'])
                    has_gltf_tools = (path_obj / 'gltf-transform').exists() or (path_obj / 'gltfpack').exists()
                    
                    if (contains_node_tools or has_gltf_tools) and path_dir not in path_components:
                        path_components.append(path_dir)
        
        standard_paths = ['/usr/local/bin', '/usr/bin', '/bin']
        for std_path in standard_paths:
            if std_path not in path_components and Path(std_path).is_dir():
                path_components.append(std_path)
        
        safe_path = ':'.join(path_components)
        
        safe_env = {
            'PATH': safe_path,
            'HOME': os.environ.get('HOME', '/tmp'),
            'USER': os.environ.get('USER', 'nobody'),
            'LOGNAME': os.environ.get('LOGNAME', 'nobody'),
            'LANG': 'en_US.UTF-8',
            'LC_ALL': 'en_US.UTF-8',
            'TMPDIR': tempfile.gettempdir()
        }
        
        essential_vars = ['NODE_PATH', 'NPM_CONFIG_PREFIX', 'PKG_CONFIG_PATH', 'NPM_CONFIG_CACHE',
                         'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'NIX_PATH', 'NIX_PROFILES']
        
        for var in essential_vars:
            if var in os.environ:
                safe_env[var] = os.environ[var]
        
        return safe_env
    
    def validate_path(self, file_path: str, allow_temp: bool = False) -> str:
        """
        Validate and sanitize file paths with TOCTOU protection
        Returns: Validated absolute path or raises ValueError
        """
        try:
            normalized_path = str(Path(file_path).resolve())
        except (OSError, ValueError):
            normalized_path = file_path
        
        cache_key = f"{normalized_path}:{allow_temp}"
        if cache_key in self._path_cache:
            cached_path = self._path_cache[cache_key]
            return self._immediate_path_validation(cached_path, allow_temp)
        
        try:
            abs_path = str(Path(file_path).resolve())
            validated_path = self._immediate_path_validation(abs_path, allow_temp)
            self._path_cache[cache_key] = validated_path
            return validated_path
            
        except Exception as e:
            logger.error(f"Path validation failed for {file_path}: {e}")
            raise ValueError(f"Invalid or unsafe file path: {file_path}")
    
    def _immediate_path_validation(self, abs_path: str, allow_temp: bool = False) -> str:
        """Immediate path validation with TOCTOU protection"""
        abs_path = str(Path(abs_path).resolve())
        
        path_obj = Path(abs_path)
        if path_obj.is_dir() or abs_path.endswith('/') or abs_path.endswith('\\'):
            pass
        elif allow_temp:
            allowed_temp_extensions = ['.glb', '.tmp', '.ktx2', '.webp', '.png', '.jpg', '.jpeg']
            has_allowed_ext = any(abs_path.lower().endswith(ext) for ext in allowed_temp_extensions)
            
            temp_dir = tempfile.gettempdir()
            is_in_temp = abs_path.startswith(temp_dir) or abs_path.startswith('/tmp')
            
            if self._secure_temp_dir and abs_path.startswith(self._secure_temp_dir):
                return abs_path
            
            if is_in_temp and has_allowed_ext:
                return abs_path
        else:
            if not abs_path.lower().endswith('.glb'):
                raise ValueError(f"Invalid file extension: must be .glb")
        
        is_valid = any(abs_path.startswith(allowed) for allowed in self.allowed_dirs)
        
        if allow_temp:
            temp_dir = tempfile.gettempdir()
            is_valid = is_valid or abs_path.startswith(temp_dir) or abs_path.startswith('/tmp')
            if self._secure_temp_dir:
                is_valid = is_valid or abs_path.startswith(self._secure_temp_dir)
        
        if not is_valid:
            raise ValueError(f"Path traversal attempt detected: {abs_path}")
        
        return abs_path
    
    def run_subprocess(
        self,
        cmd: List[str],
        step_name: str,
        description: str,
        timeout: Optional[int] = None,
        cwd: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a subprocess with comprehensive security and error handling
        """
        timeout = timeout or self.config.SUBPROCESS_TIMEOUT
        
        for i, arg in enumerate(cmd):
            if i > 0 and not arg.startswith('-'):
                try:
                    self.validate_path(arg, allow_temp=True)
                except ValueError:
                    pass
        
        safe_env = self.get_safe_environment()
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=safe_env,
                cwd=cwd
            )
            
            elapsed = time.time() - start_time
            
            if result.returncode == 0:
                logger.info(f"[{step_name}] Success in {elapsed:.2f}s: {description}")
                return {
                    'success': True,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'elapsed': elapsed
                }
            else:
                logger.warning(f"[{step_name}] Failed (code {result.returncode}) in {elapsed:.2f}s: {result.stderr}")
                return {
                    'success': False,
                    'error': f"{step_name} failed with code {result.returncode}",
                    'stderr': result.stderr,
                    'stdout': result.stdout,
                    'elapsed': elapsed
                }
                
        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            logger.error(f"[{step_name}] Timeout after {elapsed:.2f}s")
            return {
                'success': False,
                'error': f"{step_name} timed out after {timeout}s",
                'elapsed': elapsed
            }
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[{step_name}] Exception: {e}")
            return {
                'success': False,
                'error': str(e),
                'elapsed': elapsed
            }
    
    def check_required_tools(self) -> Dict[str, bool]:
        """Check availability of required external tools"""
        tools = {
            'gltf-transform': ['npx', 'gltf-transform', '--version'],
            'gltfpack': ['gltfpack', '--help']
        }
        
        results = {}
        safe_env = self.get_safe_environment()
        
        for tool_name, check_cmd in tools.items():
            try:
                result = subprocess.run(
                    check_cmd,
                    capture_output=True,
                    timeout=10,
                    env=safe_env
                )
                results[tool_name] = result.returncode == 0
            except Exception:
                results[tool_name] = False
        
        return results
    
    def add_temp_file(self, path: str):
        """Track a temporary file for cleanup"""
        self._temp_files.add(path)
    
    def cleanup_temp_files(self):
        """Remove all tracked temporary files"""
        for temp_file in list(self._temp_files):
            try:
                path = Path(temp_file)
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    import shutil
                    shutil.rmtree(temp_file, ignore_errors=True)
                self._temp_files.discard(temp_file)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file {temp_file}: {e}")
    
    def set_secure_temp_dir(self, temp_dir: str):
        """Set the secure temporary directory for this session"""
        self._secure_temp_dir = temp_dir
        self._temp_files.add(temp_dir)
