# SPDX-License-Identifier: Apache-2.0
"""The cache budget of ``ProjDataset`` on large-shaped TOF data (issue #22)."""
import tracemalloc

import numpy as np
import pytest

from fakes import CountingSource, LazyTofSource, small_demo
from pet_projection_data_visualization.model import ProjDataset, Selection, TofMode
from pet_projection_data_visualization.model.cache import ByteBudget, LRUCache
from pet_projection_data_visualization.model.dataset import DEFAULT_CACHE_BYTES

REDUCTIONS = (TofMode.SUM, TofMode.MEAN, TofMode.MAX)


def seg_bytes(src) -> int:
    i = src.info
    return i.num_views * i.num_axial(0) * i.num_tangential * 4      # segment 0 is the largest


class _Discard(dict):
    def __setitem__(self, key, value):
        pass


def session(ds: ProjDataset, after_each=lambda: None, keep: bool = True) -> dict:
    """What a user does: play the bins, step through segments, switch modes, hover, lock to the global range.
    Returns every array shown (unless ``keep`` is False), keyed by what was asked, and calls ``after_each``
    after every step."""
    i, shown = ds.info, ({} if keep else _Discard())
    for k in i.tof_bins:
        shown[(0, TofMode.BIN, k)] = ds.segment_array(0, TofMode.BIN, k).copy()
        after_each()
    for s in i.segments:
        shown[(s, TofMode.BIN, i.min_tof)] = ds.segment_array(s, TofMode.BIN, i.min_tof).copy()
        after_each()
    for mode in REDUCTIONS:
        for s in i.segments:
            shown[(s, mode, None)] = ds.segment_array(s, mode).copy()
            after_each()
    for a in range(0, i.num_axial(1), 5):
        shown[("profile", a)] = ds.tof_profile(1, 3, a, 0)
        after_each()
    for mode in (TofMode.BIN, TofMode.SUM):
        shown[("global", mode)] = ds.global_range(Selection.initial(i).with_tof_mode(mode))
        after_each()
    return shown


# ---- ByteBudget / LRUCache -------------------------------------------------------------------
def test_shared_budget_evicts_the_least_recently_used_entry_of_any_cache():
    budget = ByteBudget(300)
    a, b = LRUCache(10, budget=budget), LRUCache(10, budget=budget)
    a.put("a1", np.zeros(100, np.uint8))
    b.put("b1", np.zeros(100, np.uint8))
    a.put("a2", np.zeros(100, np.uint8))
    assert a.get("a1") is not None                  # a1 now newer than b1
    b.put("b2", np.zeros(100, np.uint8))
    assert "b1" not in b and "a1" in a and "a2" in a and "b2" in b
    assert budget.nbytes == a.nbytes + b.nbytes == 300


def test_shared_budget_keeps_the_newest_entry_even_if_too_big():
    budget = ByteBudget(150)
    a, b = LRUCache(10, budget=budget), LRUCache(10, budget=budget)
    a.put("a", np.zeros(100, np.uint8))
    b.put("big", np.zeros(1000, np.uint8))
    assert len(a) == 0 and "big" in b and budget.nbytes == 1000
    a.put("a", np.zeros(100, np.uint8))             # and it goes as soon as something newer comes
    assert "big" not in b and budget.nbytes == 100


def test_zero_budget_keeps_only_the_last_entry():
    c = LRUCache(10, max_bytes=0)
    for i in range(3):
        c.put(i, np.zeros(10, np.uint8))
    assert len(c) == 1 and 2 in c


def test_peek_does_not_refresh_an_entry():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    assert c.peek("a") == 1 and c.peek("missing") is None
    c.put("c", 3)
    assert "a" not in c


def test_budget_arguments_are_checked():
    with pytest.raises(ValueError):
        ByteBudget(-1)
    with pytest.raises(ValueError):
        LRUCache(2, max_bytes=10, budget=ByteBudget(10))


# ---- ProjDataset -----------------------------------------------------------------------------
def test_default_budget_is_one_gib_for_all_caches_together():
    ds = ProjDataset(small_demo())
    assert ds.cache_bytes == DEFAULT_CACHE_BYTES == 1 << 30
    assert ds._raw.budget is ds._reduced.budget is ds._sinograms.budget is ds.budget


@pytest.mark.parametrize("segments_in_budget", [0, 1, 3.5, 12])
def test_all_caches_together_stay_within_the_budget(segments_in_budget):
    src = LazyTofSource()
    budget = int(segments_in_budget * seg_bytes(src))
    ds = ProjDataset(src, cache_bytes=budget)
    worst = []

    def check():
        held = ds._raw.nbytes + ds._reduced.nbytes + ds._sinograms.nbytes
        assert held == ds.cached_bytes
        worst.append(held)
        # within the budget, or one entry alone (the one just used) that is larger than it
        assert held <= budget or (len(ds._raw) + len(ds._reduced) + len(ds._sinograms) == 1), held

    session(ds, check)
    assert max(worst) > 0


def test_results_are_the_same_with_and_without_a_budget():
    small = session(ProjDataset(LazyTofSource(), cache_bytes=2 * seg_bytes(LazyTofSource())))
    unlimited = session(ProjDataset(LazyTofSource(), cache_bytes=None))
    assert small.keys() == unlimited.keys()
    for key in small:
        np.testing.assert_array_equal(small[key], unlimited[key], err_msg=str(key))


def test_reductions_match_numpy_on_large_tof_data():
    src = LazyTofSource()
    ds = ProjDataset(src, cache_bytes=seg_bytes(src))
    bins = np.stack([src.get_segment(1, k) for k in src.info.tof_bins])
    expected = (bins.sum(axis=0, dtype=np.float64), bins.mean(axis=0, dtype=np.float64), bins.max(axis=0))
    for mode, want in zip(REDUCTIONS, expected):
        np.testing.assert_allclose(ds.segment_array(1, mode), want, rtol=1e-6)


@pytest.mark.parametrize("mode", REDUCTIONS)
def test_a_reduction_does_not_keep_the_tof_bins(mode):
    src = LazyTofSource()
    ds = ProjDataset(src, cache_bytes=None)          # even with room for everything
    result = ds.segment_array(0, mode)
    assert len(ds._raw) == 0 and ds.cached_bytes == result.nbytes


def test_global_range_keeps_the_segment_being_viewed():
    src = CountingSource(LazyTofSource())
    ds = ProjDataset(src, cache_bytes=3 * seg_bytes(src))
    ds.segment_array(0, TofMode.SUM)
    ds.segment_array(0, TofMode.BIN, 2)
    before = ds.cached_bytes
    ds.global_range(Selection.initial(src.info))
    ds.global_range(Selection.initial(src.info).with_tof_mode(TofMode.MAX))
    assert ds.cached_bytes == before
    reads = src.reads
    ds.segment_array(0, TofMode.SUM)
    ds.segment_array(0, TofMode.BIN, 2)
    assert src.reads == reads


def test_going_back_to_a_cached_slice_does_not_read_again():
    src = CountingSource(LazyTofSource())
    ds = ProjDataset(src, cache_bytes=4 * seg_bytes(src))
    sel = Selection.initial(src.info)
    first = ds.slice(sel).data.copy()
    ds.segment_array(1, TofMode.BIN, src.info.min_tof)
    ds.segment_array(0, TofMode.SUM)
    reads = src.reads
    np.testing.assert_array_equal(ds.slice(sel).data, first)
    ds.segment_array(0, TofMode.SUM)
    assert src.reads == reads


def test_memory_stays_under_the_budget_with_large_fake_data():
    """Measured with tracemalloc (numpy reports its buffers to it): over a whole session the peak is the
    budget plus the working arrays of one reduction (float64 accumulator, one bin, the float32 result)."""
    src = LazyTofSource(tof_bins=33, views=96, tangential=129, rings=32, max_segment=4)
    one = seg_bytes(src)
    budget = 4 * one
    ds = ProjDataset(src, cache_bytes=budget)
    tracemalloc.start()
    try:
        base = tracemalloc.get_traced_memory()[0]
        session(ds, keep=False)
        peak = tracemalloc.get_traced_memory()[1] - base
    finally:
        tracemalloc.stop()
    assert ds.cached_bytes <= budget
    # 2 (float64 accumulator) + 1 (bin being added) + 1 (result) + 1 (the fake's workspace)
    # + 1 (the copy ``session`` makes)
    assert peak <= budget + 6 * one, (peak / one, budget / one)
    # and far below what all TOF bins of one segment would take (33 segments' worth)
    assert peak < src.info.num_tof_bins * one / 2
