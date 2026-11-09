# SPDX-License-Identifier: Apache-2.0
"""Write a small TOF projection data file (``.hs`` + ``.s``) with the STIR Python bindings.

STIR's recon_test_pack has no TOF file, so the real-STIR tests make one:

    python scripts/make_tof_projdata.py out/tof_small.hs [--scanner "Discovery 690"] [--tof-bins 5]

The scanner comes from STIR's own list (the first TOF-capable one of ``DEFAULT_SCANNERS`` unless
``--scanner`` is given). Views and tangential positions are reduced so the file stays around a megabyte.
Every (segment, TOF bin) is filled with its own constant, ``fill_value``, so a test can tell whether
a reader mixed up TOF bins or segments.
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys
from types import ModuleType

from pet_projection_data_visualization.stir_interface.swig_gateway import StirObject

# Scanners in STIR's built-in list that carry TOF information (STIR >= 6.0). Tried in this order.
DEFAULT_SCANNERS: tuple[str, ...] = ("Discovery 690", "Discovery MI4", "Discovery MI3", "Discovery 710")


def fill_value(segment: int, tof_bin: int) -> float:
    """The constant in segment ``segment``, TOF bin ``tof_bin``: unique for |segment| < 50."""
    return float(1000 + 100 * tof_bin + segment)


def max_timing_poss(scanner: StirObject) -> int:
    """Number of unmashed TOF bins of a STIR scanner; 0 or 1 means not TOF."""
    getter = getattr(scanner, "get_max_num_timing_poss", None)
    if getter is None:
        return 0
    try:
        return int(getter())
    except Exception:  # noqa: BLE001 - an unknown scanner may not answer at all
        return 0


def find_tof_scanner(stir: ModuleType, names: tuple[str, ...]) -> StirObject:
    """The first scanner of ``names`` that STIR knows and that has more than one TOF bin."""
    for name in names:
        scanner = stir.Scanner.get_scanner_from_name(name)
        if max_timing_poss(scanner) > 1:
            return scanner
    raise RuntimeError(f"none of these STIR scanners has TOF information: {', '.join(names)}")


def tof_mash_factor(max_bins: int, wanted_bins: int) -> int:
    """TOF mashing factor that leaves about ``wanted_bins`` bins (at least 2) out of ``max_bins``."""
    if max_bins < 2:
        raise ValueError("the scanner has no TOF bins")
    wanted = min(max(wanted_bins, 2), max_bins)
    return max(1, max_bins // wanted)


def _empty_segment(stir: ModuleType, pd: StirObject, segment: int, tof_bin: int) -> StirObject:
    # same two overloads as SwigProjData._segment_by_view: (segment, make_odd, timing_pos), then SegmentIndices
    try:
        return pd.get_empty_segment_by_view(segment, False, tof_bin)
    except TypeError:
        return pd.get_empty_segment_by_view(stir.SegmentIndices(segment, tof_bin))


def _exam_info(stir: ModuleType) -> StirObject:
    try:
        return stir.ExamInfo(stir.ImagingModality(stir.ImagingModality.PT))
    except Exception:  # noqa: BLE001 - older bindings: default ExamInfo
        return stir.ExamInfo()


def make_tof_projdata(stir: ModuleType, path: str, scanner_names: tuple[str, ...] = DEFAULT_SCANNERS,
                      tof_bins: int = 5, view_mash: int = 8, num_tangential: int = 101,
                      max_ring_difference: int = 1) -> StirObject:
    """Build the TOF ProjData in memory, fill it and write it to ``path`` (``.hs``). Returns the ProjData."""
    scanner = find_tof_scanner(stir, scanner_names)
    mash = tof_mash_factor(max_timing_poss(scanner), tof_bins)
    num_views = max(1, int(scanner.get_num_detectors_per_ring()) // 2 // view_mash)
    info = stir.ProjDataInfo.construct_proj_data_info(scanner, 1, max_ring_difference, num_views,
                                                      num_tangential, False, mash)
    pd = stir.ProjDataInMemory(_exam_info(stir), info)
    for segment in range(int(pd.get_min_segment_num()), int(pd.get_max_segment_num()) + 1):
        for tof_bin in range(int(pd.get_min_tof_pos_num()), int(pd.get_max_tof_pos_num()) + 1):
            seg = _empty_segment(stir, pd, segment, tof_bin)
            seg.fill(fill_value(segment, tof_bin))
            pd.set_segment(seg)
    pd.write_to_file(path)
    return pd


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Write a small TOF projection data file with the STIR Python bindings.")
    p.add_argument("path", help="output Interfile header, e.g. tof_small.hs")
    p.add_argument("--scanner", action="append", help="STIR scanner name (may be repeated; default: a TOF list)")
    p.add_argument("--tof-bins", type=int, default=5, help="about this many TOF bins after mashing (default 5)")
    args = p.parse_args(argv)
    if not args.path.endswith(".hs"):
        p.error("the output path must end in .hs")
    if args.tof_bins < 2:
        p.error("--tof-bins must be at least 2")
    folder = os.path.dirname(os.path.abspath(args.path))
    os.makedirs(folder, exist_ok=True)

    stir = importlib.import_module("stir")      # only needed here, so --help works without STIR

    names = tuple(args.scanner) if args.scanner else DEFAULT_SCANNERS
    pd = make_tof_projdata(stir, args.path, names, args.tof_bins)
    print(f"wrote {args.path}: segments {pd.get_min_segment_num()}..{pd.get_max_segment_num()}, "
          f"TOF bins {pd.get_min_tof_pos_num()}..{pd.get_max_tof_pos_num()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
