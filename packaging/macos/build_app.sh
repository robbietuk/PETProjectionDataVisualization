#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Local build of dist/PETProjectionDataVisualization.app (with STIR inside) from scratch, without conda.
#
#   packaging/macos/build_app.sh [build_app.py options, e.g. --archive --sample file.hs]
#   FRESH=1 packaging/macos/build_app.sh     # recreate build/env
#
# Needs only `uv` (https://docs.astral.sh/uv/) and the Xcode command line tools (codesign, ditto).
# Python, STIR, Qt and PyInstaller go into a conda-forge prefix under build/, made with py-rattler
# from packaging/environment-app.yml. Nothing is installed system-wide and no shell profile is touched.
# (CI uses setup-micromamba with the same environment file instead: .github/workflows/app.yml.)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
ENV="${BUILD_DIR:-$ROOT/build}/env"

if [[ "${FRESH:-0}" == 1 || ! -x "$ENV/bin/python" ]]; then
    rm -rf "$ENV"
    uv run --no-project --with 'py-rattler>=0.28' python "$ROOT/packaging/make_env.py" "$ENV"
fi
exec "$ENV/bin/python" "$ROOT/packaging/build_app.py" "$@"
