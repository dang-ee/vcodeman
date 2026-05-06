# Design: `vcodeman gen` — RTL Filelist Auto-Generator

**Date**: 2026-05-07  
**Status**: Approved  
**Feature**: RTL directory → compilable `.f` filelist generator with AI repair loop

---

## 1. Overview

`vcodeman gen <dir>` scans a directory of RTL source files and automatically produces
a Verilog-XL `.f` filelist that passes compilation. It:

1. Collects all `.sv`, `.v`, `.svh`, `.vh` files
2. Extracts dependency information via **tree-sitter-systemverilog** AST (packages, imports,
   module instantiations, includes, macro defines — all as first-class AST nodes, no regex)
3. Builds a dependency graph and topologically sorts it
4. Detects top-module candidates and selects the best one
5. Writes the `.f` filelist (plus two sidecar files)
6. Compiles with a pluggable simulator backend and, if it fails, iterates using the
   **Claude API** to repair the filelist — repeating until success or `--max-iter` is
   reached

---

## 2. CLI

```bash
vcodeman gen <rtl-dir> [OPTIONS]

Arguments:
  rtl-dir   Root directory to scan recursively for RTL files

Options:
  -o, --output PATH         Output filelist path (default: <rtl-dir>/out.f)
  --top MODULE              Force a specific top module (skip auto-detection)
  --simulator TEXT          Backend to use: icarus (default) | xcelium | vcs
  --max-iter INTEGER        Max AI repair iterations (default: 5)
  --no-compile              Skip compilation check (generate filelist only)
  --no-ai                   Disable AI repair loop (static analysis only)
  --no-comments             Strip comments from generated filelist
  -h, --help                Show this message and exit
```

### Output files

| File | Description |
|------|-------------|
| `<output>.f` | Generated compilable filelist |
| `<output>.tops.txt` | All top-module candidates with instantiation scores |
| `<output>.macros.yaml` | All detected `define` macros and their usage |

---

## 3. Architecture

```
RTL Directory
      │
      ▼
┌─────────────┐    .sv/.v/.svh/.vh paths
│  Scanner    │──────────────────────────────────────────┐
└─────────────┘                                          │
                                                         ▼
┌──────────────────────────────────────────────────────────────┐
│  Analyzer (tree-sitter-systemverilog)                        │
│    Per file extracts (all as AST nodes, no regex):           │
│      - package declarations  (package_declaration)           │
│      - package imports       (package_import_item)           │
│      - module declarations   (module_declaration)            │
│      - module instantiations (module_instantiation)          │
│      - `include directives   (include_compiler_directive)    │
│      - `define macros        (text_macro_definition)         │
│      - `ifdef/`ifndef        (conditional_compilation_dir.)  │
└───────────────────────────┬──────────────────────────────────┘
                            │  FileInfo list
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  DependencyGraph + TopologicalSort                           │
│    Edges:  package-file → files that import it               │
│            submodule-file → files that instantiate it        │
│    Header dirs → +incdir+ entries                            │
│    Output: ordered list of source files                      │
└───────────────────────────┬──────────────────────────────────┘
                            │
                    ┌───────┴───────┐
                    ▼               ▼
         ┌──────────────┐  ┌────────────────────┐
         │ TopDetector  │  │  MacroExtractor     │
         │              │  │                     │
         │ Candidates = │  │ Dumps all `define,  │
         │ modules not  │  │ `ifdef, `ifndef to  │
         │ instantiated │  │ <out>.macros.yaml   │
         │ by others    │  └────────────────────┘
         │              │
         │ Best = module│
         │ with largest │
         │ transitive   │
         │ instantiation│
         │ closure      │
         └──────┬───────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────┐
│  FilelistWriter                                              │
│    +incdir+ lines (first)                                    │
│    package files (in import-order)                           │
│    remaining source files (topological order)                │
│    -top <best_module>  (last line)                           │
│    Sidecar: <out>.tops.txt with all candidates + scores      │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  Compiler (SimulatorBackend, pluggable)                      │
│    compile_cmd(filelist) → list[str]                         │
│    parse_errors(stdout, stderr, rc) → list[CompileError]     │
│                                                              │
│    IcarusBackend:   eda-env iverilog -c -f <f> -o /dev/null  │
│    XceliumBackend:  eda-env xrun -compile -f <f>  (future)   │
│    VCSBackend:      eda-env vcs -compile -f <f>   (future)   │
└───────────────────────────┬──────────────────────────────────┘
                            │ success → done
                            │ failure ↓
┌──────────────────────────────────────────────────────────────┐
│  AIRepairLoop (anthropic SDK)                                │
│    Input to Claude:                                          │
│      - compiler error log (structured CompileError list)     │
│      - current .f content                                    │
│      - first 30 lines of each referenced file                │
│    Output from Claude: corrected .f content                  │
│    Repeats up to --max-iter times                            │
│    Final failure: exit non-zero with last error log          │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. Module Design

### 4.1 `gen/scanner.py`

```python
@dataclass
class ScanResult:
    source_files: list[Path]    # .sv, .v
    header_files: list[Path]    # .svh, .vh
    include_dirs: list[Path]    # dirs containing header files (deduped)
```

Walks the given directory recursively. Collects source vs. header files.
Include dirs = unique set of parent dirs of all header files.

### 4.2 `gen/analyzer.py`

```python
@dataclass
class FileInfo:
    path: Path
    declared_packages: list[str]
    imported_packages: list[str]
    declared_modules: list[str]
    instantiated_modules: list[str]  # type names only, not instance names
    included_files: list[str]        # raw string from `include "..."
    defined_macros: list[MacroDef]   # name + optional value + line
    used_macros: list[str]           # `ifdef / `ifndef referenced names
```

Uses `tree-sitter-systemverilog` to parse raw file bytes. All preprocessor
directives (`include, `define, `ifdef) appear as first-class AST nodes — no
regex needed. `gate_instantiation` and `module_instantiation` are distinct node
types, so gate primitives are never mistaken for module dependencies. One
`FileInfo` per source file; header files (`.svh`) are also analyzed for macros.

### 4.3 `gen/graph.py`

Builds a directed acyclic graph (DAG) where nodes are files and edges encode
"must come before" relationships:

- `package_file → importer_file` (package must compile first)
- `submodule_file → instantiator_file` (submodule must compile first)

Performs Kahn's algorithm for topological sort. On cycle detection, reports
the cycle and falls through to AI repair.

### 4.4 `gen/top_detector.py`

```python
@dataclass
class TopCandidate:
    module_name: str
    file_path: Path
    transitive_instance_count: int  # size of transitive closure
    score: float                    # normalized 0.0–1.0
```

1. **Candidates** = modules declared in any file but never instantiated by
   any other file in the scan set.
2. **Ranking** = transitive count of unique modules reachable downward through
   instantiation edges (BFS/DFS). Larger = more likely real top.
3. **Best** = highest score candidate. Tie-break by name heuristic
   (`top`, `tb`, `dut`, `chip` preferred).

Writes `<out>.tops.txt` with all candidates, scores, and file paths.

### 4.5 `gen/writer.py`

Produces the `.f` text in order:

```
// Generated by vcodeman gen — 2026-05-07T...
// Simulator: icarus | Iterations: 0

+incdir+/abs/path/to/include/dir1
+incdir+/abs/path/to/include/dir2

// --- packages ---
/abs/path/to/pkg_a.sv
/abs/path/to/pkg_b.sv

// --- sources (topological order) ---
/abs/path/to/submod.sv
/abs/path/to/top.sv

// -top top_module_name   ← informational; move to sim cmd for Icarus, .f directive for Xcelium
```

`-top` handling is backend-specific: `SimulatorBackend.top_directive(module)` returns
either a `.f` line (Xcelium supports `-top` in `.f`) or `None` (Icarus: add `-s <top>`
to the compile command instead). The writer calls this method so the difference is
encapsulated in the backend class.

### 4.6 `gen/compiler.py`

```python
@dataclass
class CompileError:
    file: str | None
    line: int | None
    message: str
    raw: str

class SimulatorBackend(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def compile_cmd(self, filelist: Path) -> list[str]: ...

    @abstractmethod
    def parse_errors(self, stdout: str, stderr: str, rc: int) -> list[CompileError]: ...

    def top_directive(self, module: str) -> str | None:
        """Return a .f-file line for top module, or None if top is a CLI-only arg."""
        return None  # default: no .f directive (Icarus adds -s via compile_cmd)

class IcarusBackend(SimulatorBackend):
    name = "icarus"
    wrapper = "eda-env"

    def compile_cmd(self, filelist):
        return [self.wrapper, "iverilog", "-c", "-f", str(filelist), "-o", "/dev/null"]

    def parse_errors(self, stdout, stderr, rc):
        # parses "path:line: error: message" format
        ...
```

**To swap to Xcelium**: implement `XceliumBackend` with its `compile_cmd`
(`eda-env xrun -compile -f ...`) and `parse_errors` (xmelab format).
No other code changes required.

### 4.7 `gen/ai_repair.py`

Uses `anthropic` SDK with `claude-sonnet-4-6` (or configurable).
System prompt establishes the SV filelist expert role.
User message template:

```
Compilation failed with the following errors:
<errors>

Current filelist:
<filelist content>

File headers (first 30 lines each):
<per-file excerpts>

Return ONLY a corrected filelist. No explanation. Start with the first line of the filelist.
```

Retries up to `max_iter`. Each iteration feeds the new error log back.
Tracks iteration count and logs it as a comment in the final `.f` header.

### 4.8 `gen/macro_extractor.py`

```python
@dataclass
class MacroDef:
    name: str
    value: str | None     # None for bare `define NAME
    defined_in: Path
    line: int

@dataclass
class MacroReport:
    definitions: list[MacroDef]
    usages: dict[str, list[Path]]   # macro_name → files that `ifdef/`ifndef it
```

Serialized to `<out>.macros.yaml`:

```yaml
definitions:
  - name: SIMULATION
    value: null
    defined_in: /path/to/defines.svh
    line: 3
  - name: WIDTH
    value: "8"
    defined_in: /path/to/pkg.sv
    line: 12
usages:
  SIMULATION:
    - /path/to/core.sv
    - /path/to/mem.sv
  WIDTH:
    - /path/to/alu.sv
```

---

## 5. Dependencies Added to `pyproject.toml`

```toml
[project.dependencies]
# existing ...
"tree-sitter>=0.25",
"tree-sitter-systemverilog>=0.3",
"anthropic>=0.25",
"pyyaml>=6.0",
```

`pyslang` is **not** used — tree-sitter-systemverilog handles all SV dependency
extraction including preprocessor directives as first-class AST nodes.

---

## 6. Error Handling

| Condition | Behavior |
|-----------|----------|
| Cycle in dependency graph | Warning + skip cycle edges, AI repair handles order |
| `--max-iter` exhausted | Exit 1 with final error log printed |
| `--no-compile` | Skip compiler, write filelist only |
| `--no-ai` | Skip AI repair, exit 1 on first compile failure |
| File unreadable by pyslang | Warning + skip file, note in filelist comment |
| ANTHROPIC_API_KEY missing | Error on first AI repair attempt with clear message |

---

## 7. Success Criteria

- `vcodeman gen <dir>` produces a `.f` that compiles cleanly on first try
  for ≥80% of well-structured RTL directories (no AI needed)
- AI repair loop resolves remaining cases within 3 iterations for typical
  10–500 file projects
- Simulator swap (Icarus → Xcelium) requires implementing one new class only
- All three output files (`.f`, `.tops.txt`, `.macros.yaml`) are written on
  every successful run
