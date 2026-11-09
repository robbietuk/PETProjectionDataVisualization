# PETProjectionDataVisualization

[![tests](https://github.com/robbietuk/PETProjectionDataVisualization/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/robbietuk/PETProjectionDataVisualization/actions/workflows/test.yml?query=branch%3Amain)
[![pre-commit](https://github.com/robbietuk/PETProjectionDataVisualization/actions/workflows/pre-commit.yml/badge.svg?branch=main)](https://github.com/robbietuk/PETProjectionDataVisualization/actions/workflows/pre-commit.yml?query=branch%3Amain)
[![real STIR](https://github.com/robbietuk/PETProjectionDataVisualization/actions/workflows/stir.yml/badge.svg?branch=main)](https://github.com/robbietuk/PETProjectionDataVisualization/actions/workflows/stir.yml?query=branch%3Amain)
[![build](https://github.com/robbietuk/PETProjectionDataVisualization/actions/workflows/build.yml/badge.svg?branch=main)](https://github.com/robbietuk/PETProjectionDataVisualization/actions/workflows/build.yml?query=branch%3Amain)
[![app](https://github.com/robbietuk/PETProjectionDataVisualization/actions/workflows/app.yml/badge.svg?branch=main)](https://github.com/robbietuk/PETProjectionDataVisualization/actions/workflows/app.yml?query=branch%3Amain)

<!-- The PyPI and conda-forge badges show "not found" until the first release is published. -->
[![PyPI version](https://img.shields.io/pypi/v/PETProjectionDataVisualization)](https://pypi.org/project/PETProjectionDataVisualization/)
[![Python versions](https://img.shields.io/pypi/pyversions/PETProjectionDataVisualization)](https://pypi.org/project/PETProjectionDataVisualization/)
[![conda-forge version](https://img.shields.io/conda/vn/conda-forge/petprojectiondatavisualization)](https://anaconda.org/conda-forge/petprojectiondatavisualization)
[![conda-forge platforms](https://img.shields.io/conda/pn/conda-forge/petprojectiondatavisualization)](https://anaconda.org/conda-forge/petprojectiondatavisualization)
[![last commit](https://img.shields.io/github/last-commit/robbietuk/PETProjectionDataVisualization/main)](https://github.com/robbietuk/PETProjectionDataVisualization/commits/main)
[![commits since latest release](https://img.shields.io/github/commits-since/robbietuk/PETProjectionDataVisualization/latest/main)](https://github.com/robbietuk/PETProjectionDataVisualization/commits/main)
[![license](https://img.shields.io/github/license/robbietuk/PETProjectionDataVisualization)](https://github.com/robbietuk/PETProjectionDataVisualization/blob/main/LICENSE)

Interactive viewer for STIR projection data: sinograms, viewgrams and tangential slices, with
a time-of-flight (TOF) dimension you can step through, play back, or collapse.
PySide6 + pyqtgraph (no matplotlib), Python >= 3.11. A development tool: run it as a script,
no compiled executable.

This started as a rewrite of STIR's `examples/python/projdata_visualisation` (PyQt5 + matplotlib), which is
still part of STIR and unchanged. See [docs/PLAN.md](https://github.com/robbietuk/PETProjectionDataVisualization/blob/main/docs/PLAN.md) for design decisions and the roadmap.

## Getting set up

New to Python or conda? The [step-by-step guide](https://github.com/robbietuk/PETProjectionDataVisualization/blob/main/docs/INSTALL.md)
covers Windows, macOS and Linux: installing Python 3.11 or newer, Miniforge and the viewer, checking it works,
and common problems (such as macOS's built-in `/usr/bin/python3`, which is 3.9 and too old). In short:

* **Desktop app, no Python needed:** download the app for your system from
  [GitHub Releases](https://github.com/robbietuk/PETProjectionDataVisualization/releases). STIR is included.
* **conda (recommended, includes STIR):** install [Miniforge](https://github.com/conda-forge/miniforge), then
  `conda create -n petpdv -c conda-forge petprojectiondatavisualization` and `conda activate petpdv`.
* **pip (no STIR):** in a virtual environment with Python 3.11 or newer,
  `pip install PETProjectionDataVisualization`. Numpy files and the demo work; `.hs` files need STIR from
  elsewhere.

Then run `pet-projection-data-visualization --demo`. Until the PyPI and conda-forge packages are published,
the guide shows how to install from GitHub instead. Developer set-up (editable install, pre-commit, tests) is in
[CONTRIBUTING.md](https://github.com/robbietuk/PETProjectionDataVisualization/blob/main/CONTRIBUTING.md).

## Versions and changes

Releases follow [semantic versioning](https://semver.org/); the version comes only from the git tag
(`vX.Y.Z`). `pet-projection-data-visualization --version` prints it. See [CHANGELOG.md](CHANGELOG.md) for what changed
and [CONTRIBUTING.md](CONTRIBUTING.md) for pull requests and releasing.

## Install

STIR's Python module is a compiled extension and is **not** a pip dependency; the viewer finds it
at run time. To install from a clone of this repository (macOS/Linux shell; for Windows and for installing
Python or conda first, see [Getting set up](#getting-set-up)), pick one:

```sh
# A) conda (recommended): STIR, Qt and the viewer in one environment
conda env create -f environment.yml && conda activate stir-viewer
pip install -e .                      # run from this directory

# B) existing STIR source build + a venv. The venv must use the SAME Python minor version (and a numpy
#    ABI compatible with) the one STIR was built against, or `import stir` will fail.
python -m venv .venv && . .venv/bin/activate
pip install -e .                      # numpy, PySide6, pyqtgraph
export LD_LIBRARY_PATH=<STIR install>/lib:$LD_LIBRARY_PATH   # DYLD_LIBRARY_PATH on macOS; on Windows --stir-path also registers <prefix>/bin and <prefix>/lib
pet-projection-data-visualization file.hs --stir-path <STIR install>/python

# C) no STIR at all: numpy files and the synthetic demo still work
pip install -e . && pet-projection-data-visualization --demo
```

## Loading data

The viewer accepts three kinds of input:

| Input | Needs `stir`? | Notes |
|---|---|---|
| STIR projection data: an Interfile header (`.hs`) or any other file `stir.ProjData.read_from_file` can open | yes | Read lazily, one segment (and TOF bin) at a time. |
| A numpy file (`.npy` / `.npz`) | no | See [numpy layout](#numpy-layout) below. |
| The built-in demo (`--demo`) | no | A synthetic TOF phantom, handy to check the install. |

### 1. From the command line

Run these from an environment where the viewer is installed (see [Install](#install)):

```sh
pet-projection-data-visualization my_sinogram.hs                    # STIR projection data
pet-projection-data-visualization -f my_sinogram.hs                 # same, old-tool spelling
python -m pet_projection_data_visualization my_sinogram.hs          # same, without the console script
pet-projection-data-visualization data.npz                          # numpy arrays
pet-projection-data-visualization --demo                            # synthetic TOF demo
pet-projection-data-visualization                                   # empty window: load from the GUI
pet-projection-data-visualization my_sinogram.hs --theme light      # light colour scheme
```

If `stir` is a source build that is not on the Python path, tell the viewer where it is installed:

```sh
pet-projection-data-visualization my_sinogram.hs --stir-path <STIR install prefix>/python
# or, once per shell:
export STIR_PYTHON_PATH=<STIR install prefix>/python
export DYLD_LIBRARY_PATH=<STIR install prefix>/lib:$DYLD_LIBRARY_PATH   # macOS (LD_LIBRARY_PATH on Linux)
```

The `.hs` header must sit next to its data file (`.s`) as STIR expects; relative paths in the header are
resolved by STIR, not by the viewer.

### 2. From the window

* Type or paste a path in the *Data* box and press **Load** (or Enter), or
* press **Browse...** (File > Open) and choose a `.hs`, `.npy` or `.npz` file, or
* use File > **Demo data** for the synthetic phantom.

If loading fails, the reason is shown in a banner at the top of the window and the previously loaded data
stays on screen. The most common message, *Could not import the 'stir' module*, means the viewer cannot see
STIR's Python bindings: use the conda environment, or `--stir-path` / `STIR_PYTHON_PATH` as above.

### 3. From Python

`launch` blocks until the window is closed. It takes a filename, a `stir.ProjData` object you already have
(for example one you just forward projected into), or nothing:

```python
from pet_projection_data_visualization.app import launch    # `launch_GUI` is kept as an alias of the old name

launch("my_sinogram.hs")                         # a filename (.hs, .npy, .npz)

import stir
proj_data = stir.ProjData.read_from_file("my_sinogram.hs")
launch(proj_data)                                # an in-memory stir.ProjData

launch(demo=True)                                # the synthetic demo
launch("my_sinogram.hs", stir_path="/opt/stir/python", theme="light")
```

### numpy layout

Two `.npz` layouts are accepted, plus `.npy`:

* **STIR's own export.** `ProjData.as_array()` returns one array `(tof, sinograms, views, tangential)` in which the
  sinograms of all segments follow each other in STIR's order 0, 1, -1, 2, -2, ... Since that array alone does
  not say where one segment ends, save the number of axial positions per segment with it:

  ```python
  import numpy as np, stir
  pd = stir.ProjData.read_from_file("my_sinogram.hs")
  n = pd.get_num_segments()
  order = [0] + [s for k in range(1, n) for s in (k, -k)][: n - 1]     # 0, 1, -1, 2, -2, ...
  np.savez("my_sinogram.npz", as_array=pd.as_array(),
           axial_counts=[pd.get_num_axial_poss(s) for s in order])
  ```

  For a segment range that is not symmetric (e.g. -1..2) also save `segment_numbers=` with STIR's order
  (for -1..2: `[0, 1, -1, 2]`). A bare `np.save(..., pd.as_array())` `.npy` cannot be split into segments and
  is **not** in the layout below, so it would be shown wrongly: use the `.npz` form above.

* **One array per segment**, named `segment_<n>` (`n` may be negative, e.g. `segment_-1`). Each array is
  `(views, axial, tangential)` for non-TOF data or `(tof, views, axial, tangential)` for TOF data. Segment
  numbers must be contiguous (e.g. -1, 0, 1). All segments must have the same number of views, tangential
  positions and TOF bins; the axial size may differ.
* `.npy`: a single array with the same shape rules, shown as segment 0.

```python
import numpy as np
np.savez("data.npz", segment_0=seg0, **{"segment_-1": seg_m1, "segment_1": seg_p1})
```

## Using the window

The image takes most of the window. Hovering an icon of the rail on the left (or tabbing to it) shows a
short summary; clicking it (or Enter/Space) opens its flyout, which stays open until you click it again,
click elsewhere or press Esc: *Data* (path box, Browse, Load, demo data, the files opened recently,
and whether STIR was found), *Info* (the data set's metadata), *Display* (colour map, log display and
theme) and *Settings* (show or hide the TOF profile and the line profile, animation speed, loop or
bounce at the end of an axis, the keyboard shortcuts). The slice toolbar under the image has the image
type tabs (Sinogram | Viewgram | Tangential) on the left and, on the right, one row for each axis the
image does not show: the segment, the fixed axis (axial position for a sinogram, view for a viewgram,
tangential position for a tangential slice) and, for TOF data, the TOF bin. Each row has ‹ › step
buttons, a value box, a slider and its own play button; only one axis plays at a time, so pressing
another row's play switches to it. The TOF row also chooses a single bin or Sum / Mean / Max over all
bins; while TOF is collapsed its play button is disabled, and its tooltip says why.

Beside the colour bar are the colour levels: Max at the top, Min at the bottom, *Adaptive | Locked* and
*Global range* (see below). Hovering shows a readout in a corner of the image (segment, view, axial and
tangential position, TOF bin and value); when the cursor comes close to it, it moves to another corner.
The plot column on the right (drag its edge to resize it, or the edge between the plots) shows:

* the **TOF profile** of the LOR under the cursor (TOF data only), with the current bin marked. While
  TOF is collapsed (Sum, Mean or Max) it is still shown, as context: "TOF bins at this LOR (the image
  shows their Sum: …)", with the collapsed value as a dashed reference line;
* the **line profile**, *Row | Column | Free*. Row and Column read the exact bins of the image row or
  column through the cursor (their tooltips say which axis, e.g. "Along tangential"; Row, along
  tangential, is the default). Free reads along a line drawn on the image: drag the line or its end
  handles; the samples are interpolated and plotted against the distance in bins. The profile shows
  the image as displayed (one TOF bin, or Sum/Mean/Max); *per TOF bin* adds one faint curve per TOF bin
  along the same line.

A click on the image freezes both profiles at that LOR (marked with a cross) while you change slices or
image type; another click, or Esc, releases them. The viewer remembers the window and panel sizes, the
theme, the recent files and the display, profile and animation settings for the next session.

Keys: Space plays or pauses the axis played last (TOF at first for TOF data, otherwise the fixed axis;
the toolbar says which), Left/Right step the fixed axis, PgUp/PgDn change segment, L lock/unlock the colour
levels, F freezes or releases the profiles (at the cursor, or the centre of the image), Esc closes the
open flyout or else releases frozen profiles (*Settings* lists these keys). When a slider, spin box or
text field has the keyboard focus, these keys go to it instead (e.g. Right on the segment slider moves
the segment, L typed in the path box is just a letter). Min/Max level accept any number, including
scientific notation such as `2.5e-8`.

Colour levels (beside the colour bar, *Adaptive | Locked*):

| | **Adaptive** (default) | **Locked** |
|---|---|---|
| Min/Max and the colour bar | recomputed from every slice shown | stay exactly the same |
| Step view / axial / tangential / segment / TOF bin, play | follow the new slice | unchanged |
| Sinogram / viewgram / tangential, Bin / Sum / Mean / Max | follow the new slice | unchanged |
| Type Min or Max, drag the histogram | locks at the new values | stays locked at the new values |
| *Global range* | locks at the range of the whole data set (current TOF mode) | same, replaces the lock |
| log(1 + x) display | recomputed in the new scale | the same data values, mapped through log(1 + x) |
| Load another data set | adaptive | back to adaptive (old limits may mean nothing there) |
| A read or load fails | unchanged | stays locked at the same values |

Locking freezes what is on screen, including the colour bar's axis (locking by dragging the histogram does not
rescale it under the mouse; typed levels and *Global range* fit the axis to the new limits). While locked
the header shows a chip such as *Levels locked 0 – 3.86*.

## Architecture (MVVM)

```
stir module ─▶ stir_interface ─▶ model ◀─ viewmodel ◀─ view (PySide6 + pyqtgraph)
               gateway+adapter   pure     no Qt         thin binding
               (only layer       domain   observable
               that sees stir)   logic    props+commands
```

| Package | Knows about | Role |
|---|---|---|
| `model/` | numpy only | `ProjDataInfo`, immutable `Selection`, `ProjDataset` (slices, TOF reduction, caches, stats), line profiles through a slice (`profiles.py`) |
| `sources/` | model | numpy `.npy/.npz` source, synthetic TOF demo, `make_source` |
| `stir_interface/` | model, `stir` | `StirGateway`/`StirProjDataHandle` protocols, `SwigStirGateway` (the only file importing `stir`), `StirProjDataSource` adapter |
| `viewmodel/` | model | `ViewerViewModel` (files, title, status, errors) owning a `ProjectionPaneViewModel` (`vm.pane`: everything about the data set on screen): observable properties + command methods, formatting, playback steps (`playback.py`), what the profile plots read (`profiles.py`), the readout's corner (`readout.py`), the settings remembered between sessions; shared `ChoiceOptions` and `BindingRegistry`; no Qt |
| `view/` | viewmodel, Qt | `ViewerWindow` arranges the icon rail (`rail.py`), the self-contained `ProjectionDataPane` (`pane.py`: image, colour bar, readout, profile plots) and the slice toolbar, built from reusable `components`; `theme` (colour scheme) is Qt-free; knows nothing about sources or STIR |
| `app.py` | everything | composition root: wires loader, demo data, the STIR probe, view model, window and the `QSettings` file |

`tests/test_architecture.py` enforces these import rules, and checks in a clean interpreter that the
Qt-free layers never load PySide6, pyqtgraph, matplotlib or `stir`.

## Look and feel

The UI uses one colour scheme (`view/theme.py`): a dark default and a light variant, chosen with
`--theme dark|light`, View > Light theme or the *Display* flyout (the viewer starts with the theme used last). Every colour comes from a `Palette` (text/background pairs are
tested for WCAG AA contrast, and a test fails if a widget file hard-codes a colour); `build_stylesheet`
turns the palette into the application stylesheet and the plots read the same palette.

Shared component logic lives in two places: Qt-free `viewmodel/options.py` (`ChoiceOptions`: one definition of
the labels/order of slice modes, TOF modes, level modes and colour maps) and `viewmodel/bindings.py`
(`BindingRegistry`: declarative property -> widget bindings, each run once per command), and Qt
`view/components.py` (`SegmentedControl` and `ChoiceCombo` share one `ChoiceControl` contract; `Card`,
`LabeledRow`, `ChipRow`, `MetricGrid`, `Banner`, `EmptyState`, `AxisRowControl`). Errors appear in an inline,
dismissable banner instead of a modal dialog, and an empty state is shown until data is loaded.

## Tests

```sh
pip install -e .[test] && pytest
```

| Directory | What it covers | Needs |
|---|---|---|
| `tests/model` | selection clamping, slicing, TOF reductions, caches, stats, geometry | numpy |
| `tests/sources` | array/demo sources, file loading, loader dispatch | numpy |
| `tests/stir_interface` | SWIG gateway against a fake `stir`, adapter, one contract run on every handle implementation | numpy |
| `tests/viewmodel` | every command, notification batching, levels, hover/profile, failure paths, seeded random-command invariants | numpy |
| `tests/view` | window binding with stubbed Qt (always runs) and with real PySide6 offscreen (if installed) | Qt optional |
| `tests/tooling` | the project itself: release checks and tag rules, changelog format, licence and SPDX headers, the CI helper scripts (`scripts/`) | numpy (Qt for the smoke test) |
| `tests/stir_interface/test_real_stir_integration.py` | real bindings: contract, axis order vs STIR's own accessors, full stack on a real file | `stir` + a `.hs` (`STIR_TEST_PROJDATA`) |

## Differences from the old PyQt5/matplotlib tool

Kept: sinogram and viewgram modes (same axes and orientation), segment/axial/view/TOF controls, file
browse + typed path + Load, `launch(...)` with a path, a `stir.ProjData` or no argument (`launch_GUI` alias),
`-f FILE` on the command line, max-level control (now numeric Min/Max level boxes plus a draggable histogram).

Changed on purpose: no matplotlib toolbar; the slice is always shown as a fixed image with axis ticks (no zoom/pan), File > Save image;
vmin is no longer fixed at 0 (adaptive per slice, or locked, e.g. at the global range); the initial slice is the central one;
the data summary is shown in the Information panel instead of the console.

Dropped: the Qt style/palette selector; zoom/pan (the slice is always shown whole, as a fixed image).

Installation: this is a separate package (`pip install PETProjectionDataVisualization`, or from conda-forge once
the recipe is accepted). The old tool is still part of STIR as `stir.projdata_visualisation` and is unchanged.

## Known limitations

* Everything runs on the UI thread. Collapsing TOF bins reads every bin of one segment, and *Global range*
  reads the whole data set once (every segment and, for single bins, every TOF bin); on large TOF data this
  takes a while (a wait cursor is shown). Not measured on real data yet.
* Memory: segments are cached up to about 1 GiB (plus up to 1 GiB of Sum/Mean/Max results); beyond that the least
  recently used ones are dropped and read again when needed. Hovering reads single sinograms (one per TOF bin),
  not whole segments.
* Tested in CI with PySide6 >= 6.6 and pyqtgraph >= 0.13.7 on Linux, macOS and Windows (Python 3.11 to 3.14), and against real STIR from conda-forge.
* PySide6 6.12.0 on Linux gives back references to `None`, `True` and `False` that it never took (about 64 per
  repaint of the colour bar, measured on Python 3.11; 6.8.3 to 6.11.3, and 6.12.0 on macOS and Windows, are fine).
  From Python 3.12 those objects are immortal and nothing happens, but on Python 3.11 the viewer aborted after a few
  seconds of playback ("deallocating None" / "deallocating True or False", exit status 134). Two defences:
  `pyproject.toml` does not let pip install PySide6 6.12 with Python < 3.12 (pip picks 6.11.x), and on CPython
  < 3.12 the viewer raises the reference count of those three objects by 2**40 at start-up
  (`_refcount_guard.py`, the same guard the test suite uses), which covers conda environments and any later PySide6
  with the same bug. Python 3.12 or newer avoids the question entirely; the packaged app uses 3.12.
