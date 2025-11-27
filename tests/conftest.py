"""pytest configuration and fixtures for vcodeman tests."""

import pytest
from pathlib import Path
from click.testing import CliRunner
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from vcodeman.models import Base


@pytest.fixture(scope="session")
def db_engine():
    """Session-scoped in-memory SQLite engine."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Function-scoped database session with transaction rollback."""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def cli_runner():
    """Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def test_filelists(tmp_path):
    """Create test filelist directory structure with common test files."""
    filelist_dir = tmp_path / "filelists"
    filelist_dir.mkdir()

    # Create a simple test filelist
    (filelist_dir / "simple.f").write_text(
        "# Simple filelist\n"
        "file1.v\n"
        "file2.v\n"
    )

    # Create nested structure
    # Use -F (uppercase) to resolve relative to filelist directory
    (filelist_dir / "nested_root.f").write_text(
        "# Root filelist\n"
        "-F nested_level1.f\n"
        "root_file.v\n"
    )

    (filelist_dir / "nested_level1.f").write_text(
        "# Level 1 filelist\n"
        "level1_file.v\n"
    )

    # Create circular reference test files
    # Use -F to resolve relative to filelist directory
    (filelist_dir / "circular_a.f").write_text(
        "# Circular reference test - A references B\n"
        "-F circular_b.f\n"
        "file_a.v\n"
    )

    (filelist_dir / "circular_b.f").write_text(
        "# Circular reference test - B references A\n"
        "-F circular_a.f\n"
        "file_b.v\n"
    )

    return filelist_dir


@pytest.fixture
def temp_filelist(tmp_path):
    """Create a temporary filelist file for testing."""
    def _create_filelist(content: str, filename: str = "test.f") -> Path:
        filelist = tmp_path / filename
        filelist.write_text(content)
        return filelist
    return _create_filelist
