# vcodeman — Verilog-XL Filelist Parser and Analyzer

A Python tool for parsing, flattening, and analyzing Verilog-XL format
filelists. Designed to feed downstream simulators (Cadence Xcelium / xrun,
Synopsys VCS, Verilator) a single, fully-resolved filelist regardless of
how nested or env-var-laden the original is.

## Features

- **Recursive filelist flattening**: expands `-f` / `-F` includes inline.
- **Path resolution**: expands `$VAR` / `${VAR}`, resolves relative paths
  against the containing filelist's directory (`-F`) or the cwd (`-f`),
  and converts everything to absolute.
- **Circular reference detection**: refuses to hang on `a.f → b.f → a.f`.
- **Verilog-XL option parsing**: `-y`, `-v`, `+incdir+`, `+define+`,
  `+libext+`.
- **Resolve markers**: expanded `-f`/`-F` includes are bracketed by
  `// resolved start / end` comments so a reader can trace where each
  block came from.
- **Env var injection**: `--env KEY=VALUE` (repeatable) sets variables
  before parsing, useful when filelists reference site-specific names
  like `$project` or `${userdir}`.
- **Strict mode**: `--strict-env` fails fast on undefined env vars.
- **Structured data model**: `--format json` and `--format sqlite` for
  programmatic post-processing.

## Installation

```bash
git clone https://github.com/dang-ee/vcodeman.git
cd vcodeman
uv tool install .                  # installs the `vcodeman` binary
```

For development, use an editable install: `uv sync --all-extras`.

## Quick start

### Flatten a filelist for a simulator

```bash
vcodeman parse /path/to/design.f --output flat.f
xrun -f flat.f -elaborate ...
```

### Inject env vars consumed by the filelist

```bash
vcodeman parse design.f \
        --env project=/proj/myproj --env userdir=alice \
        --output flat.f
```

### Inspect as JSON

```bash
vcodeman parse design.f --format json --output model.json
```

### Export to SQLite for query-style analysis

```bash
vcodeman parse design.f --format sqlite --output design.db
sqlite3 design.db 'SELECT filepath, exists FROM file_entry WHERE exists = 0;'
```

### Strict mode

```bash
vcodeman parse design.f --strict-env       # fail on undefined env vars
```

`-h` and `--help` both work, on the group and every subcommand.

## Python API

```python
from pathlib import Path
from vcodeman import FilelistParser

parser = FilelistParser()
result = parser.parse(Path("/path/to/design.f"))

print(f"Total files:    {result.total_files}")
print(f"Include dirs:   {[d.path for d in result.include_directories]}")
print(f"Missing files:  {[f.filepath for f in result.file_entries if not f.exists]}")

json_blob = result.serialize_to_json()
```

## Requirements

- Python 3.12+
- Dependencies (auto-installed): `lark`, `sqlalchemy`, `click`

## Development

```bash
uv run pytest                  # run the full suite
uv run pytest --cov=vcodeman   # with coverage
uv run ruff format .
uv run mypy src/vcodeman
```

## Project structure

```
vcodeman/
├── src/vcodeman/
│   ├── __init__.py
│   ├── cli.py                 # Click entry: vcodeman parse
│   ├── parser.py              # Lark parser + transformer
│   ├── resolver.py            # Path resolution + env var expansion
│   ├── models.py              # SQLAlchemy data models
│   └── grammar.lark           # Lark grammar
├── tests/
│   ├── conftest.py            # pytest fixtures
│   ├── test_parser.py
│   ├── test_resolver.py
│   ├── test_models.py
│   ├── test_cli.py
│   └── filelists/             # test fixtures
├── pyproject.toml
└── README.md
```

## Companion tool

[`cmenv`](https://github.com/dang-ee/cmenv) drives the broader CodeMiner
pre/post-flow and invokes vcodeman with `--env project=... --env
userdir=...` to produce per-side filelists for `xrun -elaborate`. If
you only need filelist resolution, vcodeman alone is enough.

## License

MIT.
