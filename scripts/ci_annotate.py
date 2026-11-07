# SPDX-License-Identifier: Apache-2.0
"""Turn a failed pytest log into GitHub Actions error annotations.

Annotations are readable through the public API without signing in, unlike job logs, so a failure can be
diagnosed from the run's annotations alone. Usage (in a step with ``if: failure()``):

    python scripts/ci_annotate.py pytest.log
"""
from __future__ import annotations

import sys


def _escape(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main(path: str) -> int:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError as e:
        print(f"::error title=pytest::no log ({e})")
        return 0
    failed = [ln for ln in lines if ln.startswith(("FAILED ", "ERROR "))]
    for ln in failed[:8]:
        print(f"::error title=pytest::{_escape(ln[:900])}")
    tail = "\n".join(lines[-80:])[-3500:]
    print(f"::error title=pytest log tail::{_escape(tail)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "pytest.log"))
