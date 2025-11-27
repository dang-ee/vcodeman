"""Verilog-XL HDL Filelist Parser and Analyzer.

This package provides tools for parsing and analyzing Verilog-XL format filelists,
resolving nested file references, expanding environment variables, and creating
structured data models for HDL verification workflows.
"""

__version__ = "0.1.0"

from vcodeman.parser import FilelistParser
from vcodeman.resolver import PathResolver, CircularReferenceError, UndefinedVariableError
from vcodeman.models import (
    Base,
    Filelist,
    FileEntry,
    LibraryDirectory,
    LibraryFile,
    IncludeDirectory,
    MacroDefinition,
    LibraryExtension,
    ParsedFilelist,
    ResolutionContext,
)

__all__ = [
    "__version__",
    "FilelistParser",
    "PathResolver",
    "CircularReferenceError",
    "UndefinedVariableError",
    "Base",
    "Filelist",
    "FileEntry",
    "LibraryDirectory",
    "LibraryFile",
    "IncludeDirectory",
    "MacroDefinition",
    "LibraryExtension",
    "ParsedFilelist",
    "ResolutionContext",
]
