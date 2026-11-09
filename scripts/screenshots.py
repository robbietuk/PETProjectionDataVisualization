# SPDX-License-Identifier: Apache-2.0
"""Headless screenshots of the main window with the demo data, in both themes and at two widths.

    QT_QPA_PLATFORM=offscreen python scripts/screenshots.py --out-dir shots [--prefix after]

Writes ``<prefix>-<theme>-<width>.png`` for the dark and light themes at a normal (1320 px) and a
narrow (760 px) width. Used for the before/after evidence of visual changes in pull requests.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

WIDTHS = (1320, 760)
HEIGHT = 840


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", default="screenshots")
    p.add_argument("--prefix", default="shot")
    args = p.parse_args(argv)
    out_dir = Path(str(args.out_dir))
    out_dir.mkdir(parents=True, exist_ok=True)

    from PySide6 import QtWidgets

    from pet_projection_data_visualization.app import build
    from pet_projection_data_visualization.view.styling import apply_theme
    from pet_projection_data_visualization.view.theme import PALETTES

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    if not isinstance(app, QtWidgets.QApplication):
        print("a non-GUI application already exists", file=sys.stderr)
        return 1
    for name, palette in PALETTES.items():
        apply_theme(app, palette)
        vm, window = build(theme=name)
        if not vm.load_demo():
            print(f"load failed: {vm.error}", file=sys.stderr)
            return 1
        window.show()
        for width in WIDTHS:
            window.resize(width, HEIGHT)
            for _ in range(5):
                app.processEvents()
            path = out_dir / f"{args.prefix}-{name}-{width}.png"
            window.grab().save(str(path))
            print(path)
        window.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
