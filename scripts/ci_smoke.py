# SPDX-License-Identifier: Apache-2.0
"""Headless smoke run used by CI: open the real window, load data, step through every slice mode,
save a screenshot, and exit non-zero on any failure.

    python scripts/ci_smoke.py --demo [--out shot.png]
    python scripts/ci_smoke.py path/to/file.hs [--out shot.png]

This plays the role STIR's CI gives to running ``examples/python/recon_demo_gradient.py``.
"""
from __future__ import annotations

import argparse
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("path", nargs="?")
    p.add_argument("--demo", action="store_true")
    p.add_argument("--out", default="ci_smoke.png")
    args = p.parse_args(argv)
    if not args.demo and not args.path:
        p.error("give a path or --demo")

    from PySide6 import QtWidgets

    from stir_projdata_viewer.app import build
    from stir_projdata_viewer.model import SliceMode

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    vm, window = build()
    ok = vm.load_demo() if args.demo else vm.load(args.path)
    if not ok:
        print(f"load failed: {vm.error}", file=sys.stderr)
        return 1
    window.resize(1200, 800)
    window.show()
    for mode in SliceMode:
        vm.set_slice_mode(mode)
        app.processEvents()
        if vm.error:
            print(f"{mode}: {vm.error}", file=sys.stderr)
            return 1
    if not window.grab().save(args.out):
        print(f"could not save {args.out}", file=sys.stderr)
        return 1
    print(f"ok: {vm.source_label}, screenshot in {args.out}")
    window.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
