from collections import deque
from dataclasses import dataclass
from pathlib import Path

from vcodeman.gen.analyzer import FileInfo

_NAME_PRIORITY = ["top", "chip", "dut", "tb", "testbench", "wrapper"]


@dataclass
class TopCandidate:
    module_name: str
    file_path: Path
    transitive_instance_count: int
    score: float


def detect_tops(file_infos: list[FileInfo]) -> list[TopCandidate]:
    """Return top-module candidates sorted best-first.

    Candidates are modules declared but never instantiated by any other file.
    Ranked by transitive instantiation closure size (larger = more likely top).
    Tie-broken by name heuristic.
    """
    mod_to_file: dict[str, Path] = {}
    for fi in file_infos:
        for mod in fi.declared_modules:
            mod_to_file[mod] = fi.path

    if not mod_to_file:
        return []

    # Build instantiation adjacency: module → set of modules it instantiates
    inst_graph: dict[str, set[str]] = {m: set() for m in mod_to_file}
    instantiated_by_others: set[str] = set()
    for fi in file_infos:
        for inst in fi.instantiated_modules:
            if inst in mod_to_file:
                instantiated_by_others.add(inst)
                for declaring_mod in fi.declared_modules:
                    inst_graph[declaring_mod].add(inst)

    candidates_names = set(mod_to_file) - instantiated_by_others

    def transitive_count(start: str) -> int:
        visited: set[str] = set()
        queue: deque[str] = deque([start])
        while queue:
            mod = queue.popleft()
            for child in inst_graph.get(mod, set()):
                if child not in visited:
                    visited.add(child)
                    queue.append(child)
        return len(visited)

    counts = {m: transitive_count(m) for m in candidates_names}
    max_count = max(counts.values(), default=1) or 1

    def _sort_key(name: str) -> tuple:
        priority = next(
            (i for i, h in enumerate(_NAME_PRIORITY) if h in name.lower()),
            len(_NAME_PRIORITY),
        )
        return (-counts[name], priority, name)

    sorted_names = sorted(candidates_names, key=_sort_key)
    return [
        TopCandidate(
            module_name=name,
            file_path=mod_to_file[name],
            transitive_instance_count=counts[name],
            score=counts[name] / max_count,
        )
        for name in sorted_names
    ]
