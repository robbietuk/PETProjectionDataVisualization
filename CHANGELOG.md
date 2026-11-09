# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The version number lives only in git tags (`vMAJOR.MINOR.PATCH`). Every pull request adds its
changes under **Unreleased**. Releasing renames that section to the new version, and the tag
publishes it (see [CONTRIBUTING.md](CONTRIBUTING.md#releasing)). The first release will be 1.0.0: everything
under Unreleased below is the work since the viewer was split out of STIR's `examples/python/projdata_viewer`.

## [Unreleased]

### Added

- **Viewer.** A PySide6 + pyqtgraph viewer for STIR projection data with three slice modes:
  sinogram, viewgram and tangential. The image is fixed, with no zoom or pan, and shows bin-number
  axes on the left and bottom.
- **Time of flight.** Show a single TOF bin, play the bins back, or reduce them with Sum, Mean or
  Max. Hovering shows the value and the bin indices, plus the counts-versus-TOF-bin profile of the
  line of response under the cursor.
- **Inputs.** STIR projection data (`.hs` and anything `stir.ProjData.read_from_file` opens), read
  lazily one segment and one TOF bin at a time. Also numpy `.npy`/`.npz` files, including STIR's
  own `ProjData.as_array()` export saved with `axial_counts`, and a synthetic TOF demo (`--demo`).
- **Levels.** Adaptive (per slice) or locked; a lock can be set at the global range over all
  segments and TOF bins. The Min/Max boxes accept any magnitude, including values like `2.5e-8`. There is a draggable
  histogram and a log display switch.
- **Interface.** A dark theme and a light theme whose text/background pairs are checked against
  WCAG AA contrast. Errors appear in an inline banner, there is an empty state, File > Save image,
  and a typed or pasted path box that strips quotes and expands `~`.
- **Lockable colour levels.** An *Adaptive | Locked* toggle in the Display card (key `L`). Locked
  keeps Min/Max and the colour bar exactly constant while changing view, axial or tangential
  position, segment, TOF bin, TOF reduction, slice mode or log display, and during playback.
  Typing a level or dragging the histogram keeps the lock at the new values, *Lock to global range*
  locks at the whole data set's range, and a "Levels locked lo – hi" chip shows the state. Locking from
  the screen (toggle, `L`, a drag in the histogram) keeps the colour bar's axis where it is; typed levels
  and the global range fit it to the new limits. Loading another data set starts adaptive again; a failed
  read or load keeps the lock.
- **Keyboard.** Space plays or pauses, Left/Right step the active index and PgUp/PgDn change the
  segment. When a slider, spin box or text field has focus, the key goes to that widget instead.
- **Finding STIR.** `--stir-path`, then `STIR_PYTHON_PATH`, then a plain `import stir`. A bad
  environment variable gives a warning and falls back to `import stir`.
- **Command line.** The `pet-projection-data-visualization` command and
  `python -m pet_projection_data_visualization`, with `--version`, `--demo`, `--theme`,
  `--stir-path` and the old tool's `-f FILE`.
- **Python API.** `launch(path | stir.ProjData | source)`, with `launch_GUI` kept as an alias.
- **Versioning.** The version comes from the git tag through hatch-vcs: `v1.2.3` builds as `1.2.3`,
  and commits after a tag build as `1.2.4.devN+g<hash>`.
- **Continuous integration** on GitHub Actions, modelled on STIR's own CI and run only on standard
  free runners:
  - pre-commit, with STIR's generic hooks plus ruff and a strict Pyrefly type check
  - pytest with offscreen Qt on Ubuntu, macOS and Windows, Python 3.11 to 3.14
  - a real-STIR job with conda-forge `stir` 6.4.0 and STIR's own test data
  - building the wheel and sdist and installing each into a clean environment on all three
    operating systems
  - publishing to TestPyPI and then PyPI with trusted publishing, plus a GitHub Release whose notes
    come from this file, when a version tag is pushed
- **Tests.** About 500 tests across the model, sources, STIR interface, view model and view, using
  stubbed and real Qt. They include architecture rules that keep the model and view model free of
  Qt and STIR, and checks that every source file carries the SPDX licence line.
- **Static typing.** The package, the CI scripts and the app build scripts are fully annotated and pass a strict
  [Pyrefly](https://pyrefly.org) type check (`preset = "strict"` plus no explicit or inferred `Any`, apart from
  one alias for the untyped SWIG `stir` module), run as a pre-commit hook. The package ships a `py.typed`
  marker, so its types are visible to users' type checkers.
- **Python 3.14.** Support for Python 3.14.
- **Licence.** `LICENSE` (Apache-2.0) and `NOTICE`, shipped in the sdist and the wheel.
- **Icon rail peeks and flyout content (#36, phase 2).** Hovering or focusing a rail icon shows a
  short summary beside it: the file path and format, the scanner, dimensions and TOF yes/no, the
  display settings, or the profile and animation settings. A flyout opened with a click stays open
  until you click elsewhere in the window or press Esc. Enter or Space on a focused icon opens it
  and moves the focus into it, and Esc gives the focus back. The *Data* flyout lists the files
  opened this session and shows whether STIR was found and where. *Display* has a Dark | Light
  theme switch, in step with *View > Light theme*. *Settings* can hide the TOF profile plot and
  lists the keyboard shortcuts.
- **Slice toolbar with per-axis play (#36, phase 3).** The toolbar under the image has image type
  tabs (Sinogram | Viewgram | Tangential) and one compact row for each axis the image does not show:
  the segment, the fixed axis of the image type and, for TOF data, the TOF bin, each with ‹ › step
  buttons, a value box, a slider and its own play button. Any of these axes can be animated, not only
  TOF; one plays at a time, and pressing another row's play switches to it. Space plays or pauses the
  axis played last, and the toolbar says which. The TOF row holds Bin | Sum | Mean | Max; its play
  button is disabled while TOF is collapsed, with a tooltip saying why. *Settings* chooses whether
  playback loops round or bounces back at the end of an axis.

### Fixed

These came out of two independent code reviews, before the split from STIR:

- A failed load or slice read leaves the previous data, selection and widgets exactly as they were.
- The TOF profile under a resting cursor updates whenever the slice changes.
- The global level range covers every TOF bin, so levels locked to it do not change during playback.
- The `(segment, tof)` overload of `get_segment_by_view` is used, which every `ProjData` subclass
  has.
- Hovering reads single sinograms instead of whole segments, and the segment cache is capped at
  about 1 GiB.
- Two tests assumed POSIX paths and failed on Windows.
- A PySide6 crash during interpreter shutdown no longer fails the Linux/Python 3.11 test run.
- Python 3.11 with PySide6 6.12.0 on Linux aborted after a few seconds of playback ("deallocating None",
  exit status 134): that PySide6 release gives back references to `None`, `True` and `False` it never took.
  pip no longer installs PySide6 6.12 with Python < 3.12, and on CPython < 3.12 the viewer (and the test suite)
  make those three objects effectively immortal at start-up, as Python 3.12 does.
- conda-forge `stir` on Windows looked for its config files in the wrong folder; CI sets
  `STIR_CONFIG_DIR` to the installed tables.
- The TOF profile plot keeps its x-axis fixed on every TOF bin of the data set (negative bins
  included). The mouse wheel and dragging zoom and pan only the counts axis, which cannot be panned
  below 0 when all counts are ≥ 0. A double-click or the "A" button fits the counts again. The
  plot's right-click menu is gone.

### Changed

- **New layout (#36, phase 1).** The left column of cards is replaced by a narrow icon rail
  (Data, Info, Display, Settings); clicking an icon opens its controls in a flyout beside it and
  clicking again closes it. The image gets most of the window, the TOF profile moves to a resizable
  column on its right (hidden for non-TOF data), and the slice controls (sinogram / viewgram /
  tangential, the indices, time of flight and Play) move to a toolbar under the image. The cursor
  value is shown under the image instead of in the status bar. The Data flyout also has a
  *Load demo data* button.
- **Breaking:** for code that drives the view model: everything about the data set on screen
  (selection, levels, display, hover, TOF profile, playback) moved from `ViewerViewModel` to its
  projection data pane, `ViewerViewModel.pane` (a `ProjectionPaneViewModel`); for example
  `vm.set_slice_mode(...)` is now `vm.pane.set_slice_mode(...)`. File loading, the window title,
  the status line and errors stay on `ViewerViewModel`.
- **Breaking:** for code that drives the view model: the pane's `dimensions` (one `DimensionState`
  per index) became `axis_rows`, one `AxisRow` per toolbar row, so it no longer lists the axes the
  image shows (#36, phase 3). `set_playing(True)` and `toggle_play()` play the axis played last, which
  may be any toolbar axis (`play_axis`), and `can_play` is now also true for non-TOF data. New
  commands: `toggle_play_axis(dim)` and `set_play_mode(PlayMode.LOOP | PlayMode.BOUNCE)`.
- Refreshed visual design: new light and dark palettes with one accent colour, flat cards with
  subtle borders, a clear type scale and more generous spacing; the plots share the card colour.
  Header chips are no longer clipped (a long data set title is shortened with "…" instead), and the
  left panel narrows with the window down to the width its controls need instead of being fixed
  (with large fonts it widens instead of cutting controls off). The statistics tiles wrap into two
  rows in a narrow window, and the window never gets so narrow that the plot or its colour bar is cut off.
- The three level modes *Auto*, *Fixed (global range)* and *Manual* became two, *Adaptive* and
  *Locked* (`LevelMode.ADAPTIVE` / `LevelMode.LOCKED`). The global range is now the
  *Lock to global range* action, and editing a level locks it. Toggling the log display no longer
  drops edited levels: locked levels stay locked and are mapped through the same `log(1 + x)`.
- The project was renamed from `stir-projdata-viewer`. The PyPI name is
  `PETProjectionDataVisualization`, the import package is `pet_projection_data_visualization` and
  the command is `pet-projection-data-visualization`.

[Unreleased]: https://github.com/robbietuk/PETProjectionDataVisualization/commits/main
