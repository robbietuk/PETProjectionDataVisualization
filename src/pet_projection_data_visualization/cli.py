# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""Command line entry point: ``pet-projection-data-visualization [file] [--demo] [--stir-path DIR]``."""
from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pet-projection-data-visualization",
        description="Interactive viewer for STIR projection data (sinograms, viewgrams, TOF bins).")
    p.add_argument("path", nargs="?", help="projection data header (*.hs), or a .npy/.npz array file")
    p.add_argument("-f", "--filename", dest="filename", metavar="FILE",
                   help="same as the positional PATH (option of the old stir.projdata_visualisation tool)")
    p.add_argument("--demo", action="store_true", help="show a synthetic TOF data set (needs no STIR)")
    p.add_argument("--stir-path", metavar="DIR",
                   help="directory containing the 'stir' python package, e.g. <install prefix>/python "
                        "(default: $STIR_PYTHON_PATH, else whatever 'import stir' finds)")
    p.add_argument("--theme", choices=("dark", "light"), default="dark", help="colour scheme (default: dark)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from .app import launch  # imported here so --help works without Qt
    return launch(args.filename or args.path, stir_path=args.stir_path, demo=args.demo, theme=args.theme)


if __name__ == "__main__":
    sys.exit(main())
