from dataclasses import dataclass, field
from pathlib import Path


SOURCE_EXTS = {".sv", ".v"}
HEADER_EXTS = {".svh", ".vh"}


@dataclass
class ScanResult:
    source_files: list[Path] = field(default_factory=list)
    header_files: list[Path] = field(default_factory=list)
    include_dirs: list[Path] = field(default_factory=list)


def scan(rtl_dir: Path) -> ScanResult:
    """Recursively collect RTL source and header files from rtl_dir."""
    rtl_dir = rtl_dir.resolve()
    sources: list[Path] = []
    headers: list[Path] = []
    inc_dir_set: set[Path] = set()

    for path in sorted(rtl_dir.rglob("*")):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext in SOURCE_EXTS:
            sources.append(path)
        elif ext in HEADER_EXTS:
            headers.append(path)
            inc_dir_set.add(path.parent)

    return ScanResult(
        source_files=sources,
        header_files=headers,
        include_dirs=sorted(inc_dir_set),
    )
