"""Verilog-XL filelist parser using Lark.

Implements parsing and flattening of nested filelists with path resolution.
"""

import os
from pathlib import Path
from typing import Optional, List

from lark import Lark, Transformer, Token, Tree
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from vcodeman.models import (
    Base,
    Filelist,
    FileEntry,
    LibraryDirectory,
    LibraryFile,
    IncludeDirectory,
    MacroDefinition,
    LibraryExtension,
    LineItem,
    ParsedFilelist,
    ResolutionContext,
)
from vcodeman.resolver import PathResolver, CircularReferenceError


class FilelistTransformer(Transformer):
    """Transform Lark parse tree into structured data."""

    def __init__(
        self,
        session: Session,
        current_filelist: Filelist,
        resolver: PathResolver,
        base_dir: Path,
        cwd: Path,
        line_offset: int = 0,
        track_lines: bool = True
    ):
        """Initialize transformer.

        Args:
            session: SQLAlchemy session
            current_filelist: Current filelist being processed
            resolver: PathResolver instance
            base_dir: Base directory for relative paths (for -F option)
            cwd: Current working directory (for -f option)
            line_offset: Line number offset for tracking
            track_lines: Whether to track line items for output
        """
        super().__init__()
        self.session = session
        self.current_filelist = current_filelist
        self.resolver = resolver
        self.base_dir = base_dir
        self.cwd = cwd
        self.line_offset = line_offset
        self._line_number = 1
        self.track_lines = track_lines

    def start(self, items):
        """Start rule - return all processed items."""
        return items

    def line(self, items):
        """Process a single line."""
        self._line_number += 1
        return items[0] if items else None

    def include_file(self, items):
        """Process -f option. Token format: '-f path'

        -f resolves paths relative to cwd (current working directory).
        """
        token = str(items[0])
        # Extract path from "-f path" or "-f\tpath"
        path = token[2:].strip()
        original_text = token.strip()

        if self.track_lines:
            # -f: resolve relative to cwd
            resolved_path = self.resolver.resolve_path(path, self.cwd)
            line_item = LineItem(
                filelist_id=self.current_filelist.id,
                line_number=self._line_number,
                item_type="include_f",
                original_text=original_text,
                resolved_text=f"-f {path}",
                include_path=str(resolved_path)
            )
            self.session.add(line_item)

        return ("include_file", path, self._line_number, original_text)

    def include_file_caps(self, items):
        """Process -F option. Token format: '-F path'

        -F resolves paths relative to parent filelist directory.
        """
        token = str(items[0])
        path = token[2:].strip()
        original_text = token.strip()

        if self.track_lines:
            # -F: resolve relative to parent filelist directory
            resolved_path = self.resolver.resolve_path(path, self.base_dir)
            line_item = LineItem(
                filelist_id=self.current_filelist.id,
                line_number=self._line_number,
                item_type="include_f",
                original_text=original_text,
                resolved_text=f"-F {path}",
                include_path=str(resolved_path)
            )
            self.session.add(line_item)

        return ("include_file_caps", path, self._line_number, original_text)

    def library_dir(self, items):
        """Process -y option. Token format: '-y path'"""
        token = str(items[0])
        original_path = token[2:].strip()
        original_text = token.strip()
        resolved_path = self.resolver.resolve_path(original_path, self.base_dir)

        lib_dir = LibraryDirectory(
            filelist_id=self.current_filelist.id,
            dirpath=str(resolved_path),
            original_path=original_path,
            line_number=self._line_number,
            exists=resolved_path.exists()
        )
        self.session.add(lib_dir)

        if self.track_lines:
            line_item = LineItem(
                filelist_id=self.current_filelist.id,
                line_number=self._line_number,
                item_type="lib_dir",
                original_text=original_text,
                resolved_text=original_text
            )
            self.session.add(line_item)

        return lib_dir

    def library_file(self, items):
        """Process -v option. Token format: '-v path'"""
        token = str(items[0])
        original_path = token[2:].strip()
        original_text = token.strip()
        resolved_path = self.resolver.resolve_path(original_path, self.base_dir)

        lib_file = LibraryFile(
            filelist_id=self.current_filelist.id,
            filepath=str(resolved_path),
            original_path=original_path,
            line_number=self._line_number,
            exists=resolved_path.exists()
        )
        self.session.add(lib_file)

        if self.track_lines:
            line_item = LineItem(
                filelist_id=self.current_filelist.id,
                line_number=self._line_number,
                item_type="lib_file",
                original_text=original_text,
                resolved_text=original_text
            )
            self.session.add(line_item)

        return lib_file

    def include_directive(self, items):
        """Process +incdir+ option. Token format: '+incdir+path1+path2+...'"""
        token = str(items[0])
        original_text = token.strip()
        # Remove '+incdir+' prefix and split by '+'
        paths_str = token[8:]  # len('+incdir+') = 8
        path_list = paths_str.split('+')

        include_dirs = []
        resolved_paths = []
        for position, path_str in enumerate(path_list):
            if not path_str:
                continue
            resolved_path = self.resolver.resolve_path(path_str, self.base_dir)
            inc_dir = IncludeDirectory(
                filelist_id=self.current_filelist.id,
                dirpath=str(resolved_path),
                original_path=path_str,
                line_number=self._line_number,
                position=position,
                exists=resolved_path.exists()
            )
            self.session.add(inc_dir)
            include_dirs.append(inc_dir)
            resolved_paths.append(str(resolved_path))

        if self.track_lines:
            # Build resolved text with absolute paths
            resolved_text = "+incdir+" + "+".join(resolved_paths) if resolved_paths else original_text
            line_item = LineItem(
                filelist_id=self.current_filelist.id,
                line_number=self._line_number,
                item_type="incdir",
                original_text=original_text,
                resolved_text=resolved_text
            )
            self.session.add(line_item)

        return include_dirs

    def define_directive(self, items):
        """Process +define+ option. Token format: '+define+MACRO1+MACRO2=value+...'"""
        token = str(items[0])
        original_text = token.strip()
        # Remove '+define+' prefix and split by '+'
        macros_str = token[8:]  # len('+define+') = 8
        macro_parts = macros_str.split('+')

        macros = []
        for macro_part in macro_parts:
            if not macro_part:
                continue
            # Parse NAME=VALUE or just NAME
            if '=' in macro_part:
                name, value = macro_part.split('=', 1)
            else:
                name, value = macro_part, None

            macro_def = MacroDefinition(
                filelist_id=self.current_filelist.id,
                name=name,
                value=value,
                line_number=self._line_number,
                original_text=macro_part
            )
            self.session.add(macro_def)
            macros.append(macro_def)

        if self.track_lines:
            line_item = LineItem(
                filelist_id=self.current_filelist.id,
                line_number=self._line_number,
                item_type="define",
                original_text=original_text,
                resolved_text=original_text
            )
            self.session.add(line_item)

        return macros

    def libext_directive(self, items):
        """Process +libext+ option. Token format: '+libext+.v+.sv+...'"""
        token = str(items[0])
        original_text = token.strip()
        # Remove '+libext+' prefix and split by '+'
        exts_str = token[8:]  # len('+libext+') = 8
        ext_list = exts_str.split('+')

        extensions = []
        for position, ext in enumerate(ext_list):
            if not ext:
                continue
            # Ensure extension starts with dot
            if not ext.startswith('.'):
                ext = '.' + ext
            lib_ext = LibraryExtension(
                filelist_id=self.current_filelist.id,
                extension=ext,
                line_number=self._line_number,
                position=position
            )
            self.session.add(lib_ext)
            extensions.append(lib_ext)

        if self.track_lines:
            line_item = LineItem(
                filelist_id=self.current_filelist.id,
                line_number=self._line_number,
                item_type="libext",
                original_text=original_text,
                resolved_text=original_text
            )
            self.session.add(line_item)

        return extensions

    def file_path(self, items):
        """Process a regular file path."""
        path_token = items[0]
        original_path = str(path_token)
        resolved_path = self.resolver.resolve_path(original_path, self.base_dir)

        file_entry = FileEntry(
            filelist_id=self.current_filelist.id,
            filepath=str(resolved_path),
            original_path=original_path,
            line_number=self._line_number,
            exists=resolved_path.exists(),
            is_library=False
        )
        self.session.add(file_entry)

        if self.track_lines:
            line_item = LineItem(
                filelist_id=self.current_filelist.id,
                line_number=self._line_number,
                item_type="file",
                original_text=original_path,
                resolved_text=str(resolved_path)  # Use absolute path for files
            )
            self.session.add(line_item)

        return file_entry

    def comment(self, items):
        """Process a comment."""
        comment_text = str(items[0])

        if self.track_lines:
            # Convert # comments to // # format
            if comment_text.startswith('#'):
                resolved_text = f"// {comment_text}"
            elif comment_text.startswith('//'):
                resolved_text = comment_text
            else:
                resolved_text = f"// {comment_text}"

            line_item = LineItem(
                filelist_id=self.current_filelist.id,
                line_number=self._line_number,
                item_type="comment",
                original_text=comment_text,
                resolved_text=resolved_text
            )
            self.session.add(line_item)

        return ("comment", comment_text, self._line_number)

    def NEWLINE(self, token):
        """Track line numbers."""
        self._line_number += 1
        return None


class FilelistParser:
    """Parser for Verilog-XL format filelists."""

    def __init__(self, strict_env_vars: bool = False):
        """Initialize parser.

        Args:
            strict_env_vars: If True, fail on undefined environment variables
        """
        self.strict_env_vars = strict_env_vars
        self.resolver = PathResolver(strict_env_vars=strict_env_vars)

        # Load grammar
        grammar_path = Path(__file__).parent / "grammar.lark"
        with open(grammar_path, 'r') as f:
            grammar_text = f.read()

        self.lark_parser = Lark(
            grammar_text,
            parser='lalr',
            start='start',
            propagate_positions=True
        )

    def parse(
        self,
        filelist_path: Path,
        preserve_comments: bool = True,
        validate_files: bool = False
    ) -> ParsedFilelist:
        """Parse a Verilog-XL filelist and return structured data model.

        Args:
            filelist_path: Absolute path to root filelist
            preserve_comments: Whether to preserve comments in output
            validate_files: Whether to validate file existence

        Returns:
            ParsedFilelist with all resolved paths and parsed options

        Raises:
            CircularReferenceError: If circular filelist references detected
            UndefinedVariableError: If environment variable not found
            FileNotFoundError: If filelist file doesn't exist
            ParseError: If syntax errors in filelist
        """
        # Create in-memory database
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()

        try:
            # Create root ParsedFilelist
            parsed_result = ParsedFilelist(
                root_filepath=str(filelist_path.absolute())
            )
            session.add(parsed_result)
            session.commit()

            # Create resolution context
            context = ResolutionContext(
                base_dir=filelist_path.parent,
                strict_env_vars=self.strict_env_vars
            )

            # Parse root filelist
            self._parse_filelist_recursive(
                session=session,
                filelist_path=filelist_path,
                context=context,
                parent_filelist=None,
                nesting_level=0,
                line_number=0,
                preserve_comments=preserve_comments
            )

            session.commit()

            # Collect all parsed data while session is still open
            parsed_data = self._collect_parsed_data(session)
            parsed_result.set_parsed_data(parsed_data)

            # Expunge the object from the session so it can be used after session closes
            # Access attributes to force loading before detaching
            _ = parsed_result.id
            _ = parsed_result.root_filepath
            _ = parsed_result.timestamp
            _ = parsed_result.warnings
            _ = parsed_result.errors

            session.expunge(parsed_result)

            return parsed_result

        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    def _collect_parsed_data(self, session: Session) -> dict:
        """Collect all parsed data from session before closing.

        Args:
            session: SQLAlchemy session with parsed data

        Returns:
            Dictionary containing all filelists, files, and options
        """
        from vcodeman.models import (
            Filelist, FileEntry, LibraryDirectory, LibraryFile,
            IncludeDirectory, MacroDefinition, LibraryExtension, LineItem
        )

        # Query all filelists
        filelists = session.query(Filelist).order_by(Filelist.id).all()

        # Build hierarchical structure
        filelists_data = []
        all_files = []

        # Build a map of filelist_id to filepath for quick lookup
        filelist_map = {fl.id: fl.filepath for fl in filelists}

        for fl in filelists:
            fl_data = {
                "id": fl.id,
                "filepath": fl.filepath,
                "parent_id": fl.parent_id,
                "nesting_level": fl.nesting_level,
                "exists": fl.exists,
                "files": [],
                "library_dirs": [],
                "library_files": [],
                "include_dirs": [],
                "defines": [],
                "lib_extensions": [],
                "line_items": [],  # Ordered line items for flattened output
            }

            # Collect file entries
            for fe in fl.file_entries:
                file_data = {
                    "filepath": fe.filepath,
                    "original_path": fe.original_path,
                    "line_number": fe.line_number,
                    "exists": fe.exists,
                }
                fl_data["files"].append(file_data)
                all_files.append(fe.filepath)

            # Collect library directories (-y)
            for ld in fl.library_directories:
                fl_data["library_dirs"].append({
                    "path": ld.dirpath,
                    "original_path": ld.original_path,
                    "line_number": ld.line_number,
                })

            # Collect library files (-v)
            for lf in fl.library_files:
                fl_data["library_files"].append({
                    "path": lf.filepath,
                    "original_path": lf.original_path,
                    "line_number": lf.line_number,
                })

            # Collect include directories (+incdir+)
            for id_ in fl.include_directories:
                fl_data["include_dirs"].append({
                    "path": id_.dirpath,
                    "original_path": id_.original_path,
                    "line_number": id_.line_number,
                })

            # Collect macro definitions (+define+)
            for md in fl.macro_definitions:
                fl_data["defines"].append({
                    "name": md.name,
                    "value": md.value,
                    "line_number": md.line_number,
                })

            # Collect library extensions (+libext+)
            for le in fl.library_extensions:
                fl_data["lib_extensions"].append({
                    "extension": le.extension,
                    "line_number": le.line_number,
                })

            # Collect line items (ordered by line number)
            for li in sorted(fl.line_items, key=lambda x: x.line_number):
                fl_data["line_items"].append({
                    "line_number": li.line_number,
                    "item_type": li.item_type,
                    "original_text": li.original_text,
                    "resolved_text": li.resolved_text,
                    "include_path": li.include_path,
                })

            filelists_data.append(fl_data)

        return {
            "filelists": filelists_data,
            "all_files": all_files,
            "total_files": len(all_files),
            "total_filelists": len(filelists_data),
        }

    def _parse_filelist_recursive(
        self,
        session: Session,
        filelist_path: Path,
        context: ResolutionContext,
        parent_filelist: Optional[Filelist],
        nesting_level: int,
        line_number: int,
        preserve_comments: bool
    ) -> Filelist:
        """Recursively parse a filelist and its nested includes.

        Args:
            session: SQLAlchemy session
            filelist_path: Path to filelist file
            context: Resolution context
            parent_filelist: Parent filelist (None for root)
            nesting_level: Current nesting depth
            line_number: Line number where referenced in parent
            preserve_comments: Whether to preserve comments

        Returns:
            Filelist object

        Raises:
            CircularReferenceError: If circular reference detected
            FileNotFoundError: If filelist doesn't exist
        """
        # Resolve path - normalize to match nested path resolution
        resolved_path = Path(os.path.normpath(filelist_path.absolute()))

        # Check for circular reference
        if context.is_circular(resolved_path):
            raise CircularReferenceError(
                f"Circular reference detected: {resolved_path}"
            )

        # Check if already visited (but not circular)
        if context.was_visited(resolved_path):
            # Already processed in another branch, skip
            return None

        # Mark as being processed
        context.enter_filelist(resolved_path)

        try:
            # Create Filelist entry
            filelist = Filelist(
                filepath=str(resolved_path),
                parent_id=parent_filelist.id if parent_filelist else None,
                line_number=line_number if parent_filelist else None,
                nesting_level=nesting_level,
                exists=resolved_path.exists()
            )
            session.add(filelist)
            session.flush()  # Get ID for relationships

            # Read and parse filelist content
            if not resolved_path.exists():
                # Mark as not existing and return
                filelist.exists = False
                return filelist

            with open(resolved_path, 'r') as f:
                content = f.read()

            # Parse with Lark
            tree = self.lark_parser.parse(content)

            # Transform parse tree
            transformer = FilelistTransformer(
                session=session,
                current_filelist=filelist,
                resolver=self.resolver,
                base_dir=resolved_path.parent,
                cwd=context.cwd,
                line_offset=0
            )

            transformed = transformer.transform(tree)

            # Process nested includes
            for item in transformed:
                if isinstance(item, tuple) and item[0] in ("include_file", "include_file_caps"):
                    include_type, nested_path_str, nested_line, _ = item

                    # -f: resolve relative to cwd (current working directory)
                    # -F: resolve relative to parent filelist directory
                    if include_type == "include_file":
                        # -f option: resolve relative to cwd
                        base_dir = context.cwd
                    else:
                        # -F option: resolve relative to parent filelist directory
                        base_dir = resolved_path.parent

                    nested_path = self.resolver.resolve_path(
                        nested_path_str,
                        base_dir
                    )

                    # Recursively parse nested filelist
                    self._parse_filelist_recursive(
                        session=session,
                        filelist_path=nested_path,
                        context=context,
                        parent_filelist=filelist,
                        nesting_level=nesting_level + 1,
                        line_number=nested_line,
                        preserve_comments=preserve_comments
                    )

            return filelist

        finally:
            # Mark as completed
            context.exit_filelist(resolved_path)
