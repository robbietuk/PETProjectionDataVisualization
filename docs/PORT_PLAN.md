# Port plan: from STIR's examples folder to this repository

This file lists, in order, the work that turns the viewer copied out of STIR
(`examples/python/projdata_viewer` on `robbietuk/STIR`, branch `projdata_viewer/pyside6_rewrite`)
into a standalone project published on PyPI and conda-forge.
Each step is one branch and one pull request into `main`. CI must pass before a step is merged.
The overall release plan is the doc *PET Projection Data Visualization: extraction and release plan*.

## Status

| Step | Branch | State |
| --- | --- | --- |
| 0. History split out of STIR | `main` | Done: 2 commits, all 383 tests pass, 1 skipped (real STIR) |
| 1. CI | `ci/github-actions` | Pushed. Real STIR passes on Ubuntu and macOS; Windows path bugs and a Linux/3.11 exit abort fixed, rerunning |
| 2. This plan | `docs/port-plan` | Pushed |
| 3. Rename and metadata | `port/rename` | Pushed (on top of `ci/github-actions`), CI running |
| 4. Headers and licence | `port/headers` | Waiting on the copyright line |
| 5. Docs cleanup | `port/docs` | Not started |
| 6. STIR setup window and `--check-stir` | `feature/stir-setup` | Not started |
| 7. First release, 0.1.0 | tag `v0.1.0` | Not started |
| 8. conda-forge recipe | `recipe/conda-forge` | Draft in progress (parallel session); submitted after 7 |
| 9. STIR side | branch on `robbietuk/STIR` | After 7 |
| 10. Desktop apps (double-click) | `feature/macos-app` | In progress (parallel session): macOS `.app`, Windows `.exe`, Linux folder build on free runners |

## Decisions needed

- **Names (decided).** Repository and PyPI name `PETProjectionDataVisualization`, import package
  `pet_projection_data_visualization`, command `pet-projection-data-visualization`, conda-forge package
  `petprojectiondatavisualization`.
- **Copyright line** for the headers and `LICENSE`, for example `Copyright 2026 Robert Twyman Skelly`.
  The licence stays Apache-2.0, the same as STIR.
- **STIR side.** Remove the in-tree copy from the STIR branch and leave a pointer to this package, or keep both.

## Steps

### 1. CI (`ci/github-actions`)

Modelled on STIR's `.github/workflows` (see Step 3 of the release plan): `pre-commit.yml`, `test.yml`
(pytest, offscreen Qt, Linux/macOS/Windows, Python 3.11 to 3.13), `stir.yml` (conda-forge `stir` 6.4.0
and STIR's own test files, so the real-STIR tests run) and `build.yml` (wheel and sdist, clean-venv install,
tag-triggered publishing). Also removes 4 unused imports found by ruff.

Done when: every job is green on the branch.

### 3. Rename and metadata (`port/rename`)

- `pyproject.toml`: `name`, `authors`, `maintainers`, `[project.urls]` (Homepage, Source, Issues),
  classifiers (Python 3.11 to 3.13, Apache, Medical Science Apps, Qt), keywords, `license = "Apache-2.0"`
  with `license-files`.
- If the import name changes: `git mv src/stir_projdata_viewer src/<new>`, then update every import,
  `tests/test_architecture.py`, `[project.scripts]`, `scripts/ci_smoke.py` and the docs.
  The 383 tests are the check.
- Version from one place (`__version__` read by hatch) and `--version` on the command line.

Done when: CI is green and `pip install` from a built wheel gives the new command.

### 4. Headers and licence (`port/headers`)

- Replace `# Part of STIR (see STIR/LICENSE.txt).` in the 28 files that have it with the agreed copyright
  line. Keep `SPDX-License-Identifier: Apache-2.0`.
- Add `LICENSE` (the full Apache-2.0 text) and a short `NOTICE` saying the project started inside STIR
  (UCL/STIR) and talks to STIR through its Python bindings.
- Add a test that fails if any source file lacks the SPDX line or still says "Part of STIR".

Done when: CI is green and `grep -r "Part of STIR"` finds nothing.

### 5. Docs cleanup (`port/docs`)

- Move `PLAN.md` to `docs/PLAN.md` and keep it as the design record and roadmap.
- README: the opening says what the project is on its own, not "a rewrite of a STIR example". Install
  section in this order: conda (`conda install -c conda-forge <name>`, once step 8 is done), pip (and how
  to point it at STIR), from source. Remove the STIR-CMake install paragraph. Add CI badges.
- `CONTRIBUTING.md`: `pip install -e .[test]`, `pytest`, `pre-commit install`, and the layering rules.
- `CHANGELOG.md` starting at 0.1.0.

Done when: CI is green and every README link resolves.

### 6. STIR setup window and `--check-stir` (`feature/stir-setup`)

From Step 4 and Appendix C of the release plan:

- `--check-stir`: prints the Python and NumPy versions, where `stir` was found (or the import error), its
  Python tag, and the library-path variables, with a plain-English diagnosis.
- A per-user config file (the platform's config folder) storing the STIR path. Precedence: command line,
  `STIR_PYTHON_PATH`, the config file, then plain `import stir`.
- A setup dialog shown when a `.hs` file is opened and STIR cannot be imported: what is missing, a path
  box with Browse, Test and Save buttons, and a short how-to. On Linux and macOS, restart once after
  Save so the library path takes effect. Windows: register `bin` and `lib` for DLL loading.
- Tests: the precedence order, the config round trip, the dialog with stubbed and real Qt, and
  `--check-stir` output with and without `stir`.

Done when: CI is green, including `stir.yml`, which checks that `--check-stir` finds conda-forge's `stir`.

### 7. First release, 0.1.0

1. On test.pypi.org and pypi.org, add a trusted publisher for this repository: workflow `build.yml`,
   environments `testpypi` and `pypi`. Create both environments in the repository settings, with a
   required reviewer on `pypi`.
2. Tag `v0.1.0` on `main`. `build.yml` publishes to TestPyPI, then to PyPI.
3. Check `pip install <name>` in a clean venv on each OS and run `--demo`.

### 8. conda-forge recipe (`recipe/conda-forge`)

- Draft `recipe/recipe.yaml` (noarch: python), with the PyPI sdist as the source and run requirements
  `python >=3.11`, `numpy`, `pyside6`, `pyqtgraph >=0.13.7` and `stir`. Tests: import, `--help`, and
  `--check-stir`.
- Build it locally with `rattler-build` to check, then open a pull request on
  `conda-forge/staged-recipes` from your fork. After it is merged, the feedstock bot opens a pull request
  for each new PyPI release.

### 9. STIR side

On `robbietuk/STIR`, depending on the decision above: remove `examples/python/projdata_viewer`, the CMake
install rule and the docs that describe it, and add a short section to `examples/python/README.md`
pointing at this package. Then open an issue on UCL/STIR proposing the pointer.

## Not verified yet

- CI on GitHub's runners, as opposed to locally (step 1 checks this).
- Memory use and speed on large TOF data.
- That the image orientation matches the old `stir.projdata_visualisation` tool.

### 10. Desktop apps (`feature/macos-app`)

A double-clickable build that includes conda-forge `stir`, made with PyInstaller: a `.app` for macOS, a one-folder
`.exe` for Windows and a one-folder build for Linux. `app.yml` builds all three on the standard GitHub-hosted
runners (`macos-latest`, `windows-latest`, `ubuntu-24.04`), which are free for public repositories, and uploads them as
artifacts. Unsigned at first: on macOS, the first launch needs right-click > Open.

## CI cost

Every workflow uses only standard GitHub-hosted runners and free actions. For a public repository these have no
minute limit. No larger runners or paid services.
