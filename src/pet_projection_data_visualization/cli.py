# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""Command line entry point: ``pet-projection-data-visualization [file] [--demo] [--stir-path DIR] [--cache-size MIB]``."""
from __future__ import annotations

import argparse
import sys

from . import __version__


DEFAULT_CACHE_MIB = 1024     # the model's DEFAULT_CACHE_BYTES; not imported, so --help stays light


def _cache_size(text: str) -> int:
    try:
        mib = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a whole number of MiB: {text!r}") from None
    if mib < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return mib


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
    p.add_argument("--cache-size", type=_cache_size, default=DEFAULT_CACHE_MIB, metavar="MIB",
                   help="memory for cached segments, in MiB (default: %(default)s). The least recently used "
                        "segments are dropped beyond it; 0 keeps only the last one read")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--theme", choices=("dark", "light"), default="dark", help="colour scheme (default: dark)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from .app import launch  # imported here so --help works without Qt
    return launch(args.filename or args.path, stir_path=args.stir_path, demo=args.demo, theme=args.theme,
                  cache_bytes=args.cache_size * (1 << 20))


if __name__ == "__main__":
    sys.exit(main())
