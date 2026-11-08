# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""Where to look for STIR, the saved setting, and the helpers behind the STIR setup window.

No Qt and no ``import stir`` here (the import itself is in ``swig_gateway``; a test import runs in a
child process, because a compiled extension cannot be unloaded again).

Lookup order (``resolve_stir_path``):

1. ``--stir-path`` on the command line;
2. ``$STIR_PYTHON_PATH``;
3. the path saved by the setup window in the per-user config file (``config_file_path``);
4. nothing: plain ``import stir`` (e.g. conda-forge's ``stir`` in the active environment).

A path may be the folder holding the ``stir`` module (``<install prefix>/python`` of a source build),
the install prefix itself, or a conda environment; ``locate_stir`` works out which.
"""
from __future__ import annotations

import enum
import json
import os
import posixpath
import re
import subprocess
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Final, Mapping, Sequence, cast

from ..model.stir_setup import StirCheck

ENV_VAR: Final = "STIR_PYTHON_PATH"
CONFIG_DIR_ENV_VAR: Final = "PET_PDV_CONFIG_DIR"         # overrides the config folder (tests, portable setups)
RESTART_MARKER: Final = "PET_PDV_STIR_RESTARTED"         # set in a restarted viewer, so it restarts only once
APP_DIR_NAME: Final = "PETProjectionDataVisualization"
CONFIG_FILE_NAME: Final = "config.json"
_STIR_PATH_KEY: Final = "stir_path"
_PACKAGE: Final = __name__.split(".")[0]
_PYTHON_TAG = re.compile(r"(?:cpython-|cp)3(\d+)")
# what the dynamic loader or Python say when an extension was built for another Python version
_MISMATCH_HINTS = re.compile(r"compiled for|version mismatch|conflicts with this version of Python|"
                             r"undefined symbol: _?Py|PyInit__stir|python3\d+\.dll", re.IGNORECASE)

ExecFn = Callable[[str, list[str], dict[str, str]], object]


class StirPathSource(enum.Enum):
    CLI = "--stir-path"
    ENV = f"${ENV_VAR}"
    CONFIG = "the saved setting"


@dataclass(frozen=True)
class StirLocation:
    """``python_dir`` goes on ``sys.path``; ``prefix`` holds the ``lib`` and ``bin`` folders."""

    python_dir: str
    prefix: str


@dataclass(frozen=True)
class ResolvedStirPath:
    location: StirLocation
    source: StirPathSource


def current_python() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


# ---- the config file -------------------------------------------------------------------------
def config_dir(environ: Mapping[str, str] | None = None, platform: str | None = None,
               home: Path | None = None) -> Path:
    """The per-user config folder of the platform (what ``QStandardPaths.AppConfigLocation`` gives)."""
    env = os.environ if environ is None else environ
    plat = sys.platform if platform is None else platform
    if env.get(CONFIG_DIR_ENV_VAR):
        return Path(env[CONFIG_DIR_ENV_VAR]).expanduser()
    home = Path.home() if home is None else home
    if plat.startswith("win"):
        base = Path(env["APPDATA"]) if env.get("APPDATA") else home / "AppData" / "Roaming"
    elif plat == "darwin":
        base = home / "Library" / "Application Support"
    else:
        xdg = env.get("XDG_CONFIG_HOME", "")
        base = Path(xdg) if xdg and posixpath.isabs(xdg) else home / ".config"   # XDG: relative values are invalid;
        # POSIX rules, not the host's: ntpath.isabs("/x") is False since Python 3.13
    return base / APP_DIR_NAME


def config_file_path(environ: Mapping[str, str] | None = None, platform: str | None = None) -> Path:
    return config_dir(environ, platform) / CONFIG_FILE_NAME


def _read_config(file: Path) -> dict[str, object]:
    try:
        text = file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        warnings.warn(f"cannot read the settings file {file}: {exc}", RuntimeWarning, stacklevel=3)
        return {}
    try:
        data: object = json.loads(text)
    except ValueError as exc:
        warnings.warn(f"ignoring the settings file {file}: it is not valid JSON ({exc})", RuntimeWarning, stacklevel=3)
        return {}
    if not isinstance(data, dict):
        warnings.warn(f"ignoring the settings file {file}: it is not a JSON object", RuntimeWarning, stacklevel=3)
        return {}
    # json.loads gives str keys; the values are only ever inspected with isinstance
    return cast(dict[str, object], data)


def load_saved_path(file: Path | None = None) -> str | None:
    """The STIR path saved by the setup window, or None."""
    value = _read_config(config_file_path() if file is None else file).get(_STIR_PATH_KEY)
    return value if isinstance(value, str) and value.strip() else None


def save_path(stir_path: str, file: Path | None = None) -> Path:
    """Store ``stir_path`` (made absolute) in the config file, keeping any other settings. Returns the file."""
    file = config_file_path() if file is None else file
    data = _read_config(file)
    data[_STIR_PATH_KEY] = os.path.abspath(os.path.expanduser(stir_path))
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_name(file.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, file)     # atomic: a crash never leaves half a file
    return file


# ---- where STIR is ---------------------------------------------------------------------------
def _has_stir(folder: Path) -> bool:
    return (folder / "stir").is_dir() or (folder / "stir.py").is_file()


def locate_stir(path: str) -> StirLocation:
    """Find the folder holding the ``stir`` module from what the user gave: that folder itself, an install
    prefix (``<prefix>/python``) or a conda environment (``lib/python3.X/site-packages``, ``Lib/site-packages``).
    If none of them has ``stir``, the path is taken as the module folder (the import reports what is wrong)."""
    p = Path(os.path.abspath(os.path.expanduser(path)))
    if _has_stir(p):
        if p.name.lower() == "site-packages":       # chosen inside a conda environment: find its root
            up = 2 if p.parent.name.lower().startswith("python") else 1
            return StirLocation(str(p), str(p.parents[up]))
        return StirLocation(str(p), str(p.parent))
    site = f"python{current_python()}"
    for candidate in (p / "python", p / "lib" / site / "site-packages", p / "Lib" / "site-packages"):
        if _has_stir(candidate):
            return StirLocation(str(candidate), str(p))
    return StirLocation(str(p), str(p.parent))


def resolve_stir_path(cli: str | None, environ: Mapping[str, str], saved: str | None) -> ResolvedStirPath | None:
    """Where to import STIR from, by precedence (see the module), or None for a plain ``import stir``.

    The command line is an explicit request and is returned even if it does not exist (the import reports
    it). The environment variable and the saved setting are defaults: one that is not a folder is skipped
    with a warning."""
    if cli and cli.strip():
        return ResolvedStirPath(locate_stir(cli.strip()), StirPathSource.CLI)
    for value, source in ((environ.get(ENV_VAR), StirPathSource.ENV), (saved, StirPathSource.CONFIG)):
        if not value or not value.strip():
            continue
        location = locate_stir(value.strip())
        if os.path.isdir(location.python_dir):
            return ResolvedStirPath(location, source)
        warnings.warn(f"the STIR path from {source.value} ({value!r}) is not a directory; ignoring it",
                      RuntimeWarning, stacklevel=2)
    return None


def library_dirs(location: StirLocation) -> list[str]:
    """STIR's shared-library folders under the install prefix that exist."""
    return [d for d in (os.path.join(location.prefix, sub) for sub in ("lib", "lib64")) if os.path.isdir(d)]


def windows_dll_dirs(location: StirLocation) -> list[str]:
    """Python >= 3.8 on Windows ignores PATH for extension-module dependencies: these folders must be
    registered with ``os.add_dll_directory`` (``<prefix>/bin``, ``<prefix>/lib``, and conda's ``Library/bin``)."""
    subs = ("bin", "lib", os.path.join("Library", "bin"))
    return [d for d in (os.path.join(location.prefix, sub) for sub in subs) if os.path.isdir(d)]


def _prepend(env: dict[str, str], var: str, dirs: Sequence[str]) -> None:
    old = [p for p in env.get(var, "").split(os.pathsep) if p]
    env[var] = os.pathsep.join([*dirs, *(p for p in old if p not in dirs)])


def library_path_var(platform: str | None = None) -> str:
    """The variable the dynamic loader reads at process start-up."""
    plat = sys.platform if platform is None else platform
    if plat.startswith("win"):
        return "PATH"
    return "DYLD_LIBRARY_PATH" if plat == "darwin" else "LD_LIBRARY_PATH"


def build_stir_env(location: StirLocation, environ: Mapping[str, str] | None = None,
                   platform: str | None = None) -> dict[str, str]:
    """A copy of ``environ`` in which a new Python process finds STIR: ``PYTHONPATH`` and the library path
    (``LD_LIBRARY_PATH`` on Linux, ``DYLD_LIBRARY_PATH`` on macOS, ``PATH`` on Windows)."""
    plat = sys.platform if platform is None else platform
    env = dict(os.environ if environ is None else environ)
    _prepend(env, "PYTHONPATH", [location.python_dir])
    libs = windows_dll_dirs(location) if plat.startswith("win") else library_dirs(location)
    if libs:
        _prepend(env, library_path_var(plat), libs)
    return env


# ---- the Test button -------------------------------------------------------------------------
def extension_python_versions(python_dir: str) -> set[str]:
    """Python versions (``"3.12"``) the ``_stir`` extension in ``python_dir`` was built for, from its file
    name (``_stir.cpython-312-x86_64-linux-gnu.so``, ``_stir.cp312-win_amd64.pyd``). Empty if untagged."""
    found: set[str] = set()
    for folder in (Path(python_dir), Path(python_dir) / "stir"):
        if folder.is_dir():
            for f in folder.glob("_stir*"):
                found.update(f"3.{m.group(1)}" for m in _PYTHON_TAG.finditer(f.name))
    return found


def _mismatch(built_for: str) -> StirCheck:
    return StirCheck(False, f"This STIR was built for Python {built_for}, but the viewer runs Python "
                            f"{current_python()}. Use a STIR built for Python {current_python()}, or run the "
                            "viewer with the Python STIR was built for.", version_mismatch=True)


# run in the child process: argv = [python_dir, dll dirs...]
_IMPORT_SCRIPT: Final = """\
import os, sys
sys.path.insert(0, sys.argv[1])
for d in sys.argv[2:]:
    os.add_dll_directory(d)
import stir
print(getattr(stir, "__file__", "") or "")
"""


def check_stir(path: str, environ: Mapping[str, str] | None = None, platform: str | None = None,
               python: str = sys.executable, timeout: float = 60.0) -> StirCheck:
    """Try ``import stir`` from ``path`` in a child Python with the environment the viewer would use."""
    text = path.strip()
    if not text:
        return StirCheck(False, "Enter the folder of your STIR installation.")
    plat = sys.platform if platform is None else platform
    location = locate_stir(text)
    if not os.path.isdir(location.python_dir):
        return StirCheck(False, f"The folder {location.python_dir} does not exist.")
    if not _has_stir(Path(location.python_dir)):
        return StirCheck(False, f"There is no 'stir' Python module in {location.python_dir}. Choose the STIR "
                                "install folder (the one containing python/stir) or the conda environment.")
    versions = extension_python_versions(location.python_dir)
    if versions and current_python() not in versions:
        return _mismatch(", ".join(sorted(versions)))
    dll_dirs = windows_dll_dirs(location) if plat.startswith("win") else []
    try:
        result = subprocess.run([python, "-c", _IMPORT_SCRIPT, location.python_dir, *dll_dirs],
                                env=build_stir_env(location, environ, plat), capture_output=True, text=True,
                                timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return StirCheck(False, f"Could not run the test import: {exc}")
    if result.returncode == 0:
        where = result.stdout.strip().splitlines()[-1:] or [location.python_dir]
        return StirCheck(True, f"STIR imports correctly ({where[0]}).")
    lines = [ln for ln in result.stderr.strip().splitlines() if ln.strip()]
    reason = lines[-1] if lines else f"exit status {result.returncode}"
    if _MISMATCH_HINTS.search(result.stderr):
        return StirCheck(False, f"STIR does not match this Python ({current_python()}): {reason}",
                         version_mismatch=True)
    return StirCheck(False, f"Importing STIR failed: {reason}")


# ---- the restart after Save ------------------------------------------------------------------
def can_restart(environ: Mapping[str, str] | None = None, platform: str | None = None) -> bool:
    """Linux and macOS read the library path only at start-up, so the viewer restarts once after Save.
    Not on Windows (the DLL folders are registered in-process), and not twice."""
    env = os.environ if environ is None else environ
    plat = sys.platform if platform is None else platform
    return not plat.startswith("win") and not env.get(RESTART_MARKER)


def restart_command(args: Sequence[str], python: str = sys.executable, frozen: bool | None = None) -> list[str]:
    """The command line that starts the viewer again with ``args`` (a frozen app is its own executable)."""
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    return [python, *args] if is_frozen else [python, "-m", _PACKAGE, *args]


def restart_viewer(location: StirLocation, args: Sequence[str], environ: Mapping[str, str] | None = None,
                   platform: str | None = None, python: str = sys.executable,
                   exec_fn: ExecFn = os.execve) -> bool:
    """Replace this process with a new viewer that has STIR's library path set. Returns False, without
    doing anything, where no restart is needed or allowed (see ``can_restart``); with the real
    ``os.execve`` it does not return otherwise."""
    if not can_restart(environ, platform):
        return False
    env = build_stir_env(location, environ, platform)
    env[RESTART_MARKER] = "1"
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except (AttributeError, OSError, ValueError):   # no console (GUI launch) or already closed
            pass
    command = restart_command(args, python)
    exec_fn(command[0], command, env)
    return True


class StirSetupActions:
    """What the setup window does (the ``StirSetupService`` of the view model), plus the STIR path the
    loader should use now. ``restartable`` is False when the viewer was not started from the command line
    (e.g. ``launch()`` inside an IPython session, which a restart would end)."""

    def __init__(self, cli_path: str | None = None, theme: str | None = None, restartable: bool = False,
                 restart: Callable[[StirLocation, Sequence[str]], bool] = restart_viewer,
                 config_file: Path | None = None) -> None:
        self.stir_path = cli_path
        self._theme = theme
        self._restartable = restartable
        self._restart = restart
        self._config_file = config_file

    def initial_path(self) -> str:
        return self.stir_path or os.environ.get(ENV_VAR) or load_saved_path(self._config_file) or ""

    def test(self, path: str) -> StirCheck:
        return check_stir(path)

    def save(self, path: str) -> str:
        return str(save_path(path, self._config_file))

    def apply(self, path: str, file: str) -> None:
        """Use ``path`` from now on: restart with it (Linux, macOS), or return so the caller loads ``file``
        again in this process (Windows, a viewer that already restarted once, or one not started from the
        command line)."""
        self.stir_path = path          # beats a wrong --stir-path or $STIR_PYTHON_PATH in this session
        if self._restartable:
            args = ["--stir-path", path, *(["--theme", self._theme] if self._theme else []), "--", file]
            self._restart(locate_stir(path), args)
