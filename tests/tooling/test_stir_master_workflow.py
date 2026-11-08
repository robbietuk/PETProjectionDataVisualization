# SPDX-License-Identifier: Apache-2.0
"""The proposed STIR-master workflow (docs/workflows/stir-master.yml) and its tracking-issue helper."""
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci_tracking_issue.sh"
WORKFLOW = ROOT / "docs" / "workflows" / "stir-master.yml"

needs_bash = pytest.mark.skipif(shutil.which("bash") is None or sys.platform == "win32",
                                reason="run by a bash step in CI")

# A stand-in for `gh`: logs each call, and answers `gh issue list` with $FAKE_OPEN (the open issue number).
FAKE_GH = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$FAKE_LOG"
if [ "$1 $2" = "issue list" ]; then printf '%s' "$FAKE_OPEN"; fi
"""


def _track(tmp_path, mode, open_issue):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(FAKE_GH)
    gh.chmod(0o755)
    body = tmp_path / "body.md"
    body.write_text("run URL and STIR SHA\n")
    log = tmp_path / "gh.log"
    log.unlink(missing_ok=True)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
           "FAKE_LOG": str(log), "FAKE_OPEN": open_issue}
    r = subprocess.run(["bash", str(SCRIPT), mode, "stir-master", "CI against STIR master is failing", str(body)],
                       env=env, capture_output=True, text=True)
    calls = log.read_text().splitlines() if log.exists() else []
    return r.returncode, calls


@needs_bash
def test_a_failure_without_an_open_issue_opens_one(tmp_path):
    code, calls = _track(tmp_path, "fail", "")
    assert code == 0
    assert calls[0].startswith("issue list --label stir-master --state open")
    assert any(c.startswith("label create stir-master") for c in calls)
    creates = [c for c in calls if c.startswith("issue create")]
    assert len(creates) == 1
    assert "--label stir-master" in creates[0]


@needs_bash
def test_a_failure_with_an_open_issue_comments_on_it_and_opens_none(tmp_path):
    code, calls = _track(tmp_path, "fail", "42")
    assert code == 0
    assert any(c.startswith("issue comment 42 --body-file") for c in calls)
    assert not any(c.startswith(("issue create", "label create")) for c in calls)


@needs_bash
def test_a_pass_closes_the_open_issue(tmp_path):
    code, calls = _track(tmp_path, "pass", "42")
    assert code == 0
    assert any(c.startswith("issue close 42 --comment run URL and STIR SHA") for c in calls)


@needs_bash
def test_a_pass_without_an_open_issue_changes_nothing(tmp_path):
    code, calls = _track(tmp_path, "pass", "")
    assert code == 0
    assert len(calls) == 1                                       # only the lookup


@needs_bash
def test_bad_arguments_are_rejected(tmp_path):
    assert _track(tmp_path, "maybe", "")[0] == 2
    assert subprocess.run(["bash", str(SCRIPT), "fail"], capture_output=True).returncode == 2


def test_workflow_triggers_permissions_and_build_options():
    yaml = pytest.importorskip("yaml")
    wf = yaml.safe_load(WORKFLOW.read_text())
    on = wf.get("on", wf.get(True))                              # YAML 1.1 reads a bare `on` as True
    assert set(on) == {"schedule", "workflow_dispatch"}
    assert on["schedule"][0]["cron"].split()[2:4] == ["*", "*"]  # weekly: a fixed weekday
    assert wf["permissions"] == {"contents": "read"}
    assert wf["jobs"]["report"]["permissions"] == {"contents": "read", "issues": "write"}
    assert "permissions" not in wf["jobs"]["stir-master"]
    build = next(s["run"] for s in wf["jobs"]["stir-master"]["steps"] if s.get("name") == "Build and install STIR")
    for option in ("-DBUILD_SWIG_PYTHON=ON", "-DDISABLE_ITK=ON", "-DDISABLE_CERN_ROOT=ON",
                   "-DCMAKE_CXX_COMPILER_LAUNCHER=ccache"):
        assert option in build
    text = WORKFLOW.read_text()
    assert "scripts/ci_tracking_issue.sh" in text and SCRIPT.exists()
    assert "${{ inputs.stir_ref" not in text.replace("STIR_REF: ${{ inputs.stir_ref", "")  # input only via env
