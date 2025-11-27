"""SQLAlchemy data models for Verilog-XL filelist parsing.

Based on adjacency list pattern for hierarchical data as specified in research.md.
"""

from typing import Optional, List
from pathlib import Path
import json
from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


class Filelist(Base):
    """Represents a filelist file in the hierarchy.

    Attributes:
        id: Primary key
        filepath: Absolute path to the filelist file
        parent_id: Reference to parent filelist (for nested includes)
        line_number: Line number in parent filelist where this was referenced
        nesting_level: Depth in the hierarchy (0 for root)
        exists: Whether the filelist file exists on filesystem
    """
    __tablename__ = "filelist"

    id: Mapped[int] = mapped_column(primary_key=True)
    filepath: Mapped[str] = mapped_column(String, nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("filelist.id"))
    line_number: Mapped[Optional[int]] = mapped_column(Integer)
    nesting_level: Mapped[int] = mapped_column(Integer, default=0)
    exists: Mapped[bool] = mapped_column(Boolean, default=True)

    # Self-referential relationship for nested filelists
    children: Mapped[List["Filelist"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="select",
        join_depth=10  # Support up to 10 levels of nesting
    )

    parent: Mapped[Optional["Filelist"]] = relationship(
        back_populates="children",
        remote_side=[id],
        lazy="joined"
    )

    # One-to-many relationships to parsed items
    file_entries: Mapped[List["FileEntry"]] = relationship(
        back_populates="filelist",
        cascade="all, delete-orphan",
        lazy="select"
    )

    library_directories: Mapped[List["LibraryDirectory"]] = relationship(
        back_populates="filelist",
        cascade="all, delete-orphan",
        lazy="select"
    )

    library_files: Mapped[List["LibraryFile"]] = relationship(
        back_populates="filelist",
        cascade="all, delete-orphan",
        lazy="select"
    )

    include_directories: Mapped[List["IncludeDirectory"]] = relationship(
        back_populates="filelist",
        cascade="all, delete-orphan",
        lazy="select"
    )

    macro_definitions: Mapped[List["MacroDefinition"]] = relationship(
        back_populates="filelist",
        cascade="all, delete-orphan",
        lazy="select"
    )

    library_extensions: Mapped[List["LibraryExtension"]] = relationship(
        back_populates="filelist",
        cascade="all, delete-orphan",
        lazy="select"
    )

    line_items: Mapped[List["LineItem"]] = relationship(
        back_populates="filelist",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="LineItem.line_number"
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "filepath": self.filepath,
            "parent_id": self.parent_id,
            "line_number": self.line_number,
            "nesting_level": self.nesting_level,
            "exists": self.exists,
        }


class FileEntry(Base):
    """Represents a source or library file referenced in a filelist.

    Attributes:
        id: Primary key
        filelist_id: Reference to parent filelist
        filepath: Absolute path to the file
        original_path: Original path string before resolution
        line_number: Line number in filelist
        exists: Whether the file exists on filesystem
        is_library: Whether this is a library file
    """
    __tablename__ = "file_entry"

    id: Mapped[int] = mapped_column(primary_key=True)
    filelist_id: Mapped[int] = mapped_column(ForeignKey("filelist.id"), nullable=False)
    filepath: Mapped[str] = mapped_column(String, nullable=False)
    original_path: Mapped[str] = mapped_column(String, nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    exists: Mapped[bool] = mapped_column(Boolean, default=True)
    is_library: Mapped[bool] = mapped_column(Boolean, default=False)

    filelist: Mapped["Filelist"] = relationship(back_populates="file_entries")

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "filelist_id": self.filelist_id,
            "filepath": self.filepath,
            "original_path": self.original_path,
            "line_number": self.line_number,
            "exists": self.exists,
            "is_library": self.is_library,
        }


class LibraryDirectory(Base):
    """Represents a library search directory (-y option).

    Attributes:
        id: Primary key
        filelist_id: Reference to parent filelist
        dirpath: Absolute path to the directory
        original_path: Original path string before resolution
        line_number: Line number in filelist
        exists: Whether the directory exists
    """
    __tablename__ = "library_directory"

    id: Mapped[int] = mapped_column(primary_key=True)
    filelist_id: Mapped[int] = mapped_column(ForeignKey("filelist.id"), nullable=False)
    dirpath: Mapped[str] = mapped_column(String, nullable=False)
    original_path: Mapped[str] = mapped_column(String, nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    exists: Mapped[bool] = mapped_column(Boolean, default=True)

    filelist: Mapped["Filelist"] = relationship(back_populates="library_directories")

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "filelist_id": self.filelist_id,
            "dirpath": self.dirpath,
            "original_path": self.original_path,
            "line_number": self.line_number,
            "exists": self.exists,
        }


class LibraryFile(Base):
    """Represents a library file (-v option).

    Attributes:
        id: Primary key
        filelist_id: Reference to parent filelist
        filepath: Absolute path to the library file
        original_path: Original path string before resolution
        line_number: Line number in filelist
        exists: Whether the file exists
    """
    __tablename__ = "library_file"

    id: Mapped[int] = mapped_column(primary_key=True)
    filelist_id: Mapped[int] = mapped_column(ForeignKey("filelist.id"), nullable=False)
    filepath: Mapped[str] = mapped_column(String, nullable=False)
    original_path: Mapped[str] = mapped_column(String, nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    exists: Mapped[bool] = mapped_column(Boolean, default=True)

    filelist: Mapped["Filelist"] = relationship(back_populates="library_files")

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "filelist_id": self.filelist_id,
            "filepath": self.filepath,
            "original_path": self.original_path,
            "line_number": self.line_number,
            "exists": self.exists,
        }


class IncludeDirectory(Base):
    """Represents an include directory (+incdir+ option).

    Attributes:
        id: Primary key
        filelist_id: Reference to parent filelist
        dirpath: Absolute path to the include directory
        original_path: Original path string before resolution
        line_number: Line number in filelist
        position: Position in the include path list
        exists: Whether the directory exists
    """
    __tablename__ = "include_directory"

    id: Mapped[int] = mapped_column(primary_key=True)
    filelist_id: Mapped[int] = mapped_column(ForeignKey("filelist.id"), nullable=False)
    dirpath: Mapped[str] = mapped_column(String, nullable=False)
    original_path: Mapped[str] = mapped_column(String, nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    exists: Mapped[bool] = mapped_column(Boolean, default=True)

    filelist: Mapped["Filelist"] = relationship(back_populates="include_directories")

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "filelist_id": self.filelist_id,
            "dirpath": self.dirpath,
            "original_path": self.original_path,
            "line_number": self.line_number,
            "position": self.position,
            "exists": self.exists,
        }


class MacroDefinition(Base):
    """Represents a macro definition (+define+ option).

    Attributes:
        id: Primary key
        filelist_id: Reference to parent filelist
        name: Macro name
        value: Optional macro value
        line_number: Line number in filelist
        original_text: Original definition text
    """
    __tablename__ = "macro_definition"

    id: Mapped[int] = mapped_column(primary_key=True)
    filelist_id: Mapped[int] = mapped_column(ForeignKey("filelist.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[Optional[str]] = mapped_column(String)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    original_text: Mapped[str] = mapped_column(String, nullable=False)

    filelist: Mapped["Filelist"] = relationship(back_populates="macro_definitions")

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "filelist_id": self.filelist_id,
            "name": self.name,
            "value": self.value,
            "line_number": self.line_number,
            "original_text": self.original_text,
        }


class LibraryExtension(Base):
    """Represents a library file extension (+libext+ option).

    Attributes:
        id: Primary key
        filelist_id: Reference to parent filelist
        extension: File extension (e.g., ".v", ".sv")
        line_number: Line number in filelist
        position: Position in the extension list
    """
    __tablename__ = "library_extension"

    id: Mapped[int] = mapped_column(primary_key=True)
    filelist_id: Mapped[int] = mapped_column(ForeignKey("filelist.id"), nullable=False)
    extension: Mapped[str] = mapped_column(String, nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    filelist: Mapped["Filelist"] = relationship(back_populates="library_extensions")

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "filelist_id": self.filelist_id,
            "extension": self.extension,
            "line_number": self.line_number,
            "position": self.position,
        }


class ParsedFilelist(Base):
    """Root aggregate representing a complete parsed filelist structure.

    Attributes:
        id: Primary key
        root_filepath: Absolute path to the root filelist
        timestamp: When the parsing occurred
        warnings: List of warning messages
        errors: List of error messages
    """
    __tablename__ = "parsed_filelist"

    id: Mapped[int] = mapped_column(primary_key=True)
    root_filepath: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    warnings: Mapped[Optional[str]] = mapped_column(Text)  # JSON array
    errors: Mapped[Optional[str]] = mapped_column(Text)  # JSON array

    # Allow non-mapped instance attributes
    __allow_unmapped__ = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Non-persisted cache for parsed data (set by parser before session closes)
        self._parsed_data = None

    def set_parsed_data(self, data: dict) -> None:
        """Set the cached parsed data (call before session closes)."""
        self._parsed_data = data

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        warnings_list = json.loads(self.warnings) if self.warnings else []
        warnings_list.append(message)
        self.warnings = json.dumps(warnings_list)

    def add_error(self, message: str) -> None:
        """Add an error message."""
        errors_list = json.loads(self.errors) if self.errors else []
        errors_list.append(message)
        self.errors = json.dumps(errors_list)

    def get_warnings(self) -> List[str]:
        """Get list of warning messages."""
        return json.loads(self.warnings) if self.warnings else []

    def get_errors(self) -> List[str]:
        """Get list of error messages."""
        return json.loads(self.errors) if self.errors else []

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = {
            "id": self.id,
            "root_filepath": self.root_filepath,
            "timestamp": self.timestamp.isoformat(),
            "warnings": self.get_warnings(),
            "errors": self.get_errors(),
        }
        # Include parsed data if available
        if self._parsed_data:
            result.update(self._parsed_data)
        return result

    def serialize_to_json(self) -> str:
        """Serialize entire model tree to JSON."""
        return json.dumps(self.to_dict(), indent=2)


class LineItem(Base):
    """Represents a single line item in a filelist, preserving original order.

    Attributes:
        id: Primary key
        filelist_id: Reference to parent filelist
        line_number: Line number in filelist (1-based)
        item_type: Type of item (comment, file, option, include, blank)
        original_text: Original line text as written
        resolved_text: Resolved/processed text (for output)
    """
    __tablename__ = "line_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    filelist_id: Mapped[int] = mapped_column(ForeignKey("filelist.id"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    item_type: Mapped[str] = mapped_column(String, nullable=False)  # comment, file, lib_dir, lib_file, incdir, define, libext, include_f, blank
    original_text: Mapped[str] = mapped_column(String, nullable=False)
    resolved_text: Mapped[Optional[str]] = mapped_column(String)  # For include_f, this stores the resolved path
    include_path: Mapped[Optional[str]] = mapped_column(String)  # For include_f items, the path to the nested filelist

    filelist: Mapped["Filelist"] = relationship(back_populates="line_items")

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "line_number": self.line_number,
            "item_type": self.item_type,
            "original_text": self.original_text,
            "resolved_text": self.resolved_text,
            "include_path": self.include_path,
        }


class ResolutionContext:
    """Context for path resolution (not persisted to database).

    Attributes:
        base_dir: Base directory for resolving relative paths
        cwd: Current working directory (for -f option resolution)
        visited: Set of visited filelist paths (for circular detection)
        recursion_stack: Stack for DFS circular detection
        nesting_depth: Current nesting depth
        strict_env_vars: Whether to fail on undefined environment variables
    """

    def __init__(
        self,
        base_dir: Path,
        strict_env_vars: bool = False,
        cwd: Optional[Path] = None
    ):
        self.base_dir = base_dir
        self.cwd = cwd or Path.cwd()
        self.visited: set[Path] = set()
        self.recursion_stack: set[Path] = set()
        self.nesting_depth = 0
        self.strict_env_vars = strict_env_vars

    def enter_filelist(self, filepath: Path) -> None:
        """Mark a filelist as being processed."""
        self.recursion_stack.add(filepath)
        self.nesting_depth += 1

    def exit_filelist(self, filepath: Path) -> None:
        """Mark a filelist as completed."""
        self.recursion_stack.discard(filepath)
        self.visited.add(filepath)
        self.nesting_depth -= 1

    def is_circular(self, filepath: Path) -> bool:
        """Check if processing this filelist would create a circular reference."""
        return filepath in self.recursion_stack

    def was_visited(self, filepath: Path) -> bool:
        """Check if this filelist was already processed."""
        return filepath in self.visited
