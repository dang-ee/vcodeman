from pathlib import Path
from vcodeman.gen.writer import render_filelist


def test_incdir_first():
    inc = [Path("/inc/dir")]
    pkg = [Path("/rtl/pkg.sv")]
    src = [Path("/rtl/mod.sv")]
    text = render_filelist(inc, pkg, src)
    lines = text.splitlines()
    incdir_line = next(i for i, l in enumerate(lines) if "+incdir+" in l)
    pkg_line = next(i for i, l in enumerate(lines) if "pkg.sv" in l)
    assert incdir_line < pkg_line


def test_packages_before_sources():
    pkg = [Path("/rtl/pkg.sv")]
    src = [Path("/rtl/mod.sv")]
    text = render_filelist([], pkg, src)
    lines = text.splitlines()
    pkg_line = next(i for i, l in enumerate(lines) if "pkg.sv" in l)
    src_line = next(i for i, l in enumerate(lines) if "mod.sv" in l)
    assert pkg_line < src_line


def test_top_directive_included():
    text = render_filelist([], [], [Path("/rtl/top.sv")], top_module="my_top",
                           top_directive=None)
    assert "// -top my_top" in text


def test_top_directive_as_real_line():
    text = render_filelist([], [], [Path("/rtl/top.sv")], top_module="my_top",
                           top_directive="-top my_top")
    assert "-top my_top" in text
    assert "// -top my_top" not in text


def test_header_comment_present():
    text = render_filelist([], [], [])
    assert "vcodeman gen" in text


def test_no_comments_flag():
    text = render_filelist([], [Path("/rtl/pkg.sv")], [Path("/rtl/mod.sv")],
                           no_comments=True)
    assert "///" not in text
    assert "// ---" not in text
