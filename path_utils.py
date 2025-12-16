"""
Path utility functions for consistent pathlib.Path usage across the application.
Provides a clean abstraction layer for file system operations.
"""

from pathlib import Path
from typing import Union

PathLike = Union[str, Path]


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


def path_is_dir(path_like: PathLike) -> bool:
    """Check if path is a directory using pathlib.Path"""
    return ensure_path(path_like).is_dir()


def path_suffix(path_like: PathLike) -> str:
    """Get file extension using pathlib.Path"""
    return ensure_path(path_like).suffix


def path_with_suffix(path_like: PathLike, suffix: str) -> Path:
    """Return path with new suffix using pathlib.Path"""
    return ensure_path(path_like).with_suffix(suffix)


def normalize_path(path_like: PathLike) -> Path:
    """Normalize path by resolving .. and . components using pathlib.Path"""
    return ensure_path(path_like).resolve()


def safe_path_join(base: PathLike, *parts: PathLike) -> Path:
    """
    Safely join paths, ensuring the result stays within the base directory.
    
    Raises ValueError if the resulting path would escape the base directory
    (e.g., via ../ traversal attacks).
    """
    base_path = ensure_path(base).resolve()
    
    # Build the full path
    full_path = base_path
    for part in parts:
        full_path = full_path / ensure_path(part)
    
    # Resolve to absolute path
    resolved = full_path.resolve()
    
    # Security check: ensure the resolved path is still under base
    try:
        resolved.relative_to(base_path)
    except ValueError:
        raise ValueError(f"Path traversal detected: {resolved} is outside {base_path}")
    
    return resolved
