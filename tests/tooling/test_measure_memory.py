# SPDX-License-Identifier: Apache-2.0
"""scripts/measure_memory.py, on data small enough for the test suite."""
import importlib.util
import pathlib

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("measure_memory", ROOT / "scripts" / "measure_memory.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mm = _load()


def small_source():
    return mm.SyntheticTofSource(tof_bins=5, views=8, tangential=9, rings=6, max_segment=2)


def test_synthetic_source_has_the_requested_shape_and_known_values():
    src = small_source()
    i = src.info
    assert i.num_tof_bins == 5 and i.num_views == 8 and i.num_tangential == 9 and list(i.segments) == [-2, -1, 0, 1, 2]
    assert i.num_axial(0) == 6 and i.num_axial(-2) == 4
    seg = src.get_segment(-1, i.min_tof)
    assert seg.shape == i.expected_shape(-1) and seg.dtype == np.float32 and np.all(seg == 2.0)
    assert src.get_sinogram(0, 3, i.max_tof).shape == (8, 9) and src.reads == 1


def test_run_reports_every_step_and_no_rereads_of_a_cached_slice():
    lines = []
    seg = 8 * 6 * 9 * 4
    rows = mm.run(small_source(), cache_bytes=3 * seg, report=lines.append)
    assert [r["step"] for r in rows][0] == "open (first slice)" and len(rows) == 8
    assert rows[-1]["rereads"] == 0
    assert all(r["cached_mib"] * mm.MIB <= 3 * seg for r in rows)
    assert any("re-reads" in line for line in lines)


def test_main_parses_the_options(capsys):
    assert mm.main(["--tof-bins", "3", "--views", "4", "--tangential", "5", "--rings", "3",
                    "--max-segment", "1", "--cache-size", "-1"]) == 0
    assert "cache budget: unlimited" in capsys.readouterr().out
