# Research: Verilog-XL Filelist Resolver

**Date**: 2025-11-24
**Feature**: 001-filelist-resolver
**Status**: Complete

This document consolidates research findings for the Verilog-XL Filelist Resolver implementation using Python 3.12, Lark parser, SQLAlchemy ORM, Click CLI, and pytest.

---

## 1. Lark Grammar Design

### Decision: LALR Parser with Contextual Lexer

**Chosen Approach**: Use Lark's LALR(1) parser with a contextual lexer for the Verilog-XL filelist grammar.

**Rationale**:
- **Performance**: LALR is fastest parser algorithm (~10x faster than Earley for unambiguous grammars)
- **Error Detection**: Deterministic parser provides clear error messages at parse time
- **Grammar Simplicity**: Verilog-XL filelist syntax is unambiguous and regular, perfect for LALR
- **Maintainability**: LALR grammars are easier to debug and extend than Earley grammars

**Grammar Structure**:
```lark
?start: line+

line: filelist_include
    | library_option
    | include_directive
    | define_directive
    | libext_directive
    | file_path
    | comment
    | NEWLINE

// Filelist includes (-f/-F)
filelist_include: "-f" WS+ PATH -> include_file
                | "-F" WS+ PATH -> include_file_caps

// Library options
library_option: "-y" WS+ PATH -> library_dir
              | "-v" WS+ PATH -> library_file

// Include directories (+incdir+path1+path2+...)
include_directive: "+incdir+" path_list

// Macro definitions (+define+MACRO1+MACRO2=value+...)
define_directive: "+define+" macro_list

// Library extensions (+libext+.v+.sv+...)
libext_directive: "+libext+" ext_list

// Path lists (plus-separated)
path_list: PATH ("+" PATH)*
macro_list: macro ("+" macro)*
ext_list: EXTENSION ("+" EXTENSION)*

macro: NAME ("=" VALUE)?

// File paths and comments
file_path: PATH
comment: COMMENT | LINE_COMMENT

// Terminals
PATH: /[^\s#]+/
NAME: /[A-Z_][A-Z0-9_]*/
VALUE: /[^\s+]+/
EXTENSION: /\.[a-z]+/
COMMENT: /#[^\n]*/
LINE_COMMENT: /\/\/[^\n]*/
WS: /[ \t]+/
NEWLINE: /\r?\n/

%import common.WS
%ignore WS
```

**Error Recovery**: Use Lark's `on_error` callback for custom error messages with line numbers and context.

**Alternatives Considered**:
- **Regex-based parsing**: Rejected due to difficulty maintaining nested structures and poor error messages
- **Earley parser**: Rejected because Verilog-XL syntax is unambiguous (no need for Earley's ambiguity handling)
- **Manual recursive descent**: Rejected due to higher maintenance burden vs Lark's declarative grammar

---

## 2. SQLAlchemy ORM Patterns

### Decision: Adjacency List Pattern with In-Memory SQLite

**Chosen Approach**: Use adjacency list pattern for hierarchical filelists with in-memory SQLite for primary use case, file-based optional.

**Data Model Pattern**:
```python
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class ParsedFilelist(Base):
    __tablename__ = "parsed_filelist"

    id: Mapped[int] = mapped_column(primary_key=True)
    filepath: Mapped[str]
    line_number: Mapped[int]
    resolved_path: Mapped[str | None]
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("parsed_filelist.id"))

    # Self-referential relationship
    children: Mapped[list["ParsedFilelist"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="selectinload",
        join_depth=10  # Support up to 10 levels of nesting
    )

    parent: Mapped["ParsedFilelist | None"] = relationship(
        back_populates="children",
        remote_side=[id],  # Critical for self-referential
        lazy="joined"
    )

    # One-to-many relationships
    file_entries: Mapped[list["FileEntry"]] = relationship(
        back_populates="filelist",
        cascade="all, delete-orphan",
        lazy="selectinload"
    )
```

**Rationale**:
- **Adjacency List**: Best for application-level traversal, simple to implement, good concurrency
- **`back_populates`**: Modern SQLAlchemy 2.0+ best practice (not `backref`)
- **`selectinload` for collections**: Avoids N+1 queries, no row multiplication
- **`joined` for many-to-one**: Minimal overhead for parent access
- **`remote_side=[id]`**: Required for self-referential relationships

**In-Memory vs File-Based**:
- **Default: In-memory** (`sqlite:///:memory:`) - Fast, zero setup, 1.5x faster than file
- **Optional: File-based** with WAL mode for persistence/debugging
- **Performance**: File-based SQLite with optimizations (WAL, cache) is only ~1.5x slower

**Query Optimization**:
```python
# Controlled depth eager loading
stmt = (
    select(ParsedFilelist)
    .where(ParsedFilelist.filepath == root_path)
    .options(selectinload(ParsedFilelist.children))  # Auto-limited by join_depth
    .options(selectinload(ParsedFilelist.file_entries))
)
```

**Session Management for CLI**:
```python
from contextlib import contextmanager

@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

**Alternatives Considered**:
- **Nested Sets**: Rejected - complex writes, poor concurrency
- **Materialized Path**: Rejected - string manipulation overhead, complex queries
- **PostgreSQL**: Rejected - too heavy for a CLI tool, SQLite sufficient

---

## 3. Path Resolution Strategies

### Decision: pathlib.Path + os.path Hybrid Approach

**Chosen Approach**: Use `pathlib.Path` for OOP API with `os.path` for specific operations (env var expansion, normalization).

**Path Resolution Algorithm**:
```python
from pathlib import Path
import os

def resolve_path(path_str: str, base_dir: Path, strict_env: bool = False) -> Path:
    """Resolve Verilog-XL path to absolute path."""
    # 1. Expand environment variables
    expanded = os.path.expandvars(path_str)

    # Check for undefined variables if strict mode
    if strict_env and '$' in expanded:
        raise ValueError(f"Undefined env var in: {path_str}")

    # 2. Convert to Path object
    path = Path(expanded)

    # 3. Make absolute relative to base directory
    if not path.is_absolute():
        path = base_dir / path

    # 4. Use absolute() to preserve symlinks (NOT resolve())
    return path.absolute()
```

**Rationale**:
- **`pathlib.Path`**: Clean OOP API, automatic Unix path handling
- **`os.path.expandvars()`**: Built-in env var expansion, handles both `$VAR` and `${VAR}`
- **`Path.absolute()`**: Converts to absolute WITHOUT following symlinks (as required)
- **NOT `Path.resolve()`**: Would follow symlinks, violating requirements

**Environment Variable Expansion**:
```python
import os
import re

def expand_env_strict(path_str: str) -> str:
    """Expand with validation for undefined variables."""
    var_pattern = re.compile(r'\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?')

    # Check all variables are defined
    for match in var_pattern.finditer(path_str):
        var_name = match.group(1)
        if var_name not in os.environ:
            raise ValueError(f"Undefined variable: ${var_name}")

    return os.path.expandvars(path_str)
```

**Circular Reference Detection**:
```python
def detect_circular(filelist: Path, visited: set, rec_stack: set) -> None:
    """DFS with visited set + recursion stack."""
    filelist = filelist.resolve()

    if filelist in rec_stack:
        raise CircularReferenceError(f"Cycle detected: {filelist}")

    if filelist in visited:
        return

    rec_stack.add(filelist)
    try:
        for nested in parse_includes(filelist):
            detect_circular(nested, visited, rec_stack)
    finally:
        rec_stack.remove(filelist)
        visited.add(filelist)
```

**Rationale**: O(V+E) time complexity, detects all cycles, maintains path for error messages.

**Symbolic Link Handling**:
```python
# Detect but don't follow
if path.is_symlink():
    logger.warning(f"Symbolic link detected: {path}")

# Use absolute() NOT resolve() to preserve symlinks
return path.absolute()
```

**Alternatives Considered**:
- **Pure `pathlib`**: Rejected - no env var expansion, `resolve()` follows symlinks
- **Pure `os.path`**: Rejected - string-based API is less maintainable
- **Manual regex for env vars**: Rejected - `os.path.expandvars()` handles edge cases better
- **Floyd's cycle detection**: Considered but DFS with two sets is clearer and provides better errors

---

## 4. CLI Design with Click

### Decision: Command Groups with Standard Verbosity Flags

**Chosen Approach**: Use Click command groups for scalability with standard `-v`/`-q`/`--debug` flags.

**CLI Structure**:
```python
import click

@click.group()
@click.version_option(version='1.0.0')
@click.option('-v', '--verbose', count=True, help='Increase verbosity (-v, -vv, -vvv)')
@click.option('-q', '--quiet', is_flag=True, help='Suppress non-error output')
@click.pass_context
def cli(ctx, verbose, quiet):
    """Verilog-XL Filelist Parser."""
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['quiet'] = quiet

@cli.command()
@click.argument('filelist', type=click.Path(exists=True, readable=True, path_type=Path))
@click.option('--preserve-comments/--no-preserve-comments', default=True)
@click.option('-o', '--output', type=click.Path(path_type=Path))
@click.option('-f', '--format', type=click.Choice(['json', 'text']), default='json')
@click.option('--pretty/--compact', default=True)
@click.pass_context
def parse(ctx, filelist, preserve_comments, output, format, pretty):
    """Parse a Verilog-XL filelist."""
    result = parse_filelist(filelist, preserve_comments)

    if format == 'json':
        output_data = json.dumps(result, indent=2 if pretty else None)

    if output:
        output.write_text(output_data)
    else:
        click.echo(output_data)
```

**Rationale**:
- **Command Groups**: Scalable for adding `validate`, `export`, `analyze` commands later
- **`click.Path(path_type=Path)`**: Returns `pathlib.Path`, built-in validation
- **`click.echo()` not `print()`**: Cross-platform compatibility, handles Unicode
- **Standard verbosity**: `-v` = INFO, `-vv` = DEBUG, `-q` = ERROR only

**JSON Output**:
```python
def output_json(data, pretty=True, file=None):
    """Output JSON using click.echo for cross-platform support."""
    json_str = json.dumps(data, indent=2 if pretty else None, ensure_ascii=False)
    click.echo(json_str, file=file)
```

**Progress Indication**:
```python
# For known-size operations
with click.progressbar(length=total_files, label='Parsing') as bar:
    for file in files:
        process_file(file)
        bar.update(1)
```

**Error Handling**:
```python
class FilelistParseError(click.ClickException):
    exit_code = 3  # Data error

    def show(self, file=None):
        if file is None:
            file = click.get_text_stream('stderr')
        click.secho('Error: ', fg='red', bold=True, file=file, nl=False)
        click.echo(self.message, file=file)
```

**Alternatives Considered**:
- **Single command with subcommands**: Rejected - less scalable, messier help text
- **argparse**: Rejected - Click has better subcommand support, automatic help generation
- **`print()` for output**: Rejected - doesn't handle Windows Unicode properly
- **Custom progress implementation**: Rejected - Click's built-in is sufficient

---

## 5. Testing Strategy with pytest

### Decision: Functional Tests with tmp_path and CliRunner

**Chosen Approach**: Functional (non-class-based) tests using pytest fixtures, `tmp_path` for filesystem, in-memory SQLite for models, `CliRunner` for CLI.

**Fixture Organization**:
```python
# tests/conftest.py
import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pathlib import Path

@pytest.fixture(scope="session")
def db_engine():
    """Session-scoped in-memory SQLite."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()

@pytest.fixture
def db_session(db_engine):
    """Function-scoped session with transaction rollback."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()

@pytest.fixture
def cli_runner():
    """Click CLI runner for testing."""
    return CliRunner()

@pytest.fixture
def test_filelists(tmp_path):
    """Create test filelist directory structure."""
    filelist_dir = tmp_path / "filelists"
    filelist_dir.mkdir()

    # Create nested structure
    (filelist_dir / "root.f").write_text("-f nested/level1.f\nfile1.v\n")
    (filelist_dir / "nested").mkdir()
    (filelist_dir / "nested" / "level1.f").write_text("file2.v\n")

    return filelist_dir
```

**Rationale**:
- **`tmp_path`**: Modern pytest fixture (returns `Path`), auto-cleanup
- **In-memory SQLite**: Fast, isolated, zero setup for model tests
- **Transaction rollback**: Ensures test isolation without recreating DB
- **`CliRunner`**: Click's built-in test runner, captures output, handles I/O

**Testing SQLAlchemy Models**:
```python
def test_create_filelist(db_session):
    """Functional test for filelist creation."""
    filelist = Filelist(name="test", path="/tmp/test.f")
    db_session.add(filelist)
    db_session.commit()

    result = db_session.query(Filelist).filter_by(name="test").first()
    assert result is not None
    assert result.name == "test"
```

**Testing Click CLI**:
```python
def test_parse_command(cli_runner, tmp_path):
    """Functional test for parse command."""
    # Create test filelist
    filelist = tmp_path / "test.f"
    filelist.write_text("file1.v\nfile2.v\n")

    # Run CLI command
    result = cli_runner.invoke(cli, ['parse', str(filelist)])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data['files']) == 2
```

**Parametrized Tests**:
```python
@pytest.mark.parametrize("content,expected", [
    ("file1.v\nfile2.v\n", 2),
    ("file1.v\n", 1),
    ("", 0),
    ("# comment\nfile1.v\n", 1),
])
def test_parse_various_formats(cli_runner, tmp_path, content, expected):
    """Test parsing with various filelist formats."""
    filelist = tmp_path / "test.f"
    filelist.write_text(content)

    result = cli_runner.invoke(cli, ['parse', str(filelist)])
    assert result.exit_code == 0
    # Verify expected count
```

**Alternatives Considered**:
- **Class-based tests**: Rejected - spec requires functional style
- **`tmpdir` fixture**: Rejected - deprecated in favor of `tmp_path`
- **Real database**: Rejected - in-memory SQLite is faster and simpler
- **Manual file mocking**: Rejected - `tmp_path` provides real filesystem isolation

---

## Summary of Key Decisions

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Parser** | Lark LALR(1) with contextual lexer | Fast, clear errors, extensible grammar |
| **Data Model** | Adjacency list + SQLAlchemy ORM | Simple, good concurrency, query-friendly |
| **Storage** | In-memory SQLite (default) | Fast, zero setup, sufficient for CLI tool |
| **Path Resolution** | `pathlib.Path` + `os.path` hybrid | OOP API + needed functionality |
| **Env Var Expansion** | `os.path.expandvars()` with validation | Built-in, handles both syntaxes |
| **Circular Detection** | DFS with visited + recursion stack | O(V+E), clear error messages |
| **Symlink Handling** | Detect but preserve (use `absolute()`) | Meets requirements, avoids surprises |
| **CLI Framework** | Click with command groups | Scalable, good UX, standard patterns |
| **Output Format** | JSON via `click.echo()` | Cross-platform, parseable |
| **Progress** | `click.progressbar()` | Built-in, sufficient for use case |
| **Testing** | pytest functional + fixtures | Modern, isolated, maintainable |
| **Test Fixtures** | `tmp_path` for files, in-memory DB | Fast, auto-cleanup, realistic |

---

## Performance Expectations

Based on research findings:

- **Parsing**: 10K entries in < 1 second (Lark LALR performance)
- **DB Operations**: 10K inserts in ~100ms (SQLite bulk insert)
- **Query**: Complete tree load (10 levels) in 50-150ms (selectinload)
- **Circular Detection**: O(V+E) = ~1ms for 50 nested files
- **Serialization**: JSON dump of 10K entries in < 100ms

All performance goals from spec are achievable with chosen technologies.

---

## Implementation Priorities

1. **Phase 1: Core Infrastructure**
   - SQLAlchemy models (data-model.md)
   - Lark grammar (contracts/verilog_xl.lark)
   - Path resolver utilities

2. **Phase 2: Parser Implementation**
   - Lark transformer to data model
   - Circular reference detection
   - Environment variable expansion

3. **Phase 3: CLI Interface**
   - Click command structure
   - Output formatting (JSON, text)
   - Error handling

4. **Phase 4: Testing**
   - Unit tests (parser, resolver, models)
   - Integration tests (end-to-end workflows)
   - Contract tests (grammar completeness, CLI interface)

---

## References

All research findings are based on official documentation, Stack Overflow best practices, and community-vetted patterns as of November 2024. See individual research agent outputs for detailed source citations.
