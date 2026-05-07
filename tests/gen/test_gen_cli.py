import shutil
import pytest
from pathlib import Path
from click.testing import CliRunner
from vcodeman.cli import cli


pytestmark = pytest.mark.skipif(
    not shutil.which("eda-env"),
    reason="eda-env not available in this environment"
)


def test_gen_creates_output_files(simple_dir, tmp_path):
    runner = CliRunner()
    out = tmp_path / "test.f"
    result = runner.invoke(cli, [
        "gen", str(simple_dir),
        "-o", str(out),
        "--no-compile",
    ])
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert Path(str(out) + ".tops.txt").exists()
    assert Path(str(out) + ".macros.yaml").exists()


def test_gen_filelist_has_correct_order(simple_dir, tmp_path):
    runner = CliRunner()
    out = tmp_path / "test.f"
    runner.invoke(cli, ["gen", str(simple_dir), "-o", str(out), "--no-compile"])
    lines = [l for l in out.read_text().splitlines() if l and not l.startswith("//")]
    sv_lines = [l for l in lines if l.endswith(".sv")]
    names = [Path(l).stem for l in sv_lines]
    assert names.index("pkg_types") < names.index("alu")
    assert names.index("alu") < names.index("core")
    assert names.index("core") < names.index("top")


def test_gen_tops_file_contains_top(simple_dir, tmp_path):
    runner = CliRunner()
    out = tmp_path / "test.f"
    runner.invoke(cli, ["gen", str(simple_dir), "-o", str(out), "--no-compile"])
    tops = Path(str(out) + ".tops.txt").read_text()
    assert "top" in tops


def test_gen_macros_file_has_simulation(simple_dir, tmp_path):
    runner = CliRunner()
    out = tmp_path / "test.f"
    runner.invoke(cli, ["gen", str(simple_dir), "-o", str(out), "--no-compile"])
    import yaml
    macros = yaml.safe_load(Path(str(out) + ".macros.yaml").read_text())
    names = [d["name"] for d in macros["definitions"]]
    assert "SIMULATION" in names


def test_gen_compile_succeeds(simple_dir, tmp_path):
    runner = CliRunner()
    out = tmp_path / "test.f"
    result = runner.invoke(cli, [
        "gen", str(simple_dir),
        "-o", str(out),
        "--no-ai",
    ])
    assert result.exit_code == 0, result.output
