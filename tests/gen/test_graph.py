from pathlib import Path
from vcodeman.gen.analyzer import FileInfo
from vcodeman.gen.graph import build_order, CycleWarning


def _make_info(name: str, pkgs=(), imports=(), mods=(), insts=()) -> FileInfo:
    return FileInfo(
        path=Path(f"/fake/{name}.sv"),
        declared_packages=list(pkgs),
        imported_packages=list(imports),
        declared_modules=list(mods),
        instantiated_modules=list(insts),
    )


def test_package_before_importer():
    pkg = _make_info("pkg", pkgs=["mypkg"])
    mod = _make_info("mod", imports=["mypkg"], mods=["mymod"])
    ordered = build_order([pkg, mod])
    assert ordered.index(pkg.path) < ordered.index(mod.path)


def test_submodule_before_instantiator():
    sub = _make_info("sub", mods=["sub"])
    top = _make_info("top", mods=["top"], insts=["sub"])
    ordered = build_order([top, sub])  # given in wrong order
    assert ordered.index(sub.path) < ordered.index(top.path)


def test_chain_ordering():
    pkg = _make_info("pkg", pkgs=["pkg_types"])
    alu = _make_info("alu", imports=["pkg_types"], mods=["alu"])
    core = _make_info("core", mods=["core"], insts=["alu"])
    top = _make_info("top", mods=["top"], insts=["core"])
    ordered = build_order([top, core, alu, pkg])  # scrambled
    idx = {p.name.split(".")[0]: i for i, p in enumerate(ordered)}
    assert idx["pkg"] < idx["alu"] < idx["core"] < idx["top"]


def test_cycle_emits_warning_not_exception():
    a = _make_info("a", mods=["a"], insts=["b"])
    b = _make_info("b", mods=["b"], insts=["a"])
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        ordered = build_order([a, b])
    assert any(issubclass(x.category, CycleWarning) for x in w)
    assert len(ordered) == 2  # both files still included


def test_no_dependencies_preserves_all_files():
    a = _make_info("a", mods=["a"])
    b = _make_info("b", mods=["b"])
    ordered = build_order([a, b])
    assert set(ordered) == {a.path, b.path}
