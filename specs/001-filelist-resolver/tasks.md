# Tasks: Verilog-XL Filelist Resolver

**Input**: Design documents from `/specs/001-filelist-resolver/`
**Prerequisites**: plan.md, spec.md, research.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Repository root**: `/home/d131.kim/project/vcodeman/`
- **Source code**: `src/vcodeman/`
- **Tests**: `tests/`
- **Test filelists**: `tests/filelists/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create pyproject.toml with Python 3.12, Lark, SQLAlchemy, Click, pytest dependencies per plan.md
- [x] T002 Create src/vcodeman/__init__.py with package exports
- [x] T003 Create tests/conftest.py with pytest fixtures (db_session, cli_runner, test_filelists)
- [x] T004 Create tests/filelists/ directory for test filelist files
- [x] T005 [P] Create README.md with project description and installation instructions

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T006 Create src/vcodeman/grammar.lark with complete Verilog-XL filelist grammar (based on research.md LALR parser design)
- [x] T007 Create src/vcodeman/models.py with all SQLAlchemy models: Base, Filelist, FileEntry, LibraryDirectory, LibraryFile, IncludeDirectory, MacroDefinition, LibraryExtension, ParsedFilelist, ResolutionContext
- [x] T008 [P] Create src/vcodeman/resolver.py with PathResolver class implementing environment variable expansion and relative path resolution
- [x] T009 Add circular reference detection to src/vcodeman/resolver.py using DFS with visited set and recursion stack
- [x] T010 Create exception classes in src/vcodeman/resolver.py: CircularReferenceError, UndefinedVariableError

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Basic Filelist Flattening (Priority: P1) 🎯 MVP

**Goal**: Parse and flatten nested filelists with `-f/-F` options into a single list of resolved file paths

**Independent Test**: Provide nested filelist structure and verify all referenced files are discovered with resolved paths

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T011 [P] [US1] Create tests/filelists/simple.f with basic file list (file1.v, file2.v)
- [x] T012 [P] [US1] Create tests/filelists/nested_root.f with `-f nested_level1.f` reference
- [x] T013 [P] [US1] Create tests/filelists/nested_level1.f with file references
- [x] T014 [P] [US1] Create tests/filelists/circular_a.f and circular_b.f that reference each other
- [x] T015 [P] [US1] Write test_parser_basic in tests/test_parser.py: parse simple.f and verify 2 files found
- [x] T016 [P] [US1] Write test_parser_nested in tests/test_parser.py: parse nested_root.f and verify files from both levels
- [x] T017 [P] [US1] Write test_parser_circular in tests/test_parser.py: parse circular_a.f and verify CircularReferenceError raised

### Implementation for User Story 1

- [x] T018 [US1] Implement FilelistParser class in src/vcodeman/parser.py with parse() method
- [x] T019 [US1] Implement Lark transformer in src/vcodeman/parser.py to convert parse tree to data model
- [x] T020 [US1] Add `-f` and `-F` option handling in parser transformer
- [x] T021 [US1] Integrate PathResolver for resolving filelist include paths
- [x] T022 [US1] Integrate circular reference detection in parser before processing nested filelists
- [x] T023 [US1] Add preservation/removal of comments and blank lines based on preserve_comments flag in parser
- [x] T024 [US1] Add RESOLVE START/END marker insertion in parser output

**Checkpoint**: At this point, User Story 1 should be fully functional - basic flattening with circular detection works

---

## Phase 4: User Story 2 - Environment Variable Resolution (Priority: P1)

**Goal**: Resolve environment variables in file paths using `$VAR` and `${VAR}` syntax

**Independent Test**: Set environment variables, provide filelist with variable references, verify resolved paths

### Tests for User Story 2

- [ ] T025 [P] [US2] Create tests/filelists/envvar.f with `$HOME/project/file.v` and `${PROJECT_ROOT}/design.v`
- [ ] T026 [P] [US2] Create tests/filelists/undefined_var.f with `$UNDEFINED_VAR/file.v`
- [ ] T027 [P] [US2] Write test_resolve_env_var in tests/test_resolver.py: verify $HOME expansion
- [ ] T028 [P] [US2] Write test_resolve_env_var_braces in tests/test_resolver.py: verify ${VAR} expansion
- [ ] T029 [P] [US2] Write test_undefined_env_var in tests/test_resolver.py: verify UndefinedVariableError raised

### Implementation for User Story 2

- [ ] T030 [US2] Implement expand_env_vars() method in src/vcodeman/resolver.py using os.path.expandvars()
- [ ] T031 [US2] Add strict environment variable validation in src/vcodeman/resolver.py to detect undefined variables
- [ ] T032 [US2] Integrate environment variable expansion into PathResolver.resolve_path() method
- [ ] T033 [US2] Update FilelistParser to use PathResolver for all path resolution including env vars

**Checkpoint**: At this point, User Stories 1 AND 2 should both work - flattening + env var resolution

---

## Phase 5: User Story 3 - Relative Path Resolution (Priority: P1)

**Goal**: Convert relative paths to absolute paths based on containing filelist's directory

**Independent Test**: Create filelists in different directories with relative paths, verify resolution

### Tests for User Story 3

- [ ] T034 [P] [US3] Create tests/filelists/subdir/relative.f with `../common/utils.v` and `./local/file.v`
- [ ] T035 [P] [US3] Write test_resolve_relative_parent in tests/test_resolver.py: verify ../ resolution
- [ ] T036 [P] [US3] Write test_resolve_relative_current in tests/test_resolver.py: verify ./ resolution
- [ ] T037 [P] [US3] Write test_nested_relative in tests/test_resolver.py: verify nested filelists resolve relative to their own directory

### Implementation for User Story 3

- [ ] T038 [US3] Implement relative path resolution in src/vcodeman/resolver.py using pathlib.Path with base_dir context
- [ ] T039 [US3] Update ResolutionContext in src/vcodeman/models.py to track current base directory for nested filelists
- [ ] T040 [US3] Integrate relative path resolution into FilelistParser to update base_dir when entering nested filelists
- [ ] T041 [US3] Add path normalization in src/vcodeman/resolver.py using Path.absolute() to preserve symlinks

**Checkpoint**: User Stories 1, 2, AND 3 work - full path resolution (nested, env vars, relative paths)

---

## Phase 6: User Story 4 - Comprehensive Verilog-XL Option Parsing (Priority: P1)

**Goal**: Parse all Verilog-XL compiler options: `-y`, `-v`, `+incdir+`, `+define+`, `+libext+`

**Independent Test**: Provide filelists with various options and verify correct identification and storage

### Tests for User Story 4

- [ ] T042 [P] [US4] Create tests/filelists/library_opts.f with `-y /lib/dir` and `-v /lib/file.v`
- [ ] T043 [P] [US4] Create tests/filelists/include_opts.f with `+incdir+/inc1+/inc2+/inc3`
- [ ] T044 [P] [US4] Create tests/filelists/define_opts.f with `+define+DEBUG+VERSION=1.0+TRACE`
- [ ] T045 [P] [US4] Create tests/filelists/libext_opts.f with `+libext+.v+.sv+.vp`
- [ ] T046 [P] [US4] Create tests/filelists/mixed_opts.f with combination of all option types
- [ ] T047 [P] [US4] Write test_parse_library_dir in tests/test_parser.py: verify `-y` parsing
- [ ] T048 [P] [US4] Write test_parse_library_file in tests/test_parser.py: verify `-v` parsing
- [ ] T049 [P] [US4] Write test_parse_incdir in tests/test_parser.py: verify `+incdir+` parsing with multiple paths
- [ ] T050 [P] [US4] Write test_parse_define in tests/test_parser.py: verify `+define+` with and without values
- [ ] T051 [P] [US4] Write test_parse_libext in tests/test_parser.py: verify `+libext+` parsing
- [ ] T052 [P] [US4] Write test_parse_mixed in tests/test_parser.py: verify correct categorization of mixed options

### Implementation for User Story 4

- [ ] T053 [US4] Add `-y` and `-v` grammar rules to src/vcodeman/grammar.lark
- [ ] T054 [US4] Add `+incdir+` grammar rule with plus-separated path list to src/vcodeman/grammar.lark
- [ ] T055 [US4] Add `+define+` grammar rule with macro definitions to src/vcodeman/grammar.lark
- [ ] T056 [US4] Add `+libext+` grammar rule with extension list to src/vcodeman/grammar.lark
- [ ] T057 [US4] Implement transformer methods in src/vcodeman/parser.py for `-y` and `-v` options to create LibraryDirectory/LibraryFile models
- [ ] T058 [US4] Implement transformer method in src/vcodeman/parser.py for `+incdir+` to create IncludeDirectory models
- [ ] T059 [US4] Implement transformer method in src/vcodeman/parser.py for `+define+` to create MacroDefinition models (parse name and optional value)
- [ ] T060 [US4] Implement transformer method in src/vcodeman/parser.py for `+libext+` to create LibraryExtension models
- [ ] T061 [US4] Apply PathResolver to all option paths (library paths, include paths) for absolute path resolution
- [ ] T062 [US4] Apply environment variable expansion to all option arguments

**Checkpoint**: All Verilog-XL options are now parsed and stored correctly

---

## Phase 7: User Story 5 - Structured Data Model (Priority: P1)

**Goal**: Organize parsed information in queryable data structure with serialization support

**Independent Test**: Parse complex filelist and verify data structure is organized, queryable, and serializable

### Tests for User Story 5

- [ ] T063 [P] [US5] Create tests/filelists/complex.f with nested structure, all option types, comments
- [ ] T064 [P] [US5] Write test_models_relationships in tests/test_models.py: verify Filelist → FileEntry relationship
- [ ] T065 [P] [US5] Write test_models_hierarchy in tests/test_models.py: verify parent-child filelist relationships
- [ ] T066 [P] [US5] Write test_query_by_type in tests/test_models.py: verify filtering files by type
- [ ] T067 [P] [US5] Write test_query_by_source in tests/test_models.py: verify querying by source filelist
- [ ] T068 [P] [US5] Write test_serialization in tests/test_models.py: verify JSON serialization/deserialization

### Implementation for User Story 5

- [ ] T069 [US5] Add to_dict() method to all model classes in src/vcodeman/models.py for serialization
- [ ] T070 [US5] Add from_dict() class method to all model classes in src/vcodeman/models.py for deserialization
- [ ] T071 [US5] Implement query helper methods in ParsedFilelist class: get_files_by_type(), get_options_by_category(), get_files_from_source()
- [ ] T072 [US5] Add metadata fields to ParsedFilelist in src/vcodeman/models.py: timestamp, warnings, errors
- [ ] T073 [US5] Implement serialize_to_json() method in ParsedFilelist that converts entire model tree to JSON
- [ ] T074 [US5] Store metadata in all parsed items: source filelist path, line number, original text, existence status

**Checkpoint**: Data model is complete, queryable, and serializable

---

## Phase 8: User Story 6 - Resolution Traceability with Annotations (Priority: P1)

**Goal**: Add RESOLVE START/END and NOT EXIST markers to trace nested filelist boundaries

**Independent Test**: Parse nested filelists and verify output contains markers at correct locations

### Tests for User Story 6

- [ ] T075 [P] [US6] Write test_resolve_markers in tests/test_parser.py: verify RESOLVE START/END markers around nested content
- [ ] T076 [P] [US6] Write test_not_exist_marker in tests/test_parser.py: verify NOT EXIST marker for missing filelists
- [ ] T077 [P] [US6] Write test_nested_markers in tests/test_parser.py: verify nested RESOLVE markers show hierarchy
- [ ] T078 [P] [US6] Write test_markers_with_no_preserve in tests/test_parser.py: verify markers preserved even when comments removed

### Implementation for User Story 6

- [ ] T079 [US6] Implement marker insertion logic in src/vcodeman/parser.py before processing nested filelist
- [ ] T080 [US6] Insert `// RESOLVE START: -f <filepath>` marker when entering nested filelist
- [ ] T081 [US6] Insert `// RESOLVE END  : -f <filepath>` marker when exiting nested filelist
- [ ] T082 [US6] Insert `// NOT EXIST    : -f <filepath>` marker when referenced filelist doesn't exist
- [ ] T083 [US6] Ensure markers are always preserved regardless of preserve_comments setting

**Checkpoint**: Traceability markers provide clear debugging information for nested structures

---

## Phase 9: User Story 7 - File Existence Validation (Priority: P2)

**Goal**: Validate that all referenced files exist on filesystem

**Independent Test**: Provide filelists with existing and non-existent files, verify correct identification

### Tests for User Story 7

- [ ] T084 [P] [US7] Create tests/filelists/missing_files.f with references to non-existent files
- [ ] T085 [P] [US7] Write test_validate_existing in tests/test_resolver.py: verify validation passes for existing files
- [ ] T086 [P] [US7] Write test_validate_missing in tests/test_resolver.py: verify missing files are identified
- [ ] T087 [P] [US7] Write test_validate_missing_filelist in tests/test_resolver.py: verify missing sub-filelist detection

### Implementation for User Story 7

- [ ] T088 [US7] Add validate_existence() method to src/vcodeman/resolver.py that checks Path.exists()
- [ ] T089 [US7] Add validation flag to FilelistParser in src/vcodeman/parser.py (optional, default disabled)
- [ ] T090 [US7] Store existence status in FileEntry.exists field in src/vcodeman/models.py
- [ ] T091 [US7] Generate warnings for missing files in ParsedFilelist.warnings in src/vcodeman/models.py
- [ ] T092 [US7] Report missing files in parser output when validation is enabled

**Checkpoint**: File validation feature complete

---

## Phase 10: User Story 8 - Output Format Options (Priority: P3)

**Goal**: Support different output formats (plain list, annotated, detailed)

**Independent Test**: Process same filelist with different format flags and verify structure

### Tests for User Story 8

- [ ] T093 [P] [US8] Write test_format_plain in tests/test_cli.py: verify plain format output (paths only)
- [ ] T094 [P] [US8] Write test_format_annotated in tests/test_cli.py: verify annotated format (paths + source)
- [ ] T095 [P] [US8] Write test_format_detailed in tests/test_cli.py: verify detailed format (paths + statistics)

### Implementation for User Story 8

- [ ] T096 [US8] Implement format_plain() in src/vcodeman/parser.py: output only absolute paths
- [ ] T097 [US8] Implement format_annotated() in src/vcodeman/parser.py: output paths with source filelist info
- [ ] T098 [US8] Implement format_detailed() in src/vcodeman/parser.py: output paths with statistics (total files, depth, warnings)
- [ ] T099 [US8] Add format option to CLI in src/vcodeman/cli.py with choices: plain, annotated, detailed

**Checkpoint**: Multiple output format options available

---

## Phase 11: CLI Interface

**Purpose**: Click-based command-line interface exposing all functionality

- [ ] T100 Create src/vcodeman/cli.py with Click command group and version option
- [ ] T101 Add `parse` command to src/vcodeman/cli.py with filelist argument and options
- [ ] T102 [P] Add `--preserve-comments/--no-preserve-comments` option (default: preserve) to parse command
- [ ] T103 [P] Add `--validate-files` flag to parse command to enable existence validation
- [ ] T104 [P] Add `-o/--output` option to parse command for output file path
- [ ] T105 [P] Add `-f/--format` option to parse command with choices: json, text
- [ ] T106 [P] Add `--pretty/--compact` option for JSON output formatting
- [ ] T107 Add `export` command to src/vcodeman/cli.py for data model serialization
- [ ] T108 [P] Implement JSON output using click.echo() for cross-platform compatibility
- [ ] T109 [P] Implement error handling with Click exceptions and colored output
- [ ] T110 Add progress indication with click.progressbar() for large filelists

---

## Phase 12: CLI Testing

**Purpose**: End-to-end testing of CLI commands

- [ ] T111 [P] Write test_cli_parse_basic in tests/test_cli.py: test parse command with simple filelist
- [ ] T112 [P] Write test_cli_parse_nested in tests/test_cli.py: test parse command with nested structure
- [ ] T113 [P] Write test_cli_parse_with_options in tests/test_cli.py: test parse with --no-preserve-comments, --validate-files
- [ ] T114 [P] Write test_cli_output_formats in tests/test_cli.py: test JSON and text output formats
- [ ] T115 [P] Write test_cli_export in tests/test_cli.py: test export command for data model serialization
- [ ] T116 [P] Write test_cli_error_handling in tests/test_cli.py: test error messages for missing files, circular refs, undefined vars

---

## Phase 13: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T117 [P] Add comprehensive docstrings to all classes and methods in src/vcodeman/
- [ ] T118 [P] Add type hints to all function signatures in src/vcodeman/
- [ ] T119 [P] Configure ruff or black for code formatting in pyproject.toml
- [ ] T120 [P] Configure mypy for type checking in pyproject.toml
- [ ] T121 [P] Add logging configuration to src/vcodeman/__init__.py
- [ ] T122 [P] Add logging statements at INFO level for key operations (parsing, resolving, validation)
- [ ] T123 [P] Add logging statements at DEBUG level for detailed tracing
- [ ] T124 Update README.md with complete usage examples from quickstart.md format
- [ ] T125 [P] Add examples/ directory with sample filelists demonstrating all features
- [ ] T126 Validate all success criteria from spec.md are met (SC-001 through SC-011)
- [ ] T127 Performance testing: verify 10K entries parse in under 1 second (SC-001, SC-006)
- [ ] T128 Performance testing: verify 10-level nesting works without degradation (SC-003)
- [ ] T129 Run all tests with pytest and ensure 100% pass rate
- [ ] T130 Code review and refactoring for maintainability

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-10)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 stories first, then P2, then P3)
- **CLI Interface (Phase 11)**: Depends on User Stories 1-6 (P1 stories) completion
- **CLI Testing (Phase 12)**: Depends on CLI Interface (Phase 11) completion
- **Polish (Phase 13)**: Depends on all desired user stories being complete

### User Story Dependencies

All user stories are independently testable but build on each other:

- **User Story 1 (P1)**: Basic flattening - Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1)**: Environment variables - Can start after US1 - Extends path resolution
- **User Story 3 (P1)**: Relative paths - Can start after US2 - Extends path resolution
- **User Story 4 (P1)**: Option parsing - Can start after US3 - Extends parser grammar
- **User Story 5 (P1)**: Data model - Can start after US4 - Adds serialization to complete model
- **User Story 6 (P1)**: Traceability markers - Can start after US5 - Adds annotations to output
- **User Story 7 (P2)**: Validation - Can start after US6 - Optional feature, extends resolver
- **User Story 8 (P3)**: Output formats - Can start after US7 - Optional feature, extends output

### Within Each User Story

1. Create test filelists FIRST
2. Write failing tests SECOND
3. Implement grammar changes (if needed)
4. Implement core functionality
5. Integrate with existing components
6. Run tests and verify all pass

### Parallel Opportunities

**Phase 1 (Setup)**: T002, T003, T004, T005 can run in parallel

**Phase 2 (Foundational)**: T007 and T008 can run in parallel after T006 completes

**Within User Stories**:
- Test creation tasks can run in parallel
- Test writing tasks can run in parallel
- Model creation tasks can run in parallel
- Independent implementation tasks can run in parallel

**CLI Phase**: T102, T103, T104, T105, T106, T108, T109, T110 can run in parallel after T100-T101

**CLI Testing Phase**: All test tasks (T111-T116) can run in parallel

**Polish Phase**: T117, T118, T119, T120, T121, T122, T123, T125 can run in parallel

---

## Parallel Example: User Story 1

```bash
# Create all test filelists in parallel:
Task T011: Create simple.f
Task T012: Create nested_root.f
Task T013: Create nested_level1.f
Task T014: Create circular_a.f and circular_b.f

# Write all test functions in parallel:
Task T015: test_parser_basic
Task T016: test_parser_nested
Task T017: test_parser_circular

# Then implement sequentially (dependencies):
Task T018: FilelistParser class → Task T019: Transformer → Task T020-T024: Features
```

---

## Implementation Strategy

### MVP First (User Stories 1-6 = All P1 Stories)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Basic Flattening)
4. Complete Phase 4: User Story 2 (Env Variables)
5. Complete Phase 5: User Story 3 (Relative Paths)
6. Complete Phase 6: User Story 4 (Option Parsing)
7. Complete Phase 7: User Story 5 (Data Model)
8. Complete Phase 8: User Story 6 (Traceability)
9. Complete Phase 11: CLI Interface
10. Complete Phase 12: CLI Testing
11. **STOP and VALIDATE**: Test all P1 features end-to-end
12. Deploy/demo MVP

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Basic flattening works
3. Add User Story 2 → Test independently → Env var resolution works
4. Add User Story 3 → Test independently → Relative path resolution works
5. Add User Story 4 → Test independently → All options parsed
6. Add User Story 5 → Test independently → Data model queryable
7. Add User Story 6 → Test independently → Traceability complete
8. Add CLI → Test independently → MVP ready for deployment
9. Optionally add User Story 7 (P2) → Validation feature
10. Optionally add User Story 8 (P3) → Format options

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Stories 1-2 (Flattening + Env Vars)
   - Developer B: User Stories 3-4 (Relative Paths + Options)
   - Developer C: User Stories 5-6 (Data Model + Traceability)
3. Integrate and test together
4. Team implements CLI together
5. Team tests and polishes together

---

## Notes

- [P] tasks = different files, no dependencies, can run in parallel
- [Story] label maps task to specific user story for traceability
- Each user story should be independently testable after implementation
- Write tests FIRST and verify they FAIL before implementing
- Grammar in src/vcodeman/grammar.lark must be completed early (T006) as it blocks parser work
- Models in src/vcodeman/models.py must be completed early (T007) as they block all data work
- PathResolver must be completed early (T008-T010) as it's used by all path resolution stories
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Run pytest frequently to catch regressions early
- Use in-memory SQLite for tests as specified in research.md
- Follow research.md decisions for implementation details (LALR parser, adjacency list, etc.)

---

## Summary

- **Total Tasks**: 130
- **Setup Tasks**: 5 (Phase 1)
- **Foundational Tasks**: 5 (Phase 2)
- **User Story 1 Tasks**: 14 (Phase 3)
- **User Story 2 Tasks**: 9 (Phase 4)
- **User Story 3 Tasks**: 8 (Phase 5)
- **User Story 4 Tasks**: 21 (Phase 6)
- **User Story 5 Tasks**: 12 (Phase 7)
- **User Story 6 Tasks**: 9 (Phase 8)
- **User Story 7 Tasks**: 9 (Phase 9)
- **User Story 8 Tasks**: 7 (Phase 10)
- **CLI Tasks**: 11 (Phase 11)
- **CLI Testing Tasks**: 6 (Phase 12)
- **Polish Tasks**: 14 (Phase 13)

**MVP Scope** (Suggested): Phases 1-8, 11-12 = 104 tasks covering all P1 user stories + CLI

**Parallel Opportunities**: 48 tasks marked [P] can run in parallel within their phase

**Independent Test Criteria Met**: Each user story has dedicated tests and can be validated independently
