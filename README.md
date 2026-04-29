# vcodeman — Verilog-XL Filelist Parser

Flatten, inspect, and transform Verilog-XL `.f` filelists.
Resolves all nested `-f`/`-F` includes, expands `$VAR`/`${VAR}`, and
produces a single ready-to-use filelist for Cadence Xcelium, Synopsys VCS,
or Verilator.

## Installation

```bash
git clone https://github.com/dang-ee/vcodeman.git
cd vcodeman
uv tool install .          # installs the `vcodeman` binary globally
```

Development (editable):

```bash
uv sync --all-extras
```

---

## Cookbook

### 1. Flatten to stdout

```bash
vcodeman parse design.f
```

Nested `-f`/`-F` blocks are expanded inline, wrapped in resolver comments:

```
// resolved start: -f sub/ip.f
/abs/path/to/sub/ip/core.v
/abs/path/to/sub/ip/ctrl.v
// resolved end  : -f sub/ip.f
/abs/path/to/top.v
```

---

### 2. Write to a file

```bash
vcodeman parse design.f -o flat.f
xrun -f flat.f -elaborate
```

---

### 3. Inject environment variables

Filelists often reference site-specific variables (`$proj`, `${USERDIR}`).
Pass them in without modifying your shell environment:

```bash
vcodeman parse design.f \
  --env PROJ=/proj/myproj \
  --env USERDIR=/home/alice \
  -o flat.f
```

`--env` is repeatable. Variables are available to all nested filelists.

---

### 4. Fail fast on undefined env vars

By default, unresolved `$VAR` tokens are left as-is with a warning.
Use `--strict-env` to turn them into a hard error:

```bash
vcodeman parse design.f --strict-env
# Error: Undefined environment variable
#   $UNDEFINED_VAR referenced in design.f:3
```

---

### 5. Skip files by extension (mixed-language filelists)

Comment out VHDL or other unwanted files without removing them from the
list — useful when running a Verilog-only sim against a mixed-language project:

```bash
vcodeman parse design.f --skip-ext vhd --skip-ext vhdl -o flat.f
```

Skipped lines appear as comments so you can audit what was filtered:

```
// skipped (.vhd): /abs/path/alu.vhd
// skipped (.vhdl): /abs/path/pkg.vhdl
/abs/path/core.v
```

The leading dot is optional: `vhd` and `.vhd` both work. `--skip-ext` is
only effective with `--format text` (the default).

---

### 6. JSON output for scripting

```bash
vcodeman parse design.f --format json | jq '.file_entries[].filepath'
```

Or save it:

```bash
vcodeman parse design.f --format json -o model.json
```

The JSON schema mirrors the internal data model — one array per entity type
(`file_entries`, `filelists`, `library_directories`, `macro_definitions`, …).

---

### 7. SQLite output for ad-hoc queries

```bash
vcodeman parse design.f --format sqlite -o design.db
```

If `-o` is omitted, the database is written next to the input file
(`design.db`).

Useful queries:

```sql
-- files that don't exist on disk
SELECT filepath, filelist_id
FROM file_entry
WHERE exists = 0;

-- all +define+ macros
SELECT name, value FROM macro_definition;

-- +incdir+ paths, in order
SELECT dirpath FROM include_directory ORDER BY position;

-- how deep is the include tree?
SELECT filepath, nesting_level FROM filelist ORDER BY nesting_level DESC;
```

---

### 8. Verbose and quiet modes

```bash
# print progress to stderr
vcodeman -v parse design.f -o flat.f

# suppress all non-error output
vcodeman -q parse design.f -o flat.f
```

`-v` can be repeated (`-vv`, `-vvv`) for more detail.

---

### 9. Real-world combined example

```bash
vcodeman parse top.f \
  --env PROJ=/proj/aurora \
  --env GRID=/cad/pdk/1.8 \
  --strict-env \
  --skip-ext vhd \
  -o run/flat.f \
  -v
```

---

## Filelist syntax reference

`vcodeman` understands the following Verilog-XL constructs:

| Syntax | Meaning |
|---|---|
| `path/to/file.v` | Source file |
| `-f path.f` | Include filelist (paths relative to **cwd**) |
| `-F path.f` | Include filelist (paths relative to **filelist's own dir**) |
| `-y /path/to/dir` | Library search directory |
| `-v /path/to/file.v` | Library file |
| `+incdir+dir1+dir2` | Include directories (chainable with `+`) |
| `+define+MACRO+KEY=val` | Preprocessor defines (chainable with `+`) |
| `+libext+.v+.sv` | Library file extensions |
| `$VAR` or `${VAR}` | Environment variable expansion |
| `// comment` or `# comment` | Line comments (passed through to output) |

Blank lines and leading/trailing whitespace are ignored. CRLF line endings
are handled transparently.

---

## Python API

```python
from pathlib import Path
from vcodeman.parser import FilelistParser

parser = FilelistParser(strict_env_vars=False)
result = parser.parse(Path("design.f"))

# summary
print(result.root_filepath)
print(result.warnings)   # list[str]
print(result.errors)     # list[str]

# flat access
data = result.to_dict()  # mirrors the JSON output schema
for fe in data["file_entries"]:
    print(fe["filepath"], "exists:", fe["exists"])
```

Inject env vars before calling `parse()`:

```python
import os
os.environ["PROJ"] = "/proj/aurora"
result = parser.parse(Path("design.f"))
```

---

## Output format details

### Text (default)

A flattened, simulator-ready filelist.  Nested includes are replaced
in-place with their contents, bracketed by resolver comments:

```
// resolved start: -F sub/ip.f
/abs/path/core.v
// resolved end  : -F sub/ip.f
```

Files skipped via `--skip-ext` become:

```
// skipped (.vhd): /abs/path/pkg.vhd
```

All other tokens (`+incdir+`, `+define+`, `-y`, `-v`, inline comments)
are passed through verbatim.

### JSON

Structured representation — one key per entity type.  Useful for
tooling that consumes filelist data programmatically.

```jsonc
{
  "root_filepath": "/abs/path/design.f",
  "timestamp": "2026-04-30T12:00:00",
  "warnings": [],
  "errors": [],
  "filelists": [...],
  "file_entries": [
    { "filepath": "/abs/path/top.v", "exists": true, "line_number": 5, ... }
  ],
  "library_directories": [...],
  "macro_definitions": [...],
  "include_directories": [...],
  "library_extensions": [...]
}
```

### SQLite

All entities are stored in a relational schema.  Table names match the
JSON keys (`file_entry`, `filelist`, `library_directory`, etc.).
The `filelist.nesting_level` column tracks include depth; `filelist.parent_id`
gives the adjacency-list tree.

---

## Error reference

| Exit code | Meaning |
|---|---|
| `0` | Success |
| `1` | Parse error (circular reference, missing file, etc.) |
| `2` | Bad CLI arguments (`--env` format error) |

Errors are printed to stderr in color.  Pass `-vv` to see a full traceback.

---

## Development

```bash
uv run pytest                   # full test suite (32 tests)
uv run pytest --cov=vcodeman    # with coverage
uv run ruff format .
uv run mypy src/vcodeman
```

## Project structure

```
vcodeman/
├── src/vcodeman/
│   ├── _version.py            # single source of truth for __version__
│   ├── __init__.py
│   ├── cli.py                 # Click entry point (dynamic imports for fast --help)
│   ├── parser.py              # Lark LALR parser + transformer
│   ├── resolver.py            # path resolution + env var expansion
│   ├── models.py              # SQLAlchemy ORM models
│   └── grammar.lark           # Verilog-XL grammar
├── tests/
│   ├── conftest.py
│   ├── test_parser.py
│   ├── test_resolver.py
│   ├── test_models.py
│   ├── test_cli.py
│   ├── test_realistic.py
│   └── filelists/             # test fixture .f files
├── pyproject.toml
└── README.md
```

## Companion tool

[`cmenv`](https://github.com/dang-ee/cmenv) drives the broader CodeMiner
pre/post-flow and calls vcodeman with `--env` to produce per-side filelists
for `xrun -elaborate`. If you only need filelist resolution, vcodeman alone
is sufficient.

## License

MIT.
