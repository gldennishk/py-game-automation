"""
Shared path utility functions for converting between absolute and relative paths.

This module provides canonical implementations of path conversion functions
that use the project base directory (obtained via get_base_dir()) as the reference point. 
All path operations should use these functions to ensure consistency across the codebase.
"""
import os


def _base_dir() -> str:
    """Get the project base directory (internal use)"""
    return os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def get_base_dir() -> str:
    """
    Get the project base directory (public API).
    
    Returns:
        Absolute path to the project root directory.
        
    This function provides a public API for accessing the base directory,
    replacing duplicate _base_dir() implementations in other modules.
    """
    return _base_dir()


def to_absolute_path(path: str) -> str:
    """
    Resolve relative path to absolute path using project base directory (get_base_dir()).
    
    Args:
        path: Path string (can be relative or absolute)
    
    Returns:
        Absolute path string. If path is already absolute, returns as-is.
        If conversion fails, returns the original path.
    """
    if not path:
        return path
    if os.path.isabs(path):
        return path
    try:
        base = _base_dir()
        abs_path = os.path.join(base, path)
        return os.path.abspath(abs_path)
    except Exception:
        return path


def to_relative_path(path: str) -> str:
    """
    Convert absolute path to project-relative path.
    
    Args:
        path: Absolute path string
    
    Returns:
        Relative path string (using forward slashes for cross-platform compatibility).
        If path is not within project base directory (get_base_dir()), returns the original path.
        If conversion fails, returns the original path.
    
    Note:
        Uses os.path.commonpath for safe path comparison on all platforms.
        This prevents false matches like C:\\project matching C:\\project_backup on Windows.
    """
    if not path:
        return path
    try:
        base = os.path.abspath(_base_dir())
        abs_path = os.path.abspath(path)
        # Use os.path.commonpath for safe path comparison on all platforms
        # This prevents false matches like C:\project matching C:\project_backup on Windows
        try:
            common = os.path.commonpath([base, abs_path])
            # Check if the common path equals the base path (meaning abs_path is within base)
            if os.path.abspath(common) == os.path.abspath(base):
                rel_path = os.path.relpath(abs_path, base)
                # Normalize path separators to forward slashes for cross-platform compatibility
                return rel_path.replace(os.sep, '/')
        except ValueError:
            # commonpath raises ValueError if paths are on different drives (Windows)
            # In this case, the paths are definitely not related
            pass
    except Exception:
        pass
    # If conversion fails, return as-is (might already be relative)
    return path

