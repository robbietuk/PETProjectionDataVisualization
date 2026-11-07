#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Build dist/PETProjectionDataVisualization.app (with STIR inside) from scratch.
#
#   packaging/macos/build_app.sh            # reuse build/env if it exists
#   FRESH=1 packaging/macos/build_app.sh    # recreate build/env
#
# Needs only `uv` (https://docs.astral.sh/uv/) and the Xcode command line tools (codesign, otool).
# Everything else (python, STIR, Qt, PyInstaller) goes into a conda-forge prefix under build/,
# created with py-rattler; nothing is installed system-wide and no shell profile is touched.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BUILD="${BUILD_DIR:-$ROOT/build}"
ENV="$BUILD/env"
DIST="$ROOT/dist"
NAME=PETProjectionDataVisualization
APP="$DIST/$NAME.app"
SAMPLE="${STIR_TEST_PROJDATA:-}"

echo "== machine: $(uname -m), macOS $(sw_vers -productVersion)"

# 1. conda-forge prefix with STIR, PySide6, pyqtgraph, PyInstaller
if [[ "${FRESH:-0}" == 1 || ! -x "$ENV/bin/python" ]]; then
    rm -rf "$ENV"
    uv run --no-project --with 'py-rattler>=0.28' python "$HERE/make_env.py" "$ENV"
fi
PY="$ENV/bin/python"
"$PY" -c "import stir, PySide6, pyqtgraph, PyInstaller; print('== stir from', stir.__file__)"

# 2. freeze
rm -rf "$APP"
"$PY" -m PyInstaller --noconfirm --clean --log-level WARN \
    --distpath "$DIST" --workpath "$BUILD/pyinstaller" "$HERE/$NAME.spec"
rm -rf "${DIST:?}/$NAME"   # the intermediate onedir folder; the .app holds the same files

# 3. ad-hoc signature (required for arm64 binaries to run at all; not a Developer ID signature)
codesign --force --deep -s - "$APP"
codesign --verify --deep --strict "$APP"

# 4. self-test inside the bundle: demo data, plus a real STIR file when one is given
EXE="$APP/Contents/MacOS/$NAME"
QT_QPA_PLATFORM=offscreen PETPDV_SELF_TEST=1 "$EXE" --demo --out "$BUILD/selftest_demo.png"
if [[ -n "$SAMPLE" ]]; then
    QT_QPA_PLATFORM=offscreen PETPDV_SELF_TEST=1 "$EXE" "$SAMPLE" --out "$BUILD/selftest_stir.png"
fi

echo "== built $APP ($(du -sh "$APP" | cut -f1))"
