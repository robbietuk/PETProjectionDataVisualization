#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Keeps one open tracking issue for a scheduled CI job (used by docs/workflows/stir-master.yml).
#
#   ci_tracking_issue.sh fail <label> <title> <body-file>   comment on the open issue with <label>, or open one
#   ci_tracking_issue.sh pass <label> <title> <body-file>   close the open issue with <label>, if there is one
#
# Needs `gh` with GH_TOKEN (issues: write) and GH_REPO set. Never opens a second issue while one is open.
set -euo pipefail

if [ "$#" -ne 4 ]; then
  echo "usage: $0 fail|pass <label> <title> <body-file>" >&2
  exit 2
fi
mode=$1 label=$2 title=$3 body_file=$4

open=$(gh issue list --label "$label" --state open --limit 1 --json number --jq '.[0].number // empty')

case "$mode" in
  fail)
    if [ -n "$open" ]; then
      gh issue comment "$open" --body-file "$body_file"
      echo "commented on the tracking issue #$open"
    else
      # the label has to exist before an issue can carry it; it is already there after the first failure
      gh label create "$label" --color B60205 --description "Scheduled CI against STIR master failed" \
        >/dev/null 2>&1 || true
      gh issue create --title "$title" --label "$label" --body-file "$body_file"
    fi
    ;;
  pass)
    if [ -n "$open" ]; then
      gh issue close "$open" --comment "$(cat "$body_file")"
      echo "closed the tracking issue #$open"
    else
      echo "no open tracking issue"
    fi
    ;;
  *)
    echo "unknown mode '$mode' (fail or pass)" >&2
    exit 2
    ;;
esac
