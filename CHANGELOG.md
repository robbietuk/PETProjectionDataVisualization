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
- **Levels.** Automatic per slice, a fixed global range over all segments and TOF bins, or manual.
  The Min/Max boxes accept any magnitude, including values like `2.5e-8`. There is a draggable
  histogram and a log display switch.
- **Interface.** A dark theme and a light theme whose text/background pairs are checked against
  WCAG AA contrast. Errors appear in an inline banner, there is an empty state, File > Save image,
  and a typed or pasted path box that strips quotes and expands `~`.
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
  - pre-commit, with STIR's generic hooks plus ruff
  - pytest with offscreen Qt on Ubuntu, macOS and Windows, Python 3.11 to 3.13
  - a real-STIR job with conda-forge `stir` 6.4.0 and STIR's own test data
  - building the wheel and sdist and installing each into a clean environment on all three
    operating systems
  - publishing to TestPyPI and then PyPI with trusted publishing, plus a GitHub Release whose notes
    come from this file, when a version tag is pushed
- **Tests.** About 400 tests across the model, sources, STIR interface, view model and view, using
  stubbed and real Qt. They include architecture rules that keep the model and view model free of
  Qt and STIR, and checks that every source file carries the SPDX licence line.
- **Licence.** `LICENSE` (Apache-2.0) and `NOTICE`, shipped in the sdist and the wheel.

### Fixed

These came out of two independent code reviews, before the split from STIR:

- A failed load or slice read leaves the previous data, selection and widgets exactly as they were.
- The TOF profile under a resting cursor updates whenever the slice changes.
- Fixed global levels cover every TOF bin, so the colour scale does not change during playback.
- The `(segment, tof)` overload of `get_segment_by_view` is used, which every `ProjData` subclass
  has.
- Hovering reads single sinograms instead of whole segments, and the segment cache is capped at
  about 1 GiB.
- Two tests assumed POSIX paths and failed on Windows.
- A PySide6 crash during interpreter shutdown no longer fails the Linux/Python 3.11 test run.
- conda-forge `stir` on Windows looked for its config files in the wrong folder; CI sets
  `STIR_CONFIG_DIR` to the installed tables.

### Changed

- The project was renamed from `stir-projdata-viewer`. The PyPI name is
  `PETProjectionDataVisualization`, the import package is `pet_projection_data_visualization` and
  the command is `pet-projection-data-visualization`.

[Unreleased]: https://github.com/robbietuk/PETProjectionDataVisualization/commits/main
