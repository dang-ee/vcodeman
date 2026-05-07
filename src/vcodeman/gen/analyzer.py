from dataclasses import dataclass, field
from pathlib import Path

import tree_sitter_systemverilog as tssv
from tree_sitter import Language, Parser

_SV_LANGUAGE = Language(tssv.language())
_PARSER = Parser(_SV_LANGUAGE)


@dataclass
class MacroDef:
    name: str
    value: str | None
    defined_in: Path
    line: int


@dataclass
class FileInfo:
    path: Path
    declared_packages: list[str] = field(default_factory=list)
    imported_packages: list[str] = field(default_factory=list)
    declared_modules: list[str] = field(default_factory=list)
    instantiated_modules: list[str] = field(default_factory=list)
    included_files: list[str] = field(default_factory=list)
    defined_macros: list[MacroDef] = field(default_factory=list)
    used_macros: list[str] = field(default_factory=list)


def _find_all(node, node_type: str) -> list:
    results = []
    if node.type == node_type:
        results.append(node)
    for child in node.children:
        results.extend(_find_all(child, node_type))
    return results


def _first_child(node, node_type: str):
    for child in node.children:
        if child.type == node_type:
            return child
    return None


def _text(node) -> str:
    return node.text.decode()


def analyze_file(path: Path) -> FileInfo:
    """Parse one RTL file via tree-sitter and extract all dependency information."""
    path = path.resolve()
    info = FileInfo(path=path)

    raw = path.read_bytes()
    root = _PARSER.parse(raw).root_node

    # Package declarations: package_declaration > simple_identifier
    for node in _find_all(root, "package_declaration"):
        ident = _first_child(node, "simple_identifier")
        if ident:
            info.declared_packages.append(_text(ident))

    # Module declarations
    for mod in _find_all(root, "module_declaration"):
        header = _first_child(mod, "module_ansi_header")
        if header:
            ident = _first_child(header, "simple_identifier")
            if ident:
                info.declared_modules.append(_text(ident))

    # Package imports (anywhere in file)
    for item in _find_all(root, "package_import_item"):
        ident = _first_child(item, "simple_identifier")
        if ident:
            name = _text(ident)
            if name not in info.imported_packages:
                info.imported_packages.append(name)

    # Module instantiations (tree-sitter separates these from gate_instantiation)
    for inst in _find_all(root, "module_instantiation"):
        ident = _first_child(inst, "simple_identifier")
        if ident:
            name = _text(ident)
            if name not in info.instantiated_modules:
                info.instantiated_modules.append(name)

    # `include directives: include_compiler_directive > quoted_string > quoted_string_item
    for node in _find_all(root, "include_compiler_directive"):
        qs = _first_child(node, "quoted_string")
        if qs:
            item = _first_child(qs, "quoted_string_item")
            if item:
                info.included_files.append(_text(item))

    # `define macros: text_macro_definition > text_macro_name > simple_identifier
    for node in _find_all(root, "text_macro_definition"):
        name_node = _first_child(node, "text_macro_name")
        if name_node:
            ident = _first_child(name_node, "simple_identifier")
            if ident:
                val_node = _first_child(node, "macro_text")
                value = _text(val_node).strip() if val_node else None
                info.defined_macros.append(MacroDef(
                    name=_text(ident),
                    value=value or None,
                    defined_in=path,
                    line=node.start_point[0] + 1,
                ))

    # `ifdef / `ifndef: conditional_compilation_directive > ifdef_condition|ifndef_condition
    for node in _find_all(root, "conditional_compilation_directive"):
        for cond_type in ("ifdef_condition", "ifndef_condition"):
            cond = _first_child(node, cond_type)
            if cond:
                ident = _first_child(cond, "simple_identifier")
                if ident:
                    name = _text(ident)
                    if name not in info.used_macros:
                        info.used_macros.append(name)

    return info
