# SPDX-License-Identifier: Apache-2.0
"""Create a self-contained conda-forge prefix holding STIR, Qt and PyInstaller.

    uv run --no-project --with 'py-rattler>=0.28' python packaging/make_env.py build/env

Uses py-rattler (the conda solver/installer library behind pixi, installed from PyPI by uv)
so that no conda/mamba installation and no shell-profile changes are needed.  Nothing is
written outside the given prefix and its sibling package cache.
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from rattler import Platform, VirtualPackage, install, solve

ENV_FILE = Path(__file__).with_name("environment-app.yml")


def read_specs(path: Path = ENV_FILE) -> list[str]:
    """The ``dependencies:`` list of a conda environment file (plain specs only, comments dropped)."""
    specs: list[str] = []
    in_deps = False
    for line in path.read_text().splitlines():
        text = line.split("#", 1)[0].rstrip()
        if not text:
            continue
        if not text.startswith(" "):
            in_deps = text.startswith("dependencies:")
        elif in_deps and text.lstrip().startswith("- "):
            specs.append(text.lstrip()[2:].strip())
    return specs


async def create(prefix: Path, specs: list[str]) -> None:
    records = await solve(
        sources=["conda-forge"],
        specs=specs,
        platforms=[Platform.current(), Platform("noarch")],
        virtual_packages=VirtualPackage.detect(),
    )
    for r in records:
        if r.name.normalized in {"python", "stir", "numpy", "pyside6", "qt6-main", "pyinstaller", "pyqtgraph"}:
            print(f"  {r.name.normalized:12} {r.version} {r.build}")
    await install(records, target_prefix=prefix, cache_dir=prefix.parent / "pkgs", show_progress=False)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("prefix", type=Path)
    p.add_argument("--spec", action="append", default=[], help="extra/override match spec")
    args = p.parse_args()
    prefix = args.prefix.resolve()
    prefix.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(create(prefix, read_specs() + args.spec))
    print(f"created {prefix}")


if __name__ == "__main__":
    main()
