# Frozen app (macOS, Windows, Linux)

PyInstaller builds a standalone viewer with Python, Qt and **STIR included**. Interfile `.hs`
projection data opens without any STIR install.

| OS      | result in `dist/`                                         | archive (`--archive`)                         |
|---------|-----------------------------------------------------------|-----------------------------------------------|
| macOS   | `PETProjectionDataVisualization.app` (ad-hoc signed)      | `PETProjectionDataVisualization-macos-arm64.zip` |
| Windows | `PETProjectionDataVisualization/PETProjectionDataVisualization.exe` (one folder) | `...-windows-amd64.zip` |
| Linux   | `PETProjectionDataVisualization/PETProjectionDataVisualization` (one folder) | `...-linux-x86_64.tar.gz` |

## Layout

- `environment-app.yml`: the conda-forge build environment (python 3.12, `stir>=6.4`, PySide6,
  pyqtgraph, PyInstaller). Pin `stir>=6.4`; otherwise the solver may pick 6.3.
- `PETProjectionDataVisualization.spec`: the shared PyInstaller spec. It bundles the STIR SWIG
  module, the libraries it links, STIR's config tables (the folder that holds
  `radionuclide_info.json`) and `scripts/ci_smoke.py` for the self-test.
- `entry.py`: the frozen entry point. If `STIR_CONFIG_DIR` is unset, it points it at the bundled
  config tables, then calls `pet_projection_data_visualization.cli:main`.
- `build_app.py`: freezes the viewer, ad-hoc signs it on macOS, self-tests it, and with
  `--archive` packs it.
- `macos/`: `info_plist.py` (bundle id `io.github.robbietuk.petprojectiondatavisualization` and the
  `.hs`/`.npy`/`.npz` document types) and `build_app.sh` (local build without conda).
- `make_env.py`: creates the environment with py-rattler (used by `macos/build_app.sh`).

## Build

On any OS, in an environment made from `environment-app.yml`:

```bash
python packaging/build_app.py --archive --sample path/to/smalllong.hs
```

On a Mac with nothing installed but [uv](https://docs.astral.sh/uv/) and the Xcode command line tools:

```bash
packaging/macos/build_app.sh --sample path/to/smalllong.hs
```

That script creates `build/env` with py-rattler: no conda install and no shell-profile changes.
`FRESH=1` recreates the environment.

The self-test runs the frozen executable headless (`QT_QPA_PLATFORM=offscreen`) on the demo data,
and also on `--sample` (or `$STIR_TEST_PROJDATA`) when given. It fails unless `stir` is imported
from inside the bundle. To run it by hand:
`PETPDV_SELF_TEST=1 QT_QPA_PLATFORM=offscreen <executable> --demo --out shot.png`.

CI (`.github/workflows/app.yml`) does the same on `ubuntu-24.04`, `windows-latest` and
`macos-latest`, using `setup-micromamba`. It uploads the archives as artifacts.

## First launch

The builds are unsigned: no Developer ID and no notarisation.

- **macOS:** right-click (or Control-click) the app, choose **Open**, then **Open** again. On
  macOS 15 and later, try to open it once, then click **Open Anyway** in *System Settings >
  Privacy & Security*. Alternatively, run
  `xattr -dr com.apple.quarantine PETProjectionDataVisualization.app`.
- **Windows:** SmartScreen may warn. Choose *More info > Run anyway*.
- **Linux:** run `PETProjectionDataVisualization/PETProjectionDataVisualization`. The build uses the
  system's OpenGL and desktop libraries. On Debian/Ubuntu install:
  `sudo apt-get install libegl1 libgl1 libopengl0 libglx0 libxkbcommon0 libfontconfig1 libdbus-1-3`
  plus `libxcb-cursor0` for the X11 (`xcb`) platform plugin.

## Using it

- Launched with no arguments, it opens an empty window. Load data with **File > Open**.
- On macOS, you can drop `.hs`, `.npy` or `.npz` files on the Dock icon, or use Finder's
  **Open With**. `.hs` only has rank *Alternate*, because Haskell source uses the same extension.
- Command-line options work the same as `pet-projection-data-visualization`.

## Notes

- Without the bundle, conda-forge `stir` 6.4.0 needs `STIR_CONFIG_DIR` to read `.hs` files.
  - On macOS and Linux, the relocated compiled-in path is padded with NUL bytes.
  - On Windows, it names `STIR-6.3`.
  - Either way, the error is *find_STIR_config_file error opening file ...*.
  - Fix: set `STIR_CONFIG_DIR` to the folder that holds `radionuclide_info.json`.
- The bundle ignores `STIR_PYTHON_PATH`, so it always uses its own STIR. `--stir-path` still
  overrides on purpose.
- The macOS app is about 200 MB (76 MB zipped), mostly Qt, ICU, OpenBLAS and STIR/ROOT.
