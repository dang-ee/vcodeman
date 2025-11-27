"""Tests for SQLAlchemy data models."""

import pytest
from pathlib import Path

from vcodeman.models import (
    Filelist,
    FileEntry,
    LibraryDirectory,
    ParsedFilelist,
)


def test_models_relationships(db_session):
    """Test Filelist to FileEntry relationship."""
    # Create a filelist
    filelist = Filelist(
        filepath="/test/design.f",
        nesting_level=0,
        exists=True
    )
    db_session.add(filelist)
    db_session.flush()

    # Add file entries
    file1 = FileEntry(
        filelist_id=filelist.id,
        filepath="/test/file1.v",
        original_path="file1.v",
        line_number=1,
        exists=True
    )
    file2 = FileEntry(
        filelist_id=filelist.id,
        filepath="/test/file2.v",
        original_path="file2.v",
        line_number=2,
        exists=True
    )
    db_session.add_all([file1, file2])
    db_session.commit()

    # Verify relationship
    assert len(filelist.file_entries) == 2
    assert filelist.file_entries[0].filepath == "/test/file1.v"


def test_models_hierarchy(db_session):
    """Test parent-child filelist relationships."""
    # Create root filelist
    root = Filelist(
        filepath="/test/root.f",
        nesting_level=0,
        exists=True
    )
    db_session.add(root)
    db_session.flush()

    # Create child filelist
    child = Filelist(
        filepath="/test/child.f",
        parent_id=root.id,
        line_number=1,
        nesting_level=1,
        exists=True
    )
    db_session.add(child)
    db_session.commit()

    # Verify hierarchy
    assert len(root.children) == 1
    assert root.children[0].filepath == "/test/child.f"
    assert child.parent.filepath == "/test/root.f"


def test_query_by_type(db_session):
    """Test filtering files by type."""
    filelist = Filelist(
        filepath="/test/design.f",
        nesting_level=0,
        exists=True
    )
    db_session.add(filelist)
    db_session.flush()

    # Add different types
    source_file = FileEntry(
        filelist_id=filelist.id,
        filepath="/test/design.v",
        original_path="design.v",
        line_number=1,
        exists=True,
        is_library=False
    )
    lib_file = FileEntry(
        filelist_id=filelist.id,
        filepath="/test/lib.v",
        original_path="lib.v",
        line_number=2,
        exists=True,
        is_library=True
    )
    db_session.add_all([source_file, lib_file])
    db_session.commit()

    # Query by type
    source_files = db_session.query(FileEntry).filter_by(
        filelist_id=filelist.id,
        is_library=False
    ).all()
    assert len(source_files) == 1
    assert source_files[0].filepath == "/test/design.v"


def test_query_by_source(db_session):
    """Test querying by source filelist."""
    root = Filelist(
        filepath="/test/root.f",
        nesting_level=0,
        exists=True
    )
    db_session.add(root)
    db_session.flush()

    # Add files to specific filelist
    file1 = FileEntry(
        filelist_id=root.id,
        filepath="/test/file1.v",
        original_path="file1.v",
        line_number=1,
        exists=True
    )
    db_session.add(file1)
    db_session.commit()

    # Query files from specific filelist
    files = db_session.query(FileEntry).filter_by(
        filelist_id=root.id
    ).all()
    assert len(files) == 1


def test_serialization(db_session):
    """Test JSON serialization/deserialization."""
    parsed = ParsedFilelist(
        root_filepath="/test/design.f"
    )
    db_session.add(parsed)
    db_session.commit()

    # Test to_dict
    data = parsed.to_dict()
    assert data['root_filepath'] == "/test/design.f"
    assert 'timestamp' in data
    assert 'warnings' in data
    assert 'errors' in data

    # Test warnings/errors
    parsed.add_warning("Test warning")
    parsed.add_error("Test error")
    db_session.commit()

    warnings = parsed.get_warnings()
    errors = parsed.get_errors()
    assert len(warnings) == 1
    assert len(errors) == 1
    assert warnings[0] == "Test warning"
    assert errors[0] == "Test error"
