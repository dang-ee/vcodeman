"""Path resolution logic for Verilog-XL filelists.

Based on research.md design: pathlib.Path + os.path hybrid approach.
"""

import os
import re
import sys
from pathlib import Path
from typing import Optional


class CircularReferenceError(Exception):
    """Raised when a circular filelist reference is detected."""
    pass


class UndefinedVariableError(Exception):
    """Raised when an undefined environment variable is referenced."""
    pass


class PathResolver:
    """Resolves paths in Verilog-XL filelists.

    Handles:
    - Environment variable expansion ($VAR and ${VAR})
    - Relative path resolution
    - Absolute path normalization
    - Symlink preservation (uses absolute() not resolve())
    """

    def __init__(self, strict_env_vars: bool = False):
        """Initialize path resolver.

        Args:
            strict_env_vars: If True, raise error on undefined environment variables.
                In non-strict mode, undefined vars survive in the output and
                each unique unresolved name is warned about exactly once.
        """
        self.strict_env_vars = strict_env_vars
        self._env_var_pattern = re.compile(r'\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?')
        # Names already warned about in non-strict mode (one warning per name
        # per resolver lifetime, to avoid spamming when the same undefined
        # var appears in many paths).
        self._warned_undefined: set[str] = set()

    def expand_env_vars(self, path_str: str) -> str:
        """Expand environment variables in path string.

        Supports both $VAR and ${VAR} syntax.

        Args:
            path_str: Path string potentially containing environment variables

        Returns:
            Path string with environment variables expanded

        Raises:
            UndefinedVariableError: If strict mode and variable is undefined.
        """
        # Strict mode: refuse to proceed on the first undefined name.
        if self.strict_env_vars:
            for match in self._env_var_pattern.finditer(path_str):
                var_name = match.group(1)
                if var_name not in os.environ:
                    raise UndefinedVariableError(
                        f"Undefined environment variable: ${var_name}"
                    )

        expanded = os.path.expandvars(path_str)

        if self.strict_env_vars and '$' in expanded:
            for match in self._env_var_pattern.finditer(expanded):
                var_name = match.group(1)
                raise UndefinedVariableError(
                    f"Undefined environment variable: ${var_name}"
                )

        # Non-strict mode: warn (once per name) about leftover unresolved
        # references so the user sees that the path they're getting has a
        # gap in it.
        if not self.strict_env_vars:
            for match in self._env_var_pattern.finditer(expanded):
                var_name = match.group(1)
                if var_name in self._warned_undefined:
                    continue
                self._warned_undefined.add(var_name)
                print(
                    f"warning: undefined env var ${var_name} survives in resolved "
                    f"path: {expanded}",
                    file=sys.stderr,
                )

        return expanded

    def resolve_path(
        self,
        path_str: str,
        base_dir: Path,
        validate_exists: bool = False
    ) -> Path:
        """Resolve a path string to an absolute path.

        Resolution steps:
        1. Expand environment variables
        2. Convert to Path object
        3. Make absolute relative to base_dir
        4. Use absolute() to preserve symlinks (NOT resolve())

        Args:
            path_str: Path string to resolve
            base_dir: Base directory for relative path resolution
            validate_exists: Whether to check if path exists

        Returns:
            Absolute Path object with symlinks preserved

        Raises:
            UndefinedVariableError: If undefined variable in strict mode
            FileNotFoundError: If validate_exists=True and path doesn't exist
        """
        # Step 1: Expand environment variables
        expanded = self.expand_env_vars(path_str)

        # Step 2: Convert to Path object
        path = Path(expanded)

        # Step 3: Make absolute relative to base directory
        if not path.is_absolute():
            path = base_dir / path

        # Step 4: Normalize path to remove ../ and ./
        # Use os.path.normpath to normalize, then convert back to Path
        resolved_path = Path(os.path.normpath(path.absolute()))

        # Optional: Validate existence
        if validate_exists and not resolved_path.exists():
            raise FileNotFoundError(f"Path does not exist: {resolved_path}")

        return resolved_path

    def check_path_exists(self, path: Path) -> bool:
        """Check if a path exists on the filesystem.

        Args:
            path: Path to check

        Returns:
            True if path exists, False otherwise
        """
        return path.exists()

    def is_symlink(self, path: Path) -> bool:
        """Check if a path is a symbolic link.

        Args:
            path: Path to check

        Returns:
            True if path is a symlink, False otherwise
        """
        return path.is_symlink()


def detect_circular_reference(
    filelist_path: Path,
    visited: set[Path],
    recursion_stack: set[Path]
) -> None:
    """Detect circular references in filelist hierarchy using DFS.

    This is a utility function for circular reference detection.
    The actual detection is integrated into the parser using ResolutionContext.

    Args:
        filelist_path: Path to check
        visited: Set of already processed filelists
        recursion_stack: Set of filelists currently in the recursion stack

    Raises:
        CircularReferenceError: If circular reference detected
    """
    # Resolve path for comparison (following symlinks for circular detection)
    resolved = filelist_path.resolve()

    # Check if we're in a cycle
    if resolved in recursion_stack:
        raise CircularReferenceError(
            f"Circular reference detected: {filelist_path}"
        )

    # Already visited this branch
    if resolved in visited:
        return

    # This would be called recursively for nested filelists
    # The actual implementation is in the parser
