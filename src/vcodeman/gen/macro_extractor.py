from dataclasses import dataclass, field
from pathlib import Path

import yaml

from vcodeman.gen.analyzer import FileInfo, MacroDef


@dataclass
class MacroReport:
    definitions: list[MacroDef] = field(default_factory=list)
    usages: dict[str, list[Path]] = field(default_factory=dict)


def build_macro_report(file_infos: list[FileInfo]) -> MacroReport:
    report = MacroReport()
    for fi in file_infos:
        report.definitions.extend(fi.defined_macros)
    for fi in file_infos:
        for name in fi.used_macros:
            report.usages.setdefault(name, []).append(fi.path)
    return report


def write_macro_yaml(report: MacroReport, output: Path) -> None:
    data = {
        "definitions": [
            {
                "name": d.name,
                "value": d.value,
                "defined_in": str(d.defined_in),
                "line": d.line,
            }
            for d in report.definitions
        ],
        "usages": {
            name: [str(p) for p in paths]
            for name, paths in sorted(report.usages.items())
        },
    }
    output.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True))
