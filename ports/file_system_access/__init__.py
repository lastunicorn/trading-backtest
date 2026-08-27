"""Locates files on disk by glob pattern, filename fragments aside.

Re-exported so callers can use the short form:

    from ports.file_system_access import find_files
"""

from ports.file_system_access.file_system import find_files

__all__ = ["find_files"]
