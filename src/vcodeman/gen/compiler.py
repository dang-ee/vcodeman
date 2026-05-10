import re
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CompileError:
    file: str | None
    line: int | None
    message: str
    raw: str


@dataclass
class CompileResult:
    success: bool
    errors: list[CompileError] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""


_ICARUS_ERROR_RE = re.compile(r"^(.+?):(\d+):\s+(?:error|warning):\s+(.+)$")


class SimulatorBackend(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def compile_cmd(self, filelist: Path, top_module: str | None = None) -> list[str]: ...

    @abstractmethod
    def parse_errors(self, stdout: str, stderr: str, rc: int) -> list[CompileError]: ...

    def top_directive(self, module: str) -> str | None:
        """Return a .f-file directive for top module, or None if CLI-arg only."""
        return None

    def compile(self, filelist: Path, top_module: str | None = None) -> CompileResult:
        cmd = self.compile_cmd(filelist, top_module)
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120
            )
        except FileNotFoundError as e:
            err = CompileError(file=None, line=None,
                               message=f"Simulator not found: {cmd[0]}: {e}", raw=str(e))
            return CompileResult(success=False, errors=[err])

        errors = self.parse_errors(proc.stdout, proc.stderr, proc.returncode)
        return CompileResult(
            success=(proc.returncode == 0),
            errors=errors,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )


class IcarusBackend(SimulatorBackend):
    name = "icarus"
    _wrapper = "eda-env"

    def compile_cmd(self, filelist: Path, top_module: str | None = None) -> list[str]:
        cmd = [self._wrapper, "iverilog", "-g2012", "-o", "/dev/null", "-f", str(filelist)]
        if top_module:
            cmd.extend(["-s", top_module])
        return cmd

    def parse_errors(self, stdout: str, stderr: str, rc: int) -> list[CompileError]:
        if rc == 0:
            return []
        errors: list[CompileError] = []
        for line in stderr.splitlines():
            m = _ICARUS_ERROR_RE.match(line.strip())
            if m:
                errors.append(CompileError(
                    file=m.group(1),
                    line=int(m.group(2)),
                    message=m.group(3),
                    raw=line,
                ))
            elif line.strip():
                errors.append(CompileError(file=None, line=None,
                                           message=line, raw=line))
        return errors


BACKENDS: dict[str, type[SimulatorBackend]] = {
    "icarus": IcarusBackend,
}


import importlib.util
import sys


def resolve_backend(spec: str) -> type[SimulatorBackend]:
    """Resolve a backend spec to a SimulatorBackend subclass.

    Spec is one of:
      - a name registered in BACKENDS (e.g. "icarus")
      - a path to a .py file containing a SimulatorBackend subclass
      - "<path>:<ClassName>" to disambiguate when the file has multiple
    """
    looks_like_path = "/" in spec or spec.endswith(".py") or spec.startswith(".")
    if not looks_like_path:
        if spec not in BACKENDS:
            raise KeyError(
                f"Unknown backend: {spec!r}. Available: {sorted(BACKENDS)}"
            )
        return BACKENDS[spec]

    if ":" in spec:
        path_str, class_name = spec.rsplit(":", 1)
    else:
        path_str, class_name = spec, None
    path = Path(path_str).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Backend file not found: {path}")

    module_name = f"vcodeman_user_backend_{path.stem}"
    spec_obj = importlib.util.spec_from_file_location(module_name, path)
    if spec_obj is None or spec_obj.loader is None:
        raise ImportError(f"Cannot load backend from {path}")
    mod = importlib.util.module_from_spec(spec_obj)
    sys.modules[module_name] = mod
    spec_obj.loader.exec_module(mod)

    if class_name:
        cls = getattr(mod, class_name, None)
        if cls is None:
            raise AttributeError(f"{path} has no class {class_name!r}")
        return cls

    candidates = [
        v for v in vars(mod).values()
        if isinstance(v, type)
        and issubclass(v, SimulatorBackend)
        and v is not SimulatorBackend
    ]
    if not candidates:
        raise ValueError(f"No SimulatorBackend subclass in {path}")
    if len(candidates) > 1:
        raise ValueError(
            f"{path} has multiple SimulatorBackend subclasses "
            f"({[c.__name__ for c in candidates]}); use 'path:ClassName' to pick one"
        )
    return candidates[0]
