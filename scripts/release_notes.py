# SPDX-License-Identifier: Apache-2.0
"""Release checks and notes, used by build.yml when a version tag is pushed.

    python scripts/release_notes.py v1.2.3 [--dist dist] [--out notes.md]

Fails (exit 1) unless:
* the tag is ``vMAJOR.MINOR.PATCH`` (optionally with ``aN``/``bN``/``rcN``), i.e. semantic versioning;
* every built file in ``--dist`` carries exactly that version (the git tag is the source of truth);
* CHANGELOG.md has a ``## [X.Y.Z]`` section, whose body is written to ``--out`` as the release notes.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

TAG = re.compile(r"^v(?P<version>(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)((a|b|rc)(0|[1-9]\d*))?)$")


def changelog_section(text: str, version: str) -> str | None:
    """Body of the ``## [version]`` section (up to the next ``## `` heading), or None."""
    m = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## |^\[[^\]]+\]: |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else None


def dist_versions(dist: pathlib.Path) -> dict[str, str]:
    out = {}
    for f in sorted(dist.iterdir()):
        if f.name.endswith(".whl"):
            out[f.name] = f.name.split("-")[1]
        elif f.name.endswith(".tar.gz"):
            out[f.name] = f.name[: -len(".tar.gz")].rsplit("-", 1)[1]
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("tag")
    p.add_argument("--dist", type=pathlib.Path)
    p.add_argument("--changelog", type=pathlib.Path, default=pathlib.Path("CHANGELOG.md"))
    p.add_argument("--out", type=pathlib.Path)
    a = p.parse_args(argv)

    m = TAG.match(a.tag)
    if not m:
        print(f"::error::tag {a.tag!r} is not a semantic version tag like v1.2.3")
        return 1
    version = m.group("version")
    ok = True
    if a.dist is not None:
        found = dist_versions(a.dist)
        if not found:
            print(f"::error::no wheel or sdist in {a.dist}")
            ok = False
        for name, v in found.items():
            if v != version:
                print(f"::error::{name} has version {v}, but the tag says {version}")
                ok = False
    notes = changelog_section(a.changelog.read_text(encoding="utf-8"), version)
    if not notes:
        print(f"::error::{a.changelog} has no '## [{version}]' section (rename [Unreleased] before tagging)")
        ok = False
    elif a.out is not None:
        a.out.write_text(notes + "\n", encoding="utf-8")
    if ok:
        print(f"release {version}: checks passed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
