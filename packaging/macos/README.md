# macOS app bundle

Builds `dist/PETProjectionDataVisualization.app`: a double-clickable viewer with Python, Qt and
**STIR included**, so Interfile `.hs` projection data opens without any STIR install.

## Build

Needs only [uv](https://docs.astral.sh/uv/) and the Xcode command line tools.

```bash
packaging/macos/build_app.sh
```

1. `make_env.py` creates a conda-forge prefix in `build/env` (python 3.12, `stir>=6.4`, PySide6,
   pyqtgraph, PyInstaller) with [py-rattler](https://pypi.org/project/py-rattler/), run through
   `uv`. No conda/mamba install and no shell-profile changes. `FRESH=1` recreates it.
2. PyInstaller freezes `entry.py` with `PETProjectionDataVisualization.spec` (windowed, bundle id
   `io.github.robbietuk.petprojectiondatavisualization`). The spec bundles the STIR SWIG module, the
   libraries it links (ROOT core, OpenMP, parallelproj), STIR's `share/STIR-*/config` tables, and
   the Qt cocoa/imageformats plugins.
3. The bundle is ad-hoc signed (`codesign --force --deep -s -`). Apple Silicon needs this to run it.
4. A self-test runs `scripts/ci_smoke.py` inside the bundle on the demo data. To also test a real
   STIR file, set `STIR_TEST_PROJDATA=/path/to/file.hs`.

The bundle is about 200 MB, mostly Qt, ICU, OpenBLAS and the STIR/ROOT libraries.

## First launch (unsigned app)

The app has no Developer ID signature and is not notarised. Gatekeeper blocks it the first time
you open a downloaded copy. Either:

- right-click (or Control-click) the app in Finder, choose **Open**, then **Open** in the dialog
  (on macOS 15 and later: try to open it once, then go to *System Settings > Privacy & Security*
  and click **Open Anyway**), or
- remove the quarantine flag: `xattr -dr com.apple.quarantine PETProjectionDataVisualization.app`

A copy you built yourself is not quarantined and opens directly.

## Using it

- Double-click to open an empty window. **File > Open** (or the Browse/Open buttons) loads data.
- Drop `.hs`, `.npy` or `.npz` files on the Dock icon, or use Finder's **Open With**. `.npy`/`.npz`
  are declared with rank *Default*. `.hs` only has rank *Alternate*, because the extension is also
  used for Haskell source, so use **Open With** (or *Get Info > Open with > Change All*) for it.
- The command line still works:
  `PETProjectionDataVisualization.app/Contents/MacOS/PETProjectionDataVisualization file.hs --theme light`

## Notes

- The bundle always uses its own STIR. It sets `STIR_CONFIG_DIR` to its copy of the config tables
  and ignores `STIR_PYTHON_PATH`. `--stir-path` still overrides on purpose.
- conda-forge `stir` 6.4.0 needs `STIR_CONFIG_DIR` even outside the bundle. When conda relocates
  the prefix, the compiled-in config path ends up padded with NUL bytes, so reading a `.hs` fails
  with *find_STIR_config_file error opening file ... (non-existent or empty file)*. Fix it with
  `export STIR_CONFIG_DIR=$CONDA_PREFIX/share/STIR-6.4/config`.
- Self-test of a built app:
  `QT_QPA_PLATFORM=offscreen PETPDV_SELF_TEST=1 <app>/Contents/MacOS/PETProjectionDataVisualization --demo --out shot.png`
  prints where `stir` was imported from.
