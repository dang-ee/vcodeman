# Feature Specification: Verilog-XL Filelist Resolver

**Feature Branch**: `001-filelist-resolver`
**Created**: 2025-11-24
**Updated**: 2025-11-26
**Status**: Implemented
**Input**: User description: "Verilog-XL 형식의 HDL filelist를 파싱하고 분석하는 기능을 만들건데, 첫 번째 기능으로 filelist resolver를 만들 거야. -f/-F로 기술된 파일리스트를 flatten 시키면서 모든 경로를 절대경로/resolved path로 변환하는 거야. 파일 경로에 포함된 환경변수와 상대경로로 되어 있는 것을 모두 실제 존재하는 절대경로로 풀어 헤쳐야 돼."

## User Scenarios & Testing

### User Story 1 - Basic Filelist Flattening (Priority: P1)

An HDL verification engineer has a Verilog-XL filelist that references other filelists using `-f` or `-F` options. They need to flatten this nested structure into a single list of resolved file paths to understand all source files in their project.

**Why this priority**: This is the core functionality - without basic flattening, no other features are useful. It delivers immediate value by showing all files in the project hierarchy.

**Independent Test**: Can be fully tested by providing a simple nested filelist structure and verifying that all referenced files are discovered and listed with resolved paths.

**Acceptance Scenarios**:

1. **Given** a root filelist containing `-f sublist1.f` and `-F sublist2.f`, **When** the resolver processes it, **Then** all files from sublist1.f and sublist2.f are included in the flattened output
2. **Given** a filelist with 3 levels of nesting (root → level1 → level2), **When** the resolver processes it, **Then** all files from all levels are discovered and flattened into a single list
3. **Given** a filelist with circular references (file1.f references file2.f which references file1.f), **When** the resolver processes it, **Then** the resolver detects the circular reference and reports an error without infinite looping

---

### User Story 2 - Environment Variable Resolution (Priority: P1)

An HDL engineer uses environment variables in file paths (e.g., `$PROJECT_ROOT/rtl/design.v` or `${VENDOR_LIB}/cells.v`) to make filelists portable across different environments. They need these variables resolved to actual absolute paths.

**Why this priority**: Environment variables are a standard practice in HDL workflows for portability. Without this, the tool cannot resolve real file locations, making it unusable for most real-world projects.

**Independent Test**: Can be tested by setting specific environment variables, providing a filelist with variable references, and verifying that output paths contain the actual resolved values.

**Acceptance Scenarios**:

1. **Given** a filelist with path `$HOME/project/file.v` and HOME is set to `/users/john`, **When** the resolver processes it, **Then** the output shows `/users/john/project/file.v`
2. **Given** a filelist with path `${PROJECT_ROOT}/rtl/design.v` and PROJECT_ROOT is `/workspace/chip`, **When** the resolver processes it, **Then** the output shows `/workspace/chip/rtl/design.v`
3. **Given** a filelist referencing undefined environment variable `$UNDEFINED_VAR/file.v`, **When** the resolver processes it with `--strict-env` option, **Then** the resolver reports an error indicating which variable is undefined

---

### User Story 3 - Relative Path Resolution (Priority: P1)

An HDL engineer uses relative paths in filelists (e.g., `../common/utils.v` or `./local/design.v`) relative to the filelist file's location. They need these converted to absolute paths to understand exact file locations.

**Why this priority**: Relative paths are ubiquitous in nested filelist structures. This is essential for the core "resolve to absolute paths" requirement.

**Independent Test**: Can be tested by creating filelists in different directories with relative path references, and verifying that all paths are resolved relative to their containing filelist's location.

**Acceptance Scenarios**:

1. **Given** a filelist at `/project/lists/design.f` containing path `../rtl/top.v`, **When** the resolver processes it, **Then** the output shows `/project/rtl/top.v`
2. **Given** a filelist at `/project/sub/list.f` containing path `./local/file.v`, **When** the resolver processes it, **Then** the output shows `/project/sub/local/file.v`
3. **Given** a nested structure where root filelist references sub/list.f, and sub/list.f contains `../common/util.v`, **When** the resolver processes it, **Then** paths in sub/list.f are resolved relative to the sub directory, not the root

---

### User Story 4 - Comprehensive Verilog-XL Option Parsing (Priority: P1)

An HDL engineer uses various Verilog-XL compiler options in filelists beyond just `-f/-F`, including library paths (`-y`, `-v`), include directories (`+incdir+`), macro definitions (`+define+`), and library extensions (`+libext+`). They need all these options parsed correctly and included in the flattened output.

**Why this priority**: These options are fundamental to Verilog-XL compilation workflows. Without proper parsing of these options, the tool cannot support real-world HDL projects that rely on libraries, includes, and compilation directives.

**Independent Test**: Can be tested by providing filelists with various Verilog-XL options and verifying that each option type is correctly identified and included in the flattened output.

**Acceptance Scenarios**:

1. **Given** a filelist with `-y /path/to/libdir` and `-v /path/to/lib.v`, **When** the resolver parses it, **Then** library directories and files are included in the flattened output
2. **Given** a filelist with `+incdir+/path/to/includes+/another/path`, **When** the resolver parses it, **Then** all include directories are extracted and output as a single `+incdir+` line
3. **Given** a filelist with `+define+MACRO1+MACRO2=value`, **When** the resolver parses it, **Then** macro definitions are output as a single `+define+` line
4. **Given** a filelist with `+libext+.v+.sv`, **When** the resolver parses it, **Then** library extensions are output as a single `+libext+` line
5. **Given** a filelist mixing `-f`, `-y`, `+incdir+`, and regular file paths, **When** the resolver parses it, **Then** each option type is correctly categorized and output in the flattened result

---

### User Story 5 - Flattened Filelist Output with Original Order Preservation (Priority: P1)

An HDL engineer needs the parsed filelist output as a flattened Verilog-XL compatible filelist that preserves the original structure, comments, and line order while only expanding `-f/-F` references inline.

**Why this priority**: The primary purpose of the tool is to produce a usable flattened filelist that maintains the original authoring structure. Engineers need to understand where each file came from and keep the compilation order intact.

**Independent Test**: Can be tested by parsing a complex nested filelist and verifying that the output preserves original line order, comments, and shows clear markers for inline expansions.

**Acceptance Scenarios**:

1. **Given** a filelist with `-f nested.f` reference, **When** parsing, **Then** output replaces the `-f` line with `// RESOLVE START: -f /absolute/path/to/nested.f`, followed by the nested content, followed by `// RESOLVE END  : -f /absolute/path/to/nested.f`
2. **Given** a filelist with `# comment` lines, **When** parsing, **Then** comments are converted to `// # comment` format (Verilog-style comments)
3. **Given** a filelist with mixed options and files, **When** parsing, **Then** original line order is preserved without any sorting or grouping
4. **Given** a filelist with various options (`-y`, `-v`, `+incdir+`, etc.), **When** parsing, **Then** options remain in their original positions in the output
5. **Given** a filelist, **When** parsing with `-o output.f` option, **Then** the flattened result is written to the specified file
6. **Given** a filelist with file paths, **When** parsing, **Then** file paths are converted to absolute paths
7. **Given** a filelist with `+incdir+` paths, **When** parsing, **Then** include directory paths are converted to absolute paths

---

### User Story 6 - JSON Output for Debugging (Priority: P2)

An HDL engineer wants to inspect the structured data model for debugging purposes or integration with other tools.

**Why this priority**: JSON output is a secondary feature for debugging and tool integration, not the primary use case.

**Independent Test**: Can be tested by parsing a filelist with `--format json` and verifying the JSON structure contains all parsed information.

**Acceptance Scenarios**:

1. **Given** a filelist, **When** parsing with `--format json` option, **Then** output is valid JSON containing all parsed data
2. **Given** a nested filelist, **When** parsing with `--format json`, **Then** JSON shows all filelists with their files and options
3. **Given** a filelist with various options, **When** parsing with `--format json`, **Then** JSON categorizes options by type (library_dirs, library_files, include_dirs, defines, lib_extensions, files)

---

### User Story 7 - SQLite Database Output (Priority: P2)

An HDL engineer or tooling developer wants to save parsed filelist data as a SQLite database for querying, analysis, or integration with database-aware tools.

**Why this priority**: SQLite output enables advanced querying and programmatic access to parsed data. It's valuable for large projects or integration with analysis tools, but not required for basic flattening workflows.

**Independent Test**: Can be tested by parsing a filelist with `--format sqlite` and verifying the SQLite database contains all expected tables and data.

**Acceptance Scenarios**:

1. **Given** a filelist, **When** parsing with `--format sqlite` option, **Then** output is a valid SQLite database file
2. **Given** a filelist without `-o` option, **When** parsing with `--format sqlite`, **Then** database is saved to `<input_filename>.db` by default
3. **Given** a nested filelist, **When** parsing with `--format sqlite`, **Then** database contains all filelists with hierarchical relationships preserved
4. **Given** a filelist with various options, **When** parsing with `--format sqlite`, **Then** database contains all entities (file_entry, library_directory, library_file, include_directory, macro_definition, library_extension, line_item)

---

### Edge Cases

- What happens when a filelist file is empty?
  - Resolver should handle gracefully, treating it as contributing zero files to the output

- What happens when a file path contains spaces?
  - Resolver should correctly parse and resolve paths with spaces

- What happens when both `-f` and `-F` reference the same sub-filelist?
  - Resolver should handle duplicate references by processing only once

- What happens when environment variables contain nested variable references (e.g., `$VAR1/$VAR2/file.v`)?
  - Resolver should expand all variables in the path

- What happens when relative path resolution goes above the filesystem root (e.g., `/../../../file.v`)?
  - Resolver should normalize the path correctly

- What happens with symbolic links in the path?
  - Symbolic links are kept as-is in the resolved paths, preserving the original path structure

- What happens when the same file is referenced multiple times through different paths?
  - Duplicate files are kept once in the output to avoid redundancy

- What happens when `+incdir+` has no paths (e.g., just `+incdir+` with no trailing paths)?
  - Resolver should skip or report a warning for malformed option

- What happens when `+define+` has macros without values mixed with macros with values (e.g., `+define+DEBUG+VERSION=1.0+TRACE`)?
  - Resolver should correctly parse each macro, treating those without `=` as flag macros (no value)

- What happens when multiple `+incdir+` options appear in the same filelist or across nested filelists?
  - Resolver should accumulate all include directories and output as a single combined `+incdir+` line

- What happens when `-y` or `-v` paths don't exist?
  - Resolver should include them in output (file existence is not validated by default)

- What happens when `+libext+` specifies extensions without leading dots (e.g., `+libext+v+sv` instead of `+libext+.v+.sv`)?
  - Resolver should normalize to include the leading dot

- What happens when the same macro is defined multiple times with different values?
  - Resolver should include all definitions (last one typically wins in simulators)

- What happens when mixing different Verilog-XL option styles in the same line?
  - Resolver should correctly parse each token according to its type

## Requirements

### Functional Requirements

- **FR-001**: System MUST parse Verilog-XL format filelists that contain file paths and options like `-f` and `-F`
- **FR-002**: System MUST recursively process nested filelists referenced by `-f` or `-F` options
- **FR-002a**: System MUST resolve `-f` paths relative to the **current working directory** (cwd)
- **FR-002b**: System MUST resolve `-F` paths relative to the **parent filelist's directory**
- **FR-003**: System MUST detect and prevent infinite loops from circular filelist references
- **FR-004**: System MUST expand environment variables in file paths using both `$VAR` and `${VAR}` syntax
- **FR-005**: System MUST resolve relative paths to absolute paths based on the containing filelist's directory location
- **FR-006**: System MUST preserve the order of files as they appear in the filelist hierarchy
- **FR-007**: System MUST support `--strict-env` option to fail on undefined environment variables
- **FR-008**: System MUST normalize paths to use Unix-style path separators
- **FR-009**: System MUST support file paths containing spaces and special characters
- **FR-010**: System MUST handle referenced sub-filelist files that do not exist gracefully
- **FR-011**: System MUST provide clear error messages indicating which filelist file and line number caused an error
- **FR-012**: System MUST handle empty filelists without errors
- **FR-013**: System MUST parse `-y <path>` option to identify library search directories
- **FR-014**: System MUST parse `-v <path>` option to identify library files
- **FR-015**: System MUST parse `+incdir+<path1>+<path2>+...` option to extract all include directories
- **FR-016**: System MUST parse `+define+<macro1>+<macro2>=<value>+...` option to extract macro definitions with optional values
- **FR-017**: System MUST parse `+libext+<ext1>+<ext2>+...` option to extract library file extensions
- **FR-018**: System MUST resolve paths in all Verilog-XL options (library paths, include paths) to absolute paths by default
- **FR-019**: System MUST expand environment variables in all Verilog-XL option arguments

### Output Requirements

- **FR-020**: System MUST output flattened Verilog-XL compatible filelist as default format (text)
- **FR-021**: System MUST preserve original line order in text output (no sorting or grouping)
- **FR-022**: System MUST convert `#` comments to `// #` format (Verilog-style)
- **FR-023**: System MUST inline expand `-f/-F` references with `// RESOLVE START: -f <absolute_path>` and `// RESOLVE END  : -f <absolute_path>` markers using absolute paths
- **FR-024**: System MUST convert all file paths to absolute paths in the output
- **FR-025**: System MUST convert all `+incdir+` paths to absolute paths in the output
- **FR-026**: System MUST support `--format json` option for structured JSON output
- **FR-027**: System MUST support `-o <file>` option to write output to a file instead of stdout
- **FR-028**: System MUST support `--format sqlite` option to export parsed data as a SQLite database file
- **FR-029**: System MUST use `<input_filename>.db` as default output path when `--format sqlite` is used without `-o` option

### Key Entities

- **Filelist**: A text file containing file paths and Verilog-XL options. Key attributes: absolute file path, parent filelist (if nested), nesting level, parsed line items.

- **FileEntry**: A source file or library file referenced in the filelist. Key attributes: absolute path, original path, source filelist, line number, existence status.

- **LibraryDirectory**: A directory specified with `-y` option for library search. Key attributes: absolute path, original path, source filelist, line number.

- **LibraryFile**: A library file specified with `-v` option. Key attributes: absolute path, original path, source filelist, line number.

- **IncludeDirectory**: A directory specified with `+incdir+` option for header file search. Key attributes: absolute path, original path, source filelist, line number, position in include path list.

- **MacroDefinition**: A macro specified with `+define+` option. Key attributes: macro name, optional value, source filelist, line number, original text.

- **LibraryExtension**: File extensions specified with `+libext+` option. Key attributes: extension (e.g., ".v", ".sv"), source filelist, line number, position in extension list.

- **ParsedFilelist**: The complete structured data model representing all parsed information. Key attributes: root filelist path, all file entries, all library directories/files, all include directories, all macro definitions, all library extensions, filelist hierarchy, parse metadata (timestamp, warnings, errors).

- **ResolutionContext**: The context used for path resolution. Key attributes: base directory, environment variable mappings, nesting depth, visited filelists (for circular detection).

## Success Criteria

### Measurable Outcomes

- **SC-001**: Engineers can flatten a typical 3-level nested filelist structure (50-100 files total) in under 1 second
- **SC-002**: System correctly resolves paths in filelists containing at least 5 different environment variables
- **SC-003**: System handles filelist hierarchies with up to 10 levels of nesting without performance degradation
- **SC-004**: 100% of circular reference scenarios are detected and reported without hanging or crashing
- **SC-005**: System processes filelists with up to 10,000 file entries without excessive memory usage (under 100MB)
- **SC-006**: Error messages include enough context that engineers can fix issues in under 2 minutes on average
- **SC-007**: System correctly parses and categorizes all 7 Verilog-XL option types (`-f`, `-F`, `-y`, `-v`, `+incdir+`, `+define+`, `+libext+`) in complex mixed filelists
- **SC-008**: Output flattened filelist can be directly used with Verilog simulators without modification
- **SC-009**: Engineers can optionally get JSON output for debugging or tool integration

## Assumptions

- Filelist files use standard Verilog-XL syntax with support for `-f`, `-F`, `-y`, `-v`, `+incdir+`, `+define+`, and `+libext+` options
- Environment variables are set in the system environment before the resolver runs
- The resolver runs on a Unix-like system (Linux, macOS) with access to the filesystem containing the referenced files
- File paths in filelists use UTF-8 encoding
- The primary use case is for verification/build automation tools that need a complete file list and compilation options
- Users expect absolute paths in the output by default to avoid ambiguity
- `-f` relative paths are resolved relative to the **current working directory** (cwd)
- `-F` relative paths are resolved relative to the **containing filelist's directory** (standard Verilog-XL behavior)
- Default behavior is to preserve file order, which is important for compilation order in some tools
- Symbolic links are kept as-is in resolved paths without resolving to target paths
- Output format uses Unix-style path separators (/) regardless of the platform
- The flattened text output is the primary deliverable; JSON is for debugging/integration purposes

## CLI Interface

### Commands

```bash
vcodeman parse <filelist>
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --output <file>` | Output file path | stdout (for text/json), `<input>.db` (for sqlite) |
| `-f, --format <text\|json\|sqlite>` | Output format | text |
| `--strict-env` | Fail on undefined environment variables | disabled |

### Examples

```bash
# Basic usage - output flattened filelist to stdout
vcodeman parse design.f

# Save to file
vcodeman parse design.f -o flat.f

# JSON output for debugging
vcodeman parse design.f --format json

# SQLite database output (creates design.db)
vcodeman parse design.f --format sqlite

# SQLite database output to specific file
vcodeman parse design.f --format sqlite -o output.db

# Strict environment variable checking
vcodeman parse design.f --strict-env
```

### Output Format (Text)

The output preserves original line order and structure. Comments are converted to Verilog-style (`//`), `-f/-F` includes are expanded inline with RESOLVE markers, and all file paths and `+incdir+` paths are converted to absolute paths.

**Example Input** (`mixed_opts.f`):
```
# Mixed options test
-f nested_level1.f
-y /lib/search
-v /lib/cells.v
+incdir+/includes+/headers
+define+SIM_MODE+VERBOSE=1
+libext+.v+.sv
design.v
testbench.v
```

**Example Output**:
```
// # Mixed options test
// RESOLVE START: -f /home/user/project/filelists/nested_level1.f
// # Level 1 nested filelist
/home/user/project/filelists/level1_file.v
// RESOLVE END  : -f /home/user/project/filelists/nested_level1.f
-y /lib/search
-v /lib/cells.v
+incdir+/home/user/project/filelists/includes+/home/user/project/filelists/headers
+define+SIM_MODE+VERBOSE=1
+libext+.v+.sv
/home/user/project/filelists/design.v
/home/user/project/filelists/testbench.v
```

**Key behaviors**:
- `# comment` → `// # comment` (Verilog-style comment conversion)
- `-f path` → `// RESOLVE START: -f <absolute_path>` + expanded content + `// RESOLVE END  : -f <absolute_path>`
- Original line order is preserved (no sorting or grouping)
- All file paths are converted to absolute paths
- All `+incdir+` paths are converted to absolute paths
- `-y`, `-v`, `+define+`, `+libext+` options remain as originally written

### Output Format (SQLite)

The SQLite output creates a database file with the following tables:

| Table | Description |
|-------|-------------|
| `parsed_filelist` | Root metadata (root path, timestamp, warnings, errors) |
| `filelist` | All filelist files with hierarchy (filepath, parent_id, nesting_level) |
| `file_entry` | Source files (filepath, original_path, line_number, is_library) |
| `library_directory` | `-y` directories (dirpath, original_path, line_number) |
| `library_file` | `-v` files (filepath, original_path, line_number) |
| `include_directory` | `+incdir+` directories (dirpath, original_path, line_number, position) |
| `macro_definition` | `+define+` macros (name, value, line_number, original_text) |
| `library_extension` | `+libext+` extensions (extension, line_number, position) |
| `line_item` | Original line items preserving order (line_number, item_type, original_text, resolved_text) |

**Example queries**:
```sql
-- Get all source files
SELECT filepath FROM file_entry WHERE is_library = 0;

-- Get nested filelist hierarchy
SELECT f.filepath, p.filepath AS parent
FROM filelist f
LEFT JOIN filelist p ON f.parent_id = p.id;

-- Get all include directories in order
SELECT dirpath FROM include_directory ORDER BY filelist_id, position;

-- Get line items for a specific filelist
SELECT * FROM line_item WHERE filelist_id = 1 ORDER BY line_number;
```
