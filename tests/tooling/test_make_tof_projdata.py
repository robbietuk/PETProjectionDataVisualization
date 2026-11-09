# SPDX-License-Identifier: Apache-2.0
"""scripts/make_tof_projdata.py against a fake ``stir`` module. The real run is in
tests/stir_interface/test_real_stir_integration.py, which needs STIR."""
import importlib.util
import pathlib
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("make_tof_projdata", ROOT / "scripts" / "make_tof_projdata.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mk = _load()


class FakeScanner:
    def __init__(self, name, tof_bins):
        self.name, self.tof_bins = name, tof_bins

    def get_max_num_timing_poss(self):
        return self.tof_bins

    def get_num_detectors_per_ring(self):
        return 576


class FakeSegment:
    def __init__(self, segment, tof):
        self.segment, self.tof, self.value = segment, tof, None

    def fill(self, value):
        self.value = value


def make_fake_stir(scanners):
    calls = {}

    class Scanner:
        @staticmethod
        def get_scanner_from_name(name):
            return scanners.get(name, FakeScanner("Unknown", 1))

    class ProjDataInfo:
        @staticmethod
        def construct_proj_data_info(scanner, span, max_delta, views, tang, arc, mash):
            calls["info"] = (scanner.name, span, max_delta, views, tang, arc, mash)
            n = scanner.tof_bins // mash
            return types.SimpleNamespace(max_delta=max_delta, tof=(-(n // 2), -(n // 2) + n - 1))

    class ProjDataInMemory:
        def __init__(self, exam_info, info):
            self.info, self.segments = info, {}

        def get_min_segment_num(self):
            return -self.info.max_delta

        def get_max_segment_num(self):
            return self.info.max_delta

        def get_min_tof_pos_num(self):
            return self.info.tof[0]

        def get_max_tof_pos_num(self):
            return self.info.tof[1]

        def get_empty_segment_by_view(self, segment, make_odd, tof):
            return FakeSegment(segment, tof)

        def set_segment(self, seg):
            self.segments[(seg.segment, seg.tof)] = seg.value

        def write_to_file(self, path):
            calls["written"] = path

    class ImagingModality:
        PT = "PT"

        def __init__(self, kind):
            self.kind = kind

    stir = types.SimpleNamespace(Scanner=Scanner, ProjDataInfo=ProjDataInfo, ProjDataInMemory=ProjDataInMemory,
                                 ExamInfo=lambda *a: object(), ImagingModality=ImagingModality,
                                 SegmentIndices=lambda s, t: (s, t))
    return stir, calls


def test_fill_values_are_unique_per_segment_and_tof_bin():
    values = {mk.fill_value(s, k) for s in range(-3, 4) for k in range(-5, 6)}
    assert len(values) == 7 * 11 and min(values) > 0


@pytest.mark.parametrize("max_bins, wanted, mash", [(55, 5, 11), (55, 1, 27), (13, 5, 2), (4, 10, 1)])
def test_tof_mash_factor_leaves_about_the_wanted_number_of_bins(max_bins, wanted, mash):
    assert mk.tof_mash_factor(max_bins, wanted) == mash
    assert max_bins // mash >= 2


def test_tof_mash_factor_rejects_a_non_tof_scanner():
    with pytest.raises(ValueError):
        mk.tof_mash_factor(1, 5)


def test_first_tof_capable_scanner_is_used_and_unknown_names_are_skipped():
    stir, _ = make_fake_stir({"B": FakeScanner("B", 33), "C": FakeScanner("C", 55)})
    assert mk.find_tof_scanner(stir, ("A", "B", "C")).name == "B"
    with pytest.raises(RuntimeError, match="no.*TOF|TOF information"):
        mk.find_tof_scanner(stir, ("A", "D"))


def test_make_tof_projdata_fills_every_segment_and_tof_bin_and_writes(tmp_path):
    stir, calls = make_fake_stir({"Discovery 690": FakeScanner("Discovery 690", 55)})
    out = str(tmp_path / "tof.hs")
    pd = mk.make_tof_projdata(stir, out)
    assert calls["written"] == out
    assert calls["info"] == ("Discovery 690", 1, 1, 576 // 2 // 8, 101, False, 11)
    assert set(pd.segments) == {(s, k) for s in (-1, 0, 1) for k in range(-2, 3)}
    assert all(v == mk.fill_value(s, k) for (s, k), v in pd.segments.items())


def test_command_line_checks_its_arguments(tmp_path):
    with pytest.raises(SystemExit):
        mk.main([str(tmp_path / "tof.s")])               # must be the .hs header
    with pytest.raises(SystemExit):
        mk.main([str(tmp_path / "tof.hs"), "--tof-bins", "1"])


def test_command_line_runs_with_the_given_scanner(tmp_path, monkeypatch, capsys):
    stir, calls = make_fake_stir({"X": FakeScanner("X", 20)})
    monkeypatch.setattr(mk.importlib, "import_module", lambda name: stir)
    out = tmp_path / "sub" / "tof.hs"
    assert mk.main([str(out), "--scanner", "X", "--tof-bins", "4"]) == 0
    assert calls["written"] == str(out) and out.parent.is_dir()
    assert calls["info"][0] == "X" and calls["info"][-1] == 5
    assert "TOF bins -2..1" in capsys.readouterr().out
