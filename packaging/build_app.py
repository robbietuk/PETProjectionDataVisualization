# SPDX-License-Identifier: Apache-2.0
"""Freeze the viewer with STIR included, self-test the result and optionally archive it.

Run with the python of an environment made from packaging/environment-app.yml:

    python packaging/build_app.py [--sample FILE.hs] [--archive]

Results, in dist/:
    macOS    PETProjectionDataVisualization.app   (ad-hoc signed)     archive: .zip (ditto)
    Windows  PETProjectionDataVisualization/      (one folder, .exe)  archive: .zip
    Linux    PETProjectionDataVisualization/      (one folder)        archive: .tar.gz

The self-test runs the frozen executable headless (QT_QPA_PLATFORM=offscreen) on the demo data, and on
``--sample`` (or $STIR_TEST_PROJDATA) when given. It fails unless ``stir`` is imported from inside
the bundle.
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
NAME = "PETProjectionDataVisualization"


def run(*cmd: str | os.PathLike, **kw) -> None:
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def freeze(dist: Path, work: Path) -> Path:
    """Run PyInstaller; return the bundle (macOS .app) or one-folder build directory."""
    env = dict(os.environ)
    if sys.platform == "win32":  # conda DLLs (STIR's dependencies, Qt) live in Library/bin
        env["PATH"] = os.pathsep.join([str(Path(sys.prefix) / "Library" / "bin"), env.get("PATH", "")])
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "WARN",
        "--distpath", dist, "--workpath", work, HERE / f"{NAME}.spec", env=env)
    if sys.platform == "darwin":
        shutil.rmtree(dist / NAME, ignore_errors=True)  # intermediate folder; the .app has the same files
        app = dist / f"{NAME}.app"
        # ad-hoc signature: needed for arm64 binaries to run at all (not a Developer ID signature)
        run("codesign", "--force", "--deep", "-s", "-", app)
        run("codesign", "--verify", "--deep", "--strict", app)
        return app
    return dist / NAME


def executable(bundle: Path) -> Path:
    if sys.platform == "darwin":
        return bundle / "Contents" / "MacOS" / NAME
    return bundle / (NAME + (".exe" if sys.platform == "win32" else ""))


def self_test(bundle: Path, args: list[str], tag: str, out_dir: Path) -> None:
    log = out_dir / f"selftest_{tag}.txt"
    png = out_dir / f"selftest_{tag}.png"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PETPDV_SELF_TEST="1", PETPDV_SELF_TEST_LOG=str(log))
    env.pop("STIR_CONFIG_DIR", None)  # test the bundle's own config, not the build machine's
    print(f"== self-test ({tag})", flush=True)
    proc = subprocess.run([str(executable(bundle)), *args, "--out", str(png)], env=env, timeout=300)
    report = log.read_text(encoding="utf-8", errors="replace") if log.exists() else "(no report)"
    print(report, flush=True)
    if proc.returncode != 0:
        raise SystemExit(f"self-test {tag} failed with exit status {proc.returncode}")
    stir_line = next((ln for ln in report.splitlines() if ln.startswith("stir imported from ")), "")
    stir_file = Path(stir_line.removeprefix("stir imported from ").strip())
    if not stir_line or not stir_file.resolve().is_relative_to(bundle.resolve()):
        raise SystemExit(f"self-test {tag}: stir was not imported from inside {bundle} ({stir_line!r})")
    if not png.exists():
        raise SystemExit(f"self-test {tag}: no screenshot written")


def archive(bundle: Path, dist: Path) -> Path:
    system = {"darwin": "macos", "win32": "windows"}.get(sys.platform, "linux")
    stem = dist / f"{NAME}-{system}-{platform.machine().lower()}"
    if sys.platform == "darwin":  # ditto keeps the framework symlinks and the signature intact
        out = stem.with_suffix(".zip")
        run("ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", bundle, out)
        return out
    fmt = "zip" if sys.platform == "win32" else "gztar"
    return Path(shutil.make_archive(str(stem), fmt, root_dir=bundle.parent, base_dir=bundle.name))


def size_of(path: Path) -> str:
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file() and not f.is_symlink())
    return f"{total / 1e6:.0f} MB"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--sample", default=os.environ.get("STIR_TEST_PROJDATA") or None,
                   help="projection data (.hs) to open in the self-test (default: $STIR_TEST_PROJDATA)")
    p.add_argument("--archive", action="store_true", help="also write the zip/tar.gz next to the build")
    p.add_argument("--dist", type=Path, default=ROOT / "dist")
    p.add_argument("--work", type=Path, default=ROOT / "build" / "pyinstaller")
    args = p.parse_args()

    import stir  # fail early, with a clear message, in an environment without STIR

    print(f"== {platform.system()} {platform.machine()}, python {sys.version.split()[0]}, "
          f"stir from {stir.__file__}", flush=True)
    bundle = freeze(args.dist, args.work)
    out_dir = args.work.parent
    self_test(bundle, ["--demo"], "demo", out_dir)
    if args.sample:
        self_test(bundle, [args.sample], "stir", out_dir)
    print(f"== built {bundle} ({size_of(bundle)})", flush=True)
    if args.archive:
        out = archive(bundle, args.dist)
        print(f"== archive {out} ({out.stat().st_size / 1e6:.0f} MB)", flush=True)


if __name__ == "__main__":
    main()
