# SPDX-License-Identifier: Apache-2.0
"""scripts/release_notes.py: semantic version tags, tag == built version, changelog section."""
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("release_notes", ROOT / "scripts" / "release_notes.py")
rn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rn)

LOG = """# Changelog

## [Unreleased]

## [1.1.0] - 2026-12-01

### Added
- thing

## [1.0.0] - 2026-11-10

- first

[Unreleased]: https://example.com
"""


@pytest.mark.parametrize("tag, ok", [("v1.0.0", True), ("v2.10.3", True), ("v2.0.0rc1", True), ("1.0.0", False),
                                     ("v1.0", False), ("v01.0.0", False), ("vX", False), ("v1.0.0-beta", False)])
def test_only_semantic_version_tags_are_accepted(tag, ok):
    assert bool(rn.TAG.match(tag)) is ok


def test_changelog_section_is_extracted_up_to_the_next_heading():
    assert rn.changelog_section(LOG, "1.1.0") == "### Added\n- thing"
    assert rn.changelog_section(LOG, "1.0.0") == "- first"
    assert rn.changelog_section(LOG, "9.9.9") is None


def _dist(tmp_path, version):
    d = tmp_path / "dist"
    d.mkdir()
    (d / f"petprojectiondatavisualization-{version}-py3-none-any.whl").write_bytes(b"")
    (d / f"petprojectiondatavisualization-{version}.tar.gz").write_bytes(b"")
    return d


def test_release_passes_when_tag_dist_and_changelog_agree(tmp_path):
    log = tmp_path / "CHANGELOG.md"
    log.write_text(LOG)
    out = tmp_path / "notes.md"
    assert rn.main(["v1.1.0", "--dist", str(_dist(tmp_path, "1.1.0")), "--changelog", str(log), "--out", str(out)]) == 0
    assert out.read_text() == "### Added\n- thing\n"


def test_release_fails_on_a_version_mismatch_or_a_missing_changelog_entry(tmp_path, capsys):
    log = tmp_path / "CHANGELOG.md"
    log.write_text(LOG)
    assert rn.main(["v1.1.0", "--dist", str(_dist(tmp_path, "1.1.1.dev2+gabc")), "--changelog", str(log)]) == 1
    assert "but the tag says 1.1.0" in capsys.readouterr().out
    assert rn.main(["v3.0.0", "--changelog", str(log)]) == 1
    assert "no '## [3.0.0]' section" in capsys.readouterr().out


def test_the_real_changelog_has_an_unreleased_section():
    assert "## [Unreleased]" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
