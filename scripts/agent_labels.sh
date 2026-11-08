#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Creates (or updates) the labels the agent workflows use. Run once per repository, with the GitHub CLI:
#   scripts/agent_labels.sh [owner/repo]
set -euo pipefail
repo="${1:-robbietuk/PETProjectionDataVisualization}"

label() { gh label create "$1" --repo "$repo" --color "$2" --description "$3" --force; }

label "agent:triaged"           "c5def5" "The triage agent posted a summary and a plan"
label "agent:needs-info"        "fbca04" "The triage agent needs answers before work can start"
label "agent:approved"          "0e8a16" "Approved by the maintainer: the implement agent builds it"
label "agent:in-progress"       "1d76db" "An agent is implementing this issue"
label "agent:pr-open"           "5319e7" "An agent pull request is open for this issue"
label "agent:changes-requested" "d93f0b" "The review agent asked for changes"
label "agent:ready-to-merge"    "0e8a16" "The review agent approved and CI passed: the maintainer merges"
label "agent:needs-human"       "b60205" "The agents stopped: a person needs to look"
label "agent:autofix"           "bfdadc" "Lets the fix agent push to this pull request"
