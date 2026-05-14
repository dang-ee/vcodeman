from pathlib import Path
from vcodeman.gen.analyzer import FileInfo
from vcodeman.gen.top_detector import detect_tops, TopCandidate


def _fi(name: str, mods=(), insts=()):
    return FileInfo(path=Path(f"/fake/{name}.sv"),
                    declared_modules=list(mods),
                    instantiated_modules=list(insts))


def test_single_top_detected():
    pkg = _fi("pkg")
    alu = _fi("alu", mods=["alu"])
    core = _fi("core", mods=["core"], insts=["alu"])
    top = _fi("top", mods=["top"], insts=["core"])
    candidates = detect_tops([pkg, alu, core, top])
    assert len(candidates) >= 1
    best = candidates[0]
    assert best.module_name == "top"


def test_transitive_count_orders_candidates():
    a = _fi("a", mods=["a"])
    b = _fi("b", mods=["b"], insts=["a"])
    c = _fi("c", mods=["c"], insts=["b"])  # deepest hierarchy
    d = _fi("d", mods=["d"], insts=["a"])  # shallower
    candidates = detect_tops([a, b, c, d])
    names = [c.module_name for c in candidates]
    assert names.index("c") < names.index("d")


def test_name_heuristic_breaks_ties():
    a = _fi("a", mods=["chip"])
    b = _fi("b", mods=["random_name"])
    # both have same transitive count (0), chip wins by name heuristic
    candidates = detect_tops([a, b])
    assert candidates[0].module_name == "chip"


def test_score_is_normalized_0_to_1():
    alu = _fi("alu", mods=["alu"])
    core = _fi("core", mods=["core"], insts=["alu"])
    top = _fi("top", mods=["top"], insts=["core"])
    candidates = detect_tops([alu, core, top])
    for c in candidates:
        assert 0.0 <= c.score <= 1.0


def test_no_modules_returns_empty():
    pkg = _fi("pkg")  # no declared_modules
    assert detect_tops([pkg]) == []
