# SPDX-License-Identifier: Apache-2.0
"""Runs only where the real ``stir`` module is importable, on a non-TOF and a TOF file.

* non-TOF: ``STIR_TEST_PROJDATA=/path/file.hs`` (default: STIR's own recon_demo/smalllong.hs);
  skipped when there is no such file.
* TOF: ``STIR_TEST_PROJDATA_TOF=/path/file.hs``; when it is not set, a small TOF file is written for the
  session with ``scripts/make_tof_projdata.py`` (STIR's test data has no TOF file). Never skipped: if that
  fails, the tests fail.
"""
import importlib.util
import os
import pathlib

import numpy as np
import pytest

stir = pytest.importorskip("stir")

from pet_projection_data_visualization.model import ProjDataset, Selection, SliceMode, TofMode  # noqa: E402
from pet_projection_data_visualization.stir_interface import open_stir_source  # noqa: E402
from pet_projection_data_visualization.stir_interface.swig_gateway import SwigStirGateway  # noqa: E402
from pet_projection_data_visualization.viewmodel import ViewerViewModel  # noqa: E402

from test_gateway_contract import check_handle_contract  # noqa: E402

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "make_tof_projdata.py"


def _make_tof_module():
    spec = importlib.util.spec_from_file_location("make_tof_projdata", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _non_tof_path() -> str:
    env = os.environ.get("STIR_TEST_PROJDATA")
    if env:
        return env
    try:
        return os.path.join(stir.get_STIR_examples_dir(), "recon_demo", "smalllong.hs")
    except Exception:  # noqa: BLE001
        return ""


@pytest.fixture(scope="session")
def tof_file(tmp_path_factory) -> tuple[str, bool]:
    """(path, generated): ``generated`` is True when the file was written here, with known fill values."""
    env = os.environ.get("STIR_TEST_PROJDATA_TOF")
    if env:
        return env, False
    path = str(tmp_path_factory.mktemp("tof") / "tof_small.hs")
    _make_tof_module().make_tof_projdata(stir, path)
    return path, True


@pytest.fixture(params=["non-tof", "tof"])
def projdata(request) -> str:
    if request.param == "tof":
        return request.getfixturevalue("tof_file")[0]
    path = _non_tof_path()
    if not os.path.exists(path):
        pytest.skip("no non-TOF projection data file available")
    return path


def _stir_segment(pd, segment: int, tof_bin: int):
    try:
        return pd.get_segment_by_view(segment, tof_bin)
    except TypeError:
        return pd.get_segment_by_view(stir.SegmentIndices(segment, tof_bin))


def test_real_handle_satisfies_the_contract(projdata):
    check_handle_contract(SwigStirGateway(stir_module=stir).open(projdata))


def test_axis_order_matches_stirs_own_accessors(projdata):
    """The assumption the whole viewer rests on: as_array() is (view, axial, tangential), in every TOF bin."""
    pd = stir.ProjData.read_from_file(projdata)
    for tof in sorted({pd.get_min_tof_pos_num(), pd.get_max_tof_pos_num()}):
        seg = _stir_segment(pd, 0, tof)
        arr = np.asarray(seg.as_array())
        lo, hi = pd.get_min_axial_pos_num(0), pd.get_max_axial_pos_num(0)
        for ax in (lo, (lo + hi) // 2, hi):
            np.testing.assert_array_equal(arr[:, ax - lo, :], np.asarray(seg.get_sinogram(ax).as_array()))
        for view in (pd.get_min_view_num(), pd.get_max_view_num()):
            np.testing.assert_array_equal(arr[view - pd.get_min_view_num()],
                                          np.asarray(seg.get_viewgram(view).as_array()))


def test_viewer_stack_on_real_data(projdata):
    src = open_stir_source(projdata, gateway=SwigStirGateway(stir_module=stir))
    ds = ProjDataset(src)
    for mode in SliceMode:
        img = ds.slice(Selection.initial(ds.info).with_slice_mode(mode))
        assert img.data.size > 0 and np.isfinite(img.data).all()
    summed = ds.segment_array(0, TofMode.SUM)
    assert summed.shape == ds.info.expected_shape(0)


def test_view_model_loads_a_real_file(projdata):
    from pet_projection_data_visualization.sources.loader import make_source
    vm = ViewerViewModel(make_source)
    assert vm.load(projdata) and vm.pane.image is not None and vm.error is None


# ---- TOF only ------------------------------------------------------------------------------------------
def test_tof_info_and_shapes_match_stir(tof_file):
    path, _ = tof_file
    pd = stir.ProjData.read_from_file(path)
    ds = ProjDataset(open_stir_source(path, gateway=SwigStirGateway(stir_module=stir)))
    i = ds.info
    assert i.is_tof
    assert (i.min_tof, i.max_tof) == (pd.get_min_tof_pos_num(), pd.get_max_tof_pos_num())
    assert i.num_tof_bins == pd.get_max_tof_pos_num() - pd.get_min_tof_pos_num() + 1 > 1
    for s in i.segments:
        assert i.expected_shape(s) == (pd.get_num_views(), pd.get_num_axial_poss(s), pd.get_num_tangential_poss())


def test_each_tof_bin_matches_stirs_own_segment(tof_file):
    path, generated = tof_file
    pd = stir.ProjData.read_from_file(path)
    handle = SwigStirGateway(stir_module=stir).open(path)
    lay = handle.layout()
    fill_value = _make_tof_module().fill_value
    for s in range(lay.min_segment, lay.max_segment + 1):
        for k in range(lay.min_tof, lay.max_tof + 1):
            ours = handle.read_segment(s, k)
            np.testing.assert_array_equal(ours, np.asarray(_stir_segment(pd, s, k).as_array(), dtype=np.float32))
            if generated:      # every (segment, TOF bin) holds its own constant: no bin or segment mixed up
                assert np.all(ours == np.float32(fill_value(s, k)))


def test_tof_sum_is_the_sum_over_bins_and_the_profile_has_one_value_per_bin(tof_file):
    path, generated = tof_file
    ds = ProjDataset(open_stir_source(path, gateway=SwigStirGateway(stir_module=stir)))
    i = ds.info
    for s in i.segments:
        by_bin = np.sum([ds.segment_array(s, TofMode.BIN, k).astype(np.float64) for k in i.tof_bins], axis=0)
        np.testing.assert_allclose(ds.segment_array(s, TofMode.SUM), by_bin, rtol=1e-6)
    a_lo, a_hi = i.axial_range(0)
    view, axial, tang = (i.min_view + i.max_view) // 2, (a_lo + a_hi) // 2, (i.min_tangential + i.max_tangential) // 2
    prof = ds.tof_profile(0, view, axial, tang)
    assert prof.shape == (i.num_tof_bins,)
    if generated:
        fill_value = _make_tof_module().fill_value
        np.testing.assert_array_equal(prof, [fill_value(0, k) for k in i.tof_bins])
