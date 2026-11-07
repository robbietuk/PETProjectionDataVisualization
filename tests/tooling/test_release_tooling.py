# SPDX-License-Identifier: Apache-2.0
"""scripts/release_notes.py: semantic version tags, tag == built version, changelog section."""
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
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


def _pyproject_tag_regex():
    import re
    import tomllib
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return re.compile(data["tool"]["hatch"]["version"]["raw-options"]["tag_regex"])


@pytest.mark.parametrize("tag", ["v1.0.0", "v2.10.3", "v2.0.0rc1", "v1.2.3a0", "v1.0.0b12", "1.0.0", "v1.0",
                                 "v01.0.0", "v1.0.0-rc1", "v1.0.0.rc1", "v1.0.0-beta", "vX", "test-junk"])
def test_hatch_vcs_and_release_check_accept_exactly_the_same_tags(tag):
    """The git tag is the source of truth: a tag hatch-vcs builds from must also pass the release check."""
    hatch = _pyproject_tag_regex().match(tag)
    release = rn.TAG.match(tag)
    assert bool(hatch) is bool(release), tag
    if hatch:
        assert hatch.group("version") == release.group("version")


def test_a_release_candidate_uses_its_own_section_or_unreleased(tmp_path):
    log = tmp_path / "CHANGELOG.md"
    log.write_text("# Changelog\n\n## [Unreleased]\n\n- coming soon\n\n## [1.0.0] - 2026-11-10\n\n- first\n")
    out = tmp_path / "notes.md"
    assert rn.main(["v1.1.0rc1", "--changelog", str(log), "--out", str(out)]) == 0
    assert out.read_text() == "- coming soon\n"
    log.write_text("# Changelog\n\n## [Unreleased]\n\n## [1.1.0rc1] - 2026-11-12\n\n- rc notes\n")
    assert rn.main(["v1.1.0rc1", "--changelog", str(log), "--out", str(out)]) == 0
    assert out.read_text() == "- rc notes\n"
    assert rn.main(["v1.1.0", "--changelog", str(log)]) == 1          # a final release needs its own section


def test_changelog_headings_are_well_formed():
    import re
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    heads = re.findall(r"^## (.*)$", text, re.M)
    assert heads and heads[0] == "[Unreleased]"
    for h in heads[1:]:
        assert re.fullmatch(r"\[\d+\.\d+\.\d+((a|b|rc)\d+)?\] - \d{4}-\d{2}-\d{2}", h), h
    for sub in re.findall(r"^### (.*)$", text, re.M):
        assert sub in {"Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"}, sub
