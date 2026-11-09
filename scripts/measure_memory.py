# SPDX-License-Identifier: Apache-2.0
"""Measure the memory the viewer's data model uses on large, synthetic TOF data (no STIR, no Qt).

    python scripts/measure_memory.py [--tof-bins 33] [--views 272] [--tangential 415] [--rings 71]
                                     [--max-segment 4] [--cache-size 1024]

The data are generated on demand, one (segment, TOF bin) at a time, the way a STIR file is read, so only
what ``ProjDataset`` keeps is ever in memory. The script walks through what a user does (open, play the TOF
bins, step through segments, switch to Sum/Mean/Max, lock to the global range, go back to a slice seen
before) and prints, after each step:

* ``peak RSS``: the process's peak resident set size so far (``getrusage``; Linux and macOS only),
* ``peak traced``: the peak of Python and numpy allocations during that step (``tracemalloc``),
* ``cached``: the bytes held by the dataset's caches afterwards,
* the time the step took.

Run it once per setting in a fresh process: the peak RSS never goes down.
"""
from __future__ import annotations

import argparse
import sys
import time
import tracemalloc
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import numpy as np
import numpy.typing as npt

from pet_projection_data_visualization.model import ProjDataInfo, ProjDataset, Selection, TofMode

MIB = 1 << 20


class SyntheticTofSource:
    """A ``ProjDataSource`` that makes each (segment, TOF bin) when asked and keeps nothing.

    Segment ``s`` covers ``rings - |s|`` axial positions (span 1, like STIR's segments); every value of
    a (segment, bin) is ``1 + bin_index + |s|``, so results are easy to check."""

    def __init__(self, tof_bins: int, views: int, tangential: int, rings: int, max_segment: int) -> None:
        if not 0 <= max_segment < rings:
            raise ValueError("need 0 <= max_segment < rings")
        half = tangential // 2
        self.info = ProjDataInfo(
            name="synthetic TOF", min_segment=-max_segment, max_segment=max_segment,
            min_view=0, max_view=views - 1, min_tangential=-half, max_tangential=tangential - 1 - half,
            axial_ranges={s: (0, rings - abs(s) - 1) for s in range(-max_segment, max_segment + 1)},
            min_tof=-(tof_bins // 2), max_tof=tof_bins - 1 - tof_bins // 2)
        self.reads = 0

    def value(self, segment: int, tof_bin: int) -> float:
        return float(1 + tof_bin - self.info.min_tof + abs(segment))

    def get_segment(self, segment: int, tof_bin: int) -> npt.NDArray[np.float32]:
        self.reads += 1
        return np.full(self.info.expected_shape(segment), self.value(segment, tof_bin), dtype=np.float32)

    def get_sinogram(self, segment: int, axial: int, tof_bin: int) -> npt.NDArray[np.float32]:
        return np.full((self.info.num_views, self.info.num_tangential), self.value(segment, tof_bin),
                       dtype=np.float32)


def peak_rss_mib() -> float | None:
    """Peak resident set size of this process so far, in MiB (None where ``resource`` is missing)."""
    try:
        import resource
    except ImportError:          # Windows
        return None
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / MIB if sys.platform == "darwin" else peak / 1024    # bytes on macOS, KiB on Linux


def cached_mib(ds: ProjDataset) -> float:
    return ds.cached_bytes / MIB


@contextmanager
def step(name: str, ds: ProjDataset, rows: list[dict[str, object]]) -> Iterator[None]:
    tracemalloc.reset_peak()
    base = tracemalloc.get_traced_memory()[0]
    t0 = time.perf_counter()
    yield
    seconds = time.perf_counter() - t0
    rows.append({"step": name, "peak_rss_mib": peak_rss_mib(),
                 "peak_traced_mib": (tracemalloc.get_traced_memory()[1] - base) / MIB,
                 "cached_mib": cached_mib(ds), "seconds": seconds})


def run(src: SyntheticTofSource, cache_bytes: int | None,
        report: Callable[[str], None] = print) -> list[dict[str, object]]:
    """Walk through a typical session; returns one row per step (also printed through ``report``)."""
    info = src.info
    seg_mib = info.num_views * info.num_axial(0) * info.num_tangential * 4 / MIB
    report(f"data: {info.num_tof_bins} TOF bins, {info.num_views} views, {info.num_tangential} tangential, "
           f"segments {info.min_segment}..{info.max_segment}; segment 0 is {seg_mib:.1f} MiB per TOF bin, "
           f"{seg_mib * info.num_tof_bins:.0f} MiB for all bins; total {info.total_bins * 4 / MIB:.0f} MiB")
    report(f"cache budget: {'unlimited' if cache_bytes is None else f'{cache_bytes / MIB:.0f} MiB'}")
    report(f"start: peak RSS {peak_rss_mib() or float('nan'):.0f} MiB")
    tracemalloc.start()
    rows: list[dict[str, object]] = []
    ds = ProjDataset(src, cache_bytes=cache_bytes)
    sel = Selection.initial(info)
    with step("open (first slice)", ds, rows):
        ds.slice(sel)
    with step("play all TOF bins of segment 0", ds, rows):
        for k in info.tof_bins:
            ds.segment_array(0, TofMode.BIN, k)
    with step("step through all segments (one bin)", ds, rows):
        for s in info.segments:
            ds.segment_array(s, TofMode.BIN, info.min_tof)
    with step("switch to Sum, Mean, Max (segment 0)", ds, rows):
        for mode in (TofMode.SUM, TofMode.MEAN, TofMode.MAX):
            ds.segment_array(0, mode)
    with step("step through all segments in Sum", ds, rows):
        for s in info.segments:
            ds.segment_array(s, TofMode.SUM)
    with step("global range, single bins", ds, rows):
        ds.global_range(sel)
    with step("global range, Sum", ds, rows):
        ds.global_range(Selection.initial(info).with_tof_mode(TofMode.SUM))
    reads = src.reads
    with step("back to a cached slice (Sum, last segment)", ds, rows):
        ds.segment_array(info.max_segment, TofMode.SUM)
    rows[-1]["rereads"] = src.reads - reads
    tracemalloc.stop()
    report(f"{'step':45} {'peak RSS':>9} {'traced':>9} {'cached':>9} {'time':>8}")
    for r in rows:
        rss = r["peak_rss_mib"]
        report(f"{r['step']!s:45} {'n/a' if rss is None else f'{rss:.0f} MiB':>9} "
               f"{r['peak_traced_mib']:6.0f} MiB {r['cached_mib']:6.0f} MiB {r['seconds']:7.3f}s")
    report(f"re-reads when going back to the cached slice: {rows[-1]['rereads']}")
    return rows


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--tof-bins", type=int, default=33)
    p.add_argument("--views", type=int, default=272)
    p.add_argument("--tangential", type=int, default=415)
    p.add_argument("--rings", type=int, default=71, help="axial positions of segment 0")
    p.add_argument("--max-segment", type=int, default=4, help="segments -N..N")
    p.add_argument("--cache-size", type=int, default=1024, metavar="MIB",
                   help="cache budget in MiB (default 1024, the viewer's default); -1 for unlimited")
    return p


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    src = SyntheticTofSource(a.tof_bins, a.views, a.tangential, a.rings, a.max_segment)
    run(src, None if a.cache_size < 0 else a.cache_size * MIB)
    return 0


if __name__ == "__main__":
    sys.exit(main())
