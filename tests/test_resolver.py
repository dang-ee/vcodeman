"""Tests for path resolution functionality."""

import pytest
import os
from pathlib import Path

from vcodeman.resolver import PathResolver, UndefinedVariableError


def test_resolve_env_var(tmp_path):
    """Test environment variable expansion with $VAR syntax."""
    resolver = PathResolver()

    # Set test environment variable
    os.environ['TEST_VAR'] = '/test/path'

    resolved = resolver.resolve_path('$TEST_VAR/file.v', tmp_path)

    assert '/test/path/file.v' in str(resolved)
    assert resolved.is_absolute()


def test_resolve_env_var_braces(tmp_path):
    """Test environment variable expansion with ${VAR} syntax."""
    resolver = PathResolver()

    # Set test environment variable
    os.environ['TEST_ROOT'] = '/root/dir'

    resolved = resolver.resolve_path('${TEST_ROOT}/design.v', tmp_path)

    assert '/root/dir/design.v' in str(resolved)
    assert resolved.is_absolute()


def test_undefined_env_var(tmp_path):
    """Test that undefined variables raise error in strict mode."""
    resolver = PathResolver(strict_env_vars=True)

    # Ensure variable is not set
    if 'UNDEFINED_TEST_VAR' in os.environ:
        del os.environ['UNDEFINED_TEST_VAR']

    with pytest.raises(UndefinedVariableError):
        resolver.resolve_path('$UNDEFINED_TEST_VAR/file.v', tmp_path)


def test_resolve_relative_parent(tmp_path):
    """Test relative path resolution with ../ syntax."""
    resolver = PathResolver()

    # Create directory structure
    subdir = tmp_path / "subdir"
    subdir.mkdir()

    resolved = resolver.resolve_path('../common/utils.v', subdir)

    assert resolved.is_absolute()
    expected = tmp_path / "common" / "utils.v"
    assert resolved == expected.absolute()


def test_resolve_relative_current(tmp_path):
    """Test relative path resolution with ./ syntax."""
    resolver = PathResolver()

    subdir = tmp_path / "subdir"
    subdir.mkdir()

    resolved = resolver.resolve_path('./local/file.v', subdir)

    assert resolved.is_absolute()
    expected = subdir / "local" / "file.v"
    assert resolved == expected.absolute()


def test_nested_relative(tmp_path):
    """Test that nested filelists resolve relative to their own directory."""
    resolver = PathResolver()

    # Create directory structure
    root_dir = tmp_path / "root"
    nested_dir = tmp_path / "root" / "nested"
    root_dir.mkdir()
    nested_dir.mkdir()

    # From nested directory, resolve relative path
    resolved = resolver.resolve_path('../common/file.v', nested_dir)

    expected = root_dir / "common" / "file.v"
    assert resolved == expected.absolute()
