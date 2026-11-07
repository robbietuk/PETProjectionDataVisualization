# SPDX-License-Identifier: Apache-2.0
"""Licence and header hygiene for the standalone project."""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY_FILES = [p for d in ("src", "tests", "scripts", "packaging") for p in (ROOT / d).rglob("*.py") if p.name != "_version.py"]


def test_every_python_file_has_an_spdx_line_and_no_stir_header():
    assert PY_FILES
    for p in PY_FILES:
        head = "\n".join(p.read_text(encoding="utf-8").splitlines()[:5])
        assert "SPDX-License-Identifier: Apache-2.0" in head, p
        assert "Part of STIR" not in head, p


def test_licence_files_exist_and_are_declared():
    assert "Apache License" in (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert (ROOT / "NOTICE").is_file()
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'license = "Apache-2.0"' in pyproject and '"LICENSE"' in pyproject


def test_package_is_marked_as_typed():
    """PEP 561: ``py.typed`` makes type checkers use the package's own annotations (the wheel ships it)."""
    assert (ROOT / "src" / "pet_projection_data_visualization" / "py.typed").is_file()
