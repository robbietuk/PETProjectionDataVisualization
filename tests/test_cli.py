# SPDX-License-Identifier: Apache-2.0
import pytest

from pet_projection_data_visualization.cli import build_parser


def test_positional_and_old_style_filename_options():
    p = build_parser()
    assert p.parse_args(["a.hs"]).path == "a.hs"
    assert p.parse_args(["-f", "b.hs"]).filename == "b.hs"          # the old tool's option
    assert p.parse_args(["--filename", "c.hs"]).filename == "c.hs"


def test_flags():
    a = build_parser().parse_args(["--demo", "--stir-path", "/opt/stir/python"])
    assert a.demo and a.stir_path == "/opt/stir/python" and a.path is None


def test_help_works_without_qt(capsys):
    with pytest.raises(SystemExit) as e:
        build_parser().parse_args(["-h"])
    assert e.value.code == 0 and "pet-projection-data-visualization" in capsys.readouterr().out


def test_theme_option():
    p = build_parser()
    assert p.parse_args([]).theme == "dark" and p.parse_args(["--theme", "light"]).theme == "light"
    with pytest.raises(SystemExit):
        p.parse_args(["--theme", "neon"])


def test_version_option_prints_the_package_version(capsys):
    import re

    from pet_projection_data_visualization import __version__
    with pytest.raises(SystemExit) as e:
        build_parser().parse_args(["--version"])
    out = capsys.readouterr().out.strip()
    assert e.value.code == 0 and out.endswith(__version__)
    # PEP 440, as produced by hatch-vcs from a vX.Y.Z tag (plus .devN+g<hash> between tags)
    assert re.fullmatch(r"\d+\.\d+\.\d+((a|b|rc)\d+)?(\.dev\d+)?(\+[0-9A-Za-z.]+)?|\d+\.\d+(\.dev\d+)?(\+[0-9A-Za-z.]+)?",
                        __version__), __version__


def test_cache_size_option_in_mib():
    p = build_parser()
    assert p.parse_args([]).cache_size == 1024 and p.parse_args(["--cache-size", "256"]).cache_size == 256
    assert p.parse_args(["--cache-size", "0"]).cache_size == 0
    for bad in ("-1", "lots", "1.5"):
        with pytest.raises(SystemExit):
            p.parse_args(["--cache-size", bad])


def test_cli_default_cache_size_is_the_model_default():
    from pet_projection_data_visualization.cli import DEFAULT_CACHE_MIB
    from pet_projection_data_visualization.model.dataset import DEFAULT_CACHE_BYTES
    assert DEFAULT_CACHE_MIB * (1 << 20) == DEFAULT_CACHE_BYTES


def test_main_passes_the_cache_size_in_bytes(monkeypatch):
    import sys
    import types

    from pet_projection_data_visualization.cli import main
    calls = []
    monkeypatch.setitem(sys.modules, "pet_projection_data_visualization.app",
                        types.SimpleNamespace(launch=lambda *a, **kw: calls.append((a, kw)) or 0))
    assert main(["--demo", "--cache-size", "3"]) == 0
    assert calls[0][1]["cache_bytes"] == 3 << 20
