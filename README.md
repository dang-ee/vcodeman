# vcodeman - Verilog-XL Filelist Parser and Analyzer

A comprehensive Python tool for parsing and analyzing Verilog-XL format filelists, designed for HDL verification and build automation workflows.

## Features

- **Filelist Flattening**: Recursively process nested filelists referenced by `-f` or `-F` options
- **Path Resolution**: Convert all paths to absolute paths by:
  - Expanding environment variables (`$VAR` and `${VAR}` syntax)
  - Resolving relative paths based on containing filelist location
  - Detecting and preventing circular references
- **Comprehensive Option Parsing**: Parse all Verilog-XL compiler options:
  - Library search directories (`-y`)
  - Library files (`-v`)
  - Include directories (`+incdir+`)
  - Macro definitions (`+define+`)
  - Library extensions (`+libext+`)
- **Structured Data Model**: Query and serialize parsed information using SQLAlchemy ORM
- **Resolution Traceability**: Clear markers showing nested filelist boundaries and missing files

## Installation

```bash
pip install vcodeman
```

Or for development:

```bash
git clone https://github.com/yourusername/vcodeman.git
cd vcodeman
pip install -e ".[dev]"
```

## Quick Start

### Command Line Interface

Parse and flatten a filelist:

```bash
vcodeman parse /path/to/design.f --output flattened.f
```

Parse with options:

```bash
vcodeman parse design.f \
  --output flat.f \
  --no-preserve-comments \
  --validate-files \
  --format json
```

Export data model as JSON:

```bash
vcodeman export design.f --format json > model.json
```

### Python API

```python
from vcodeman import FilelistParser
from pathlib import Path

# Parse a filelist
parser = FilelistParser()
result = parser.parse(Path("/path/to/design.f"))

# Access parsed data
print(f"Total files: {len(result.file_entries)}")
print(f"Include dirs: {[d.path for d in result.include_directories]}")

# Serialize to JSON
json_data = result.serialize_to_json()
```

## Requirements

- Python 3.12+
- Lark (parsing)
- SQLAlchemy (data modeling)
- Click (CLI framework)

## Development

Run tests:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=vcodeman --cov-report=html
```

Format code:

```bash
ruff format .
```

Type check:

```bash
mypy src/vcodeman
```

## Project Structure

```
vcodeman/
├── src/vcodeman/          # Source code
│   ├── __init__.py        # Package exports
│   ├── models.py          # SQLAlchemy data models
│   ├── parser.py          # Lark parser and transformer
│   ├── resolver.py        # Path resolution logic
│   ├── cli.py             # Click CLI commands
│   └── grammar.lark       # Lark grammar definition
├── tests/                 # Test suite
│   ├── conftest.py        # pytest fixtures
│   ├── test_*.py          # Test modules
│   └── filelists/         # Test filelist files
├── pyproject.toml         # Project configuration
└── README.md              # This file
```

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
