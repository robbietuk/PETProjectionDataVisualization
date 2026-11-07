# SPDX-License-Identifier: Apache-2.0
"""Third-party licence notices for the frozen app (imported by the PyInstaller spec).

Every file PyInstaller puts in the bundle is traced back to the conda package that installed it
(``<prefix>/conda-meta/*.json``). For each of those packages the licence files that conda-forge ships
in ``info/licenses`` (found through ``extracted_package_dir``, the package cache) are bundled under
``licenses/<package>/``. ``licenses/THIRD_PARTY.txt`` lists the package, version, SPDX licence,
home page and the exact conda-forge archive it came from. The source code of every package is
available from conda-forge (github.com/conda-forge/<feedstock>) and the upstream home page.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TypedDict


class _CondaRecord(TypedDict, total=False):
    """The fields used from a ``conda-meta/<package>.json`` file."""
    name: str
    version: str
    license: str
    url: str
    fn: str
    files: list[str]
    extracted_package_dir: str


class _About(TypedDict, total=False):
    """The fields used from a package's ``info/about.json``."""
    license: str
    home: str
    dev_url: str


def _owners(prefix: Path) -> tuple[dict[str, _CondaRecord], dict[str, str]]:
    records: dict[str, _CondaRecord] = {}
    owner: dict[str, str] = {}
    for meta in sorted((prefix / "conda-meta").glob("*.json")):
        try:
            rec: _CondaRecord = json.loads(meta.read_text())
        except (OSError, ValueError):
            continue
        name = rec.get("name")
        if not name:
            continue
        records[name] = rec
        for f in rec.get("files", []):
            owner[os.path.normcase(os.path.normpath(f))] = name
    return records, owner


def _relative(path: str, prefixes: list[str]) -> str | None:
    for candidate in {os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.realpath(path))}:
        for prefix in prefixes:
            if candidate.startswith(prefix + os.sep):
                return candidate[len(prefix) + 1:]
    return None


def license_datas(prefix: str | os.PathLike[str], sources: list[str], work_dir: str | os.PathLike[str],
                  extra: tuple[str, ...] = ("python",)) -> list[tuple[str, str, str]]:
    """TOC entries ``(dest, src, "DATA")`` with the licences of the conda packages that own ``sources``
    (plus ``extra`` packages, e.g. the interpreter), and a generated THIRD_PARTY.txt."""
    prefix = Path(prefix)
    records, owner = _owners(prefix)
    roots = sorted({os.path.normcase(str(prefix.absolute())), os.path.normcase(os.path.realpath(prefix))})
    used = {n for n in extra if n in records}
    for src in sources:
        rel = _relative(src, roots)
        if rel is not None and rel in owner:
            used.add(owner[rel])

    toc: list[tuple[str, str, str]] = []
    lines = ["Third-party software in this bundle (from conda-forge)", "=" * 56, ""]
    for name in sorted(used):
        rec = records[name]
        pkg_dir = Path(rec.get("extracted_package_dir") or "")
        about: _About = {}
        try:
            about = json.loads((pkg_dir / "info" / "about.json").read_text())
        except (OSError, ValueError):
            pass
        files: list[str] = []
        lic_dir = pkg_dir / "info" / "licenses"
        if lic_dir.is_dir():
            for f in sorted(p for p in lic_dir.rglob("*") if p.is_file()):
                dest = f"licenses/{name}/{f.relative_to(lic_dir).as_posix()}"
                toc.append((dest, str(f), "DATA"))
                files.append(dest)
        lines += [
            f"{name} {rec.get('version', '?')}",
            f"  licence: {rec.get('license') or about.get('license') or 'see licence files'}",
            f"  home:    {about.get('home') or about.get('dev_url') or '-'}",
            f"  package: {rec.get('url') or rec.get('fn') or '-'}",
            "  files:   " + (", ".join(files) if files else "(none shipped by the package)"),
            "",
        ]
    out = Path(work_dir) / "THIRD_PARTY.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    toc.append(("licenses/THIRD_PARTY.txt", str(out), "DATA"))
    return toc
