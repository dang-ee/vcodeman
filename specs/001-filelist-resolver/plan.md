# Implementation Plan: Verilog-XL Filelist Resolver

**Branch**: `001-filelist-resolver` | **Date**: 2025-11-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-filelist-resolver/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build a comprehensive Verilog-XL filelist parser and resolver that flattens nested filelists, resolves all paths (environment variables and relative paths) to absolute paths, parses all Verilog-XL compiler options (`-f`, `-F`, `-y`, `-v`, `+incdir+`, `+define+`, `+libext+`), and produces a structured, queryable data model for future HDL analysis features. The tool will use Lark for parsing, SQLAlchemy ORM for the data model, Click for CLI, and pytest for testing.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**:
- Lark (parsing Verilog-XL filelist grammar)
- SQLAlchemy ORM (structured data model)
- Click (CLI framework)
- pytest (functional testing)

**Storage**: SQLAlchemy with in-memory SQLite (default) and optional file-based SQLite for persistence
**Testing**: pytest with functional test style
**Target Platform**: Unix-like systems (Linux, macOS)
**Project Type**: Single library with CLI interface
**Performance Goals**:
- Parse 10,000 file entries in under 1 second
- Flatten 10-level nested hierarchy without degradation
- Serialize/deserialize data model in under 100ms

**Constraints**:
- Unix path support only (no Windows paths)
- Must detect circular references without hanging
- Must preserve compilation order
- Memory usage under 100MB for typical projects

**Scale/Scope**:
- Support up to 50 nested filelists
- Handle up to 10,000 file entries
- Parse 7 Verilog-XL option types
- Support environment variable expansion

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Status**: Constitution template not yet populated - treating as PASS with standard best practices.

**Applied Principles**:
- ✅ Library-First: Core parsing/resolution logic in standalone library
- ✅ CLI Interface: Click-based CLI with JSON + human-readable output
- ✅ Test-First: TDD workflow with pytest functional tests
- ✅ Clear separation: Parser, resolver, data model, CLI layers
- ✅ Simplicity: Start with essential features, structured for extension

## Project Structure

### Documentation (this feature)

```text
specs/001-filelist-resolver/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (grammar design, best practices)
├── data-model.md        # Phase 1 output (SQLAlchemy entity definitions)
├── quickstart.md        # Phase 1 output (usage examples)
├── contracts/           # Phase 1 output (Lark grammar, API contracts)
│   └── verilog_xl.lark  # Lark grammar for Verilog-XL filelist syntax
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/vcodeman/
├── __init__.py
├── models.py                # All SQLAlchemy models in one file
├── parser.py                # Lark parser + transformer
├── resolver.py              # Path + env var resolution logic
├── cli.py                   # Click CLI commands (all in one)
└── grammar.lark             # Lark grammar definition

tests/
├── conftest.py              # pytest fixtures (db_session, cli_runner, tmp filelists)
├── test_models.py           # Model tests
├── test_parser.py           # Parser tests
├── test_resolver.py         # Resolver tests
├── test_cli.py              # CLI tests
└── filelists/               # Test filelist files
    ├── simple.f
    ├── nested_root.f
    ├── nested_level1.f
    └── complex.f

pyproject.toml               # Project metadata, dependencies
README.md                    # Quick start guide
```

**Structure Decision**:
- **Simplified to essential files**: Instead of complex directory hierarchy, use single-file modules
- **Combined related functionality**: All models in `models.py`, all CLI in `cli.py`
- **Flat test structure**: No unit/integration/contract separation - just test files by module
- **Grammar as resource**: `.lark` file alongside Python code for easy access

**Rationale for Simplification**:
- **Small codebase**: ~2000-3000 LOC total, doesn't justify deep hierarchy
- **Clear boundaries**: Each `.py` file is self-contained (models, parser, resolver, CLI)
- **Easy navigation**: 5 source files vs 20+ files in original structure
- **Faster development**: Less boilerplate, fewer imports, clearer dependencies

## Complexity Tracking

> **No violations** - Standard single-library structure with clear layer separation.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |

---

## Phase 0: Outline & Research

### Research Tasks

Based on Technical Context unknowns and technology choices:

1. **Lark Grammar Design**
   - Research: Lark parser generator best practices for nested structures
   - Research: How to handle Verilog-XL option syntax (`-f`, `+incdir+`, etc.)
   - Research: Error recovery strategies for malformed filelists
   - Output: Grammar design decisions for `verilog_xl.lark`

2. **SQLAlchemy ORM Best Practices**
   - Research: SQLAlchemy ORM patterns for hierarchical data (nested filelists)
   - Research: In-memory vs file-based SQLite for this use case
   - Research: Query optimization for relationship traversal
   - Output: Data model design patterns

3. **Path Resolution Strategies**
   - Research: Python `pathlib` vs `os.path` for Unix path handling
   - Research: Environment variable expansion edge cases
   - Research: Circular reference detection algorithms
   - Output: Resolution algorithm decisions

4. **CLI Design with Click**
   - Research: Click command groups vs single command with subcommands
   - Research: JSON output formatting best practices
   - Research: Progress indication for long-running operations
   - Output: CLI structure and user experience design

5. **Testing Strategy**
   - Research: pytest functional testing patterns
   - Research: Test fixture organization for complex file structures
   - Research: Testing SQLAlchemy models without full DB setup
   - Output: Test architecture and fixture strategy

### Research Output Location

All research findings will be consolidated in `research.md` with the following structure:

```markdown
# Research: Verilog-XL Filelist Resolver

## 1. Lark Grammar Design
**Decision**: [chosen approach]
**Rationale**: [why chosen]
**Alternatives Considered**: [other options]

## 2. SQLAlchemy ORM Patterns
...

## 3. Path Resolution
...

## 4. CLI Design
...

## 5. Testing Strategy
...
```

---

## Phase 1: Design & Contracts

**Prerequisites**: `research.md` complete with all decisions documented

### 1. Data Model Design (`data-model.md`)

Extract entities from spec and design SQLAlchemy models:

**Entities from Spec**:
- Filelist (text file with paths and options)
- FileEntry (source file or library file)
- LibraryDirectory (`-y` option)
- LibraryFile (`-v` option)
- IncludeDirectory (`+incdir+` option)
- MacroDefinition (`+define+` option)
- LibraryExtension (`+libext+` option)
- ParsedFilelist (root aggregate with all parsed data)
- ResolutionContext (path resolution state)

**Relationships**:
- Filelist has many FileEntry (one-to-many)
- Filelist has many nested Filelist (self-referential)
- ParsedFilelist has one root Filelist (one-to-one)
- ParsedFilelist has many LibraryDirectory, IncludeDirectory, MacroDefinition, LibraryExtension

**Validation Rules** (from FR-001 to FR-034):
- Circular reference detection (FR-003)
- Environment variable validation (FR-007, FR-029)
- Path existence validation (FR-010, FR-011)
- Duplicate file warnings (FR-021)

**State Transitions**:
- Filelist: unparsed → parsing → parsed | error
- FileEntry: unresolved → resolving → resolved | missing
- ParsedFilelist: empty → building → complete → serialized

### 2. API Contracts (`contracts/`)

**Lark Grammar** (`contracts/verilog_xl.lark`):
```lark
start: line+

line: filelist_option
    | library_option
    | include_option
    | define_option
    | libext_option
    | file_path
    | comment
    | NEWLINE

filelist_option: "-f" WS+ file_path
                | "-F" WS+ file_path

library_option: "-y" WS+ file_path
               | "-v" WS+ file_path

include_option: "+incdir+" path_list

define_option: "+define+" macro_list

libext_option: "+libext+" ext_list

// ... (complete grammar in research phase)
```

**Parser Interface Contract**:
```python
# contracts/parser_interface.py (pseudo-code for documentation)

class FilelistParser:
    """Contract for filelist parser."""

    def parse(self, filelist_path: Path) -> ParsedFilelist:
        """Parse a filelist and return complete data model.

        Args:
            filelist_path: Absolute path to root filelist

        Returns:
            ParsedFilelist with all resolved paths and parsed options

        Raises:
            CircularReferenceError: If circular filelist references detected
            UndefinedVariableError: If environment variable not found
            FileNotFoundError: If filelist file doesn't exist
            ParseError: If syntax errors in filelist
        """
        pass
```

**Resolver Interface Contract**:
```python
# contracts/resolver_interface.py (pseudo-code)

class PathResolver:
    """Contract for path resolution."""

    def resolve_path(self, path: str, context: ResolutionContext) -> Path:
        """Resolve path to absolute path.

        Args:
            path: Path string (may contain env vars, relative paths)
            context: Resolution context (base dir, env vars)

        Returns:
            Absolute resolved Path

        Raises:
            UndefinedVariableError: If env variable not set
        """
        pass
```

**CLI Interface Contract**:
```bash
# contracts/cli_interface.sh (example usage)

# Parse and flatten filelist
vcodeman parse /path/to/root.f --output flat.f

# Parse with options
vcodeman parse /path/to/root.f \
  --output flat.f \
  --no-preserve-comments \
  --validate-files \
  --format json

# Export data model
vcodeman export /path/to/root.f --format json > model.json
```

### 3. Quickstart Guide (`quickstart.md`)

```markdown
# Quickstart: Verilog-XL Filelist Resolver

## Installation
```bash
pip install vcodeman
```

## Basic Usage

### Parse and flatten a filelist
```bash
vcodeman parse /path/to/design.f --output flattened.f
```

### Parse with all options
```bash
vcodeman parse design.f \
  --output flat.f \
  --no-preserve-comments \
  --validate-files
```

### Export data model as JSON
```bash
vcodeman export design.f --format json > model.json
```

## Python API Usage

```python
from vcodeman import FilelistParser
from pathlib import Path

parser = FilelistParser()
result = parser.parse(Path("/path/to/design.f"))

# Access parsed data
print(f"Total files: {len(result.file_entries)}")
print(f"Include dirs: {[d.path for d in result.include_directories]}")
```
```

### 4. Agent Context Update

After design phase completion, run:
```bash
.specify/scripts/bash/update-agent-context.sh claude
```

This will update `.claude/CONTEXT.md` with:
- Python 3.12
- Lark, SQLAlchemy, Click, pytest
- Project structure from this plan
- Key design decisions from research.md

---

## Phase 2: Task Generation

**Status**: Not yet executed (requires `/speckit.tasks` command)

Task generation will break down implementation into:
1. Phase 0: Setup (pyproject.toml, project structure)
2. Phase 1: Data models (SQLAlchemy entities)
3. Phase 2: Lark grammar and parser
4. Phase 3: Path resolver (env vars, relative paths)
5. Phase 4: CLI interface (Click commands)
6. Phase 5: Serialization (JSON, flattened output)
7. Phase 6: Testing (unit, integration, contract)
8. Phase 7: Documentation and examples

Each phase will have specific tasks with test-first requirements.

---

## Post-Design Constitution Check

**Status**: To be completed after Phase 1 design artifacts are generated

**Checks**:
- [ ] Library is self-contained (no external CLI dependencies)
- [ ] CLI exposes all library functionality
- [ ] All public interfaces have contracts defined
- [ ] Test structure supports TDD workflow
- [ ] Data model supports future features (extensibility)
- [ ] Performance goals achievable with chosen tech stack

---

## Implementation Notes

### Critical Design Decisions

1. **Lark over Regex**: Lark provides structured parsing with error recovery, easier to extend for future Verilog-XL options

2. **SQLAlchemy ORM**: Provides queryable data model with relationship traversal, essential for future analysis features (dependency graphs, compilation order)

3. **In-memory SQLite default**: Fast for typical use cases, optional file-based for persistence needs

4. **Functional pytest style**: Aligns with spec requirement, easier to read and maintain than class-based

5. **Click over argparse**: Better subcommand support, automatic help generation, validation built-in

### Extension Points

Future features can extend:
- **Parser**: Add new Verilog-XL options by extending grammar
- **Data Model**: Add new entities via SQLAlchemy inheritance
- **Serializers**: Add new export formats (YAML, TOML, etc.)
- **Validators**: Add new validation rules (dependency analysis, etc.)
- **CLI Commands**: Add new commands for analysis features

### Risk Mitigation

1. **Circular Reference Handling**: Use visited set in ResolutionContext, fail fast with clear error
2. **Large Filelist Performance**: Stream parsing, lazy loading of nested filelists if needed
3. **Path Resolution Edge Cases**: Comprehensive test fixtures covering all edge cases from spec
4. **Grammar Ambiguity**: Lark's LALR parser handles ambiguity, test with real-world filelists

---

## Next Steps

1. ✅ Phase 0: Run research agents to resolve all NEEDS CLARIFICATION
2. ⏳ Phase 1: Generate data-model.md, contracts/, quickstart.md
3. ⏳ Phase 1: Update agent context with technology stack
4. ⏳ Post-Design: Re-evaluate constitution compliance
5. ⏳ Phase 2: Execute `/speckit.tasks` to generate implementation tasks
