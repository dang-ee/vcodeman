import warnings
from collections import defaultdict, deque
from pathlib import Path

from vcodeman.gen.analyzer import FileInfo


class CycleWarning(UserWarning):
    pass


def build_order(file_infos: list[FileInfo]) -> list[Path]:
    """Return file paths in topological compile order.

    Packages compile before their importers; submodules before instantiators.
    Emits CycleWarning (does not raise) if a dependency cycle is detected.
    """
    # Build lookup maps
    pkg_to_file: dict[str, Path] = {}
    mod_to_file: dict[str, Path] = {}
    for fi in file_infos:
        for pkg in fi.declared_packages:
            pkg_to_file[pkg] = fi.path
        for mod in fi.declared_modules:
            mod_to_file[mod] = fi.path

    all_paths = [fi.path for fi in file_infos]
    path_set = set(all_paths)

    # Adjacency: dep → set of files that depend on it
    dependents: dict[Path, set[Path]] = defaultdict(set)
    in_degree: dict[Path, int] = defaultdict(int)
    for p in all_paths:
        in_degree[p]  # ensure key exists

    for fi in file_infos:
        deps: set[Path] = set()
        for pkg in fi.imported_packages:
            if pkg in pkg_to_file and pkg_to_file[pkg] != fi.path:
                deps.add(pkg_to_file[pkg])
        for mod in fi.instantiated_modules:
            if mod in mod_to_file and mod_to_file[mod] != fi.path:
                deps.add(mod_to_file[mod])
        for dep in deps:
            if dep in path_set:
                dependents[dep].add(fi.path)
                in_degree[fi.path] += 1

    queue: deque[Path] = deque(p for p in all_paths if in_degree[p] == 0)
    ordered: list[Path] = []

    while queue:
        node = queue.popleft()
        ordered.append(node)
        for dependent in sorted(dependents[node]):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(ordered) < len(all_paths):
        remaining = [p for p in all_paths if p not in set(ordered)]
        warnings.warn(
            f"Dependency cycle detected among: {[p.name for p in remaining]}. "
            "AI repair will resolve ordering.",
            CycleWarning,
            stacklevel=2,
        )
        ordered.extend(remaining)

    return ordered
