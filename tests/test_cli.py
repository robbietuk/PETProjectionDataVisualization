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
    assert p.parse_args([]).theme is None              # the theme of the last session (dark the first time)
    assert p.parse_args(["--theme", "light"]).theme == "light"
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
