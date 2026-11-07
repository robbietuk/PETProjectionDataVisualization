# Port plan: from STIR's examples folder to this repository

This file lists, in order, the work that turns the viewer copied out of STIR
(`examples/python/projdata_viewer` on `robbietuk/STIR`, branch `projdata_viewer/pyside6_rewrite`)
into a standalone project published on PyPI and conda-forge.
Each step is one branch and one pull request. CI must pass before a step is merged.
The overall release plan is the doc *PET Projection Data Visualization: extraction and release plan*.

## Pull requests are stacked

Most pull requests are based on the previous branch, not on `main`, so each one shows only its own changes:

```
main
├── #1 ci/github-actions
│   └── #2 port/rename                 (steps 3 and 4)
│       ├── #3 feature/versioning      (step 5)
│       │   ├── feature/lock-levels    (step 6)
│       │   └── #5 recipe/conda-forge  (step 11, draft)
│       └── #4 feature/macos-app       (step 7)
└── #6 docs/port-plan                  (this file)
```

Merge them in stack order (#1, #2, #3, lock levels, #4), each with a merge commit, not squash or rebase,
so the branches stacked on it keep their history. After a merge, GitHub retargets the next pull request
to the branch below it. #5 is merged after the first release (step 10). #6 is docs only and can be merged at any time.

## Status

| Step | Branch | State |
| --- | --- | --- |
| 0. History split out of STIR | `main` | Done: 2 commits, all 383 tests pass, 1 skipped (real STIR) |
| 1. CI | `ci/github-actions` (#1) | Done in PR, all checks green, including real STIR on Ubuntu, macOS and Windows |
| 2. This plan | `docs/port-plan` (#6) | In review |
| 3. Rename and metadata | `port/rename` (#2) | Done in PR, all checks green |
| 4. Headers and licence | `port/rename` (#2) | Done in PR; copyright holder to be confirmed |
| 5. Versioning, changelog, release automation | `feature/versioning` (#3) | Done in PR |
| 6. Lockable colour levels | `feature/lock-levels` | In progress (parallel session) |
| 7. Desktop apps (double-click) | `feature/macos-app` (#4) | Done in PR: app builds pass on macOS, Windows and Linux |
| 8. Docs cleanup | `port/docs` | Not started |
| 9. STIR setup window and `--check-stir` | `feature/stir-setup` | Not started |
| 10. First release, 1.0.0 | tag `v1.0.0` | Not started |
| 11. conda-forge recipe | `recipe/conda-forge` (#5, draft) | Draft; submitted after 10 |
| 12. STIR side | branch on `robbietuk/STIR` | After 10 |

## Decisions needed

- **Names (decided).** Repository and PyPI name `PETProjectionDataVisualization`, import package
  `pet_projection_data_visualization`, command `pet-projection-data-visualization`, conda-forge package
  `petprojectiondatavisualization`.
- **Copyright line.** The headers, `LICENSE` and `NOTICE` on `port/rename` say
  `Copyright 2026 Robert Twyman Skelly`. Confirm that this is the right holder before #2 is merged.
  The licence stays Apache-2.0, the same as STIR.
- **STIR side.** Remove the in-tree copy from the STIR branch and leave a pointer to this package, or keep both.

## Steps

### 1. CI (`ci/github-actions`, #1)

Modelled on STIR's `.github/workflows` (see Step 3 of the release plan): `pre-commit.yml`, `test.yml`
(pytest, offscreen Qt, Linux/macOS/Windows, Python 3.11 to 3.13), `stir.yml` (conda-forge `stir`, pinned
to 6.4 or newer, and STIR's own test files, so the real-STIR tests run) and `build.yml` (wheel and sdist,
clean-venv install on each OS, tag-triggered publishing). Also removes 4 unused imports found by ruff.

Each workflow runs once per pull request: on `pull_request` into any branch (so stacked pull requests are
tested too), and on `push` only to `main` and tags. A pull request runs the workflows that are in its
branch, so one based on `main` without #1 (such as #6) gets no checks until #1 is merged into `main`.

Done when: every job is green on the branch. Done.

### 2. This plan (`docs/port-plan`, #6)

This file. It is updated as each step is merged.

### 3. Rename and metadata (`port/rename`, #2)

- `pyproject.toml`: `name = "PETProjectionDataVisualization"`, `authors`, `[project.urls]` (Homepage,
  Source, Issues), classifiers (Python 3.11 to 3.13, Medical Science Apps, Visualization, Qt), keywords,
  `license = "Apache-2.0"` and `license-files` (PEP 639). No `maintainers`: the author is the maintainer.
- `src/stir_projdata_viewer` moved to `src/pet_projection_data_visualization`, with every import,
  `tests/test_architecture.py`, `[project.scripts]`, `scripts/ci_smoke.py` and the docs updated.
  The 383 tests are the check.

Done when: CI is green and `pip install` from a built wheel gives the new command. Done.

### 4. Headers and licence (on `port/rename`, #2)

- `# Part of STIR (see STIR/LICENSE.txt).` replaced in every source file by
  `Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).`,
  keeping `SPDX-License-Identifier: Apache-2.0`.
- `LICENSE` (the full Apache-2.0 text) and a short `NOTICE` saying the project started inside STIR and
  talks to STIR only through its Python bindings, without containing it.
- A test that fails if any source file lacks the SPDX line or still says "Part of STIR".

Done when: CI is green and `grep -r "Part of STIR"` finds nothing. Done; the copyright holder is still to be confirmed.

### 5. Versioning, changelog, release automation (`feature/versioning`, #3)

- Semantic versioning with hatch-vcs: the git tag `vMAJOR.MINOR.PATCH` is the only source of truth, and no
  file holds a version number. `--version` and `__version__` read the generated `_version.py`.
- `CHANGELOG.md` (Keep a Changelog, everything so far under Unreleased) and `CONTRIBUTING.md` (setup,
  pull-request rules, how to pick MAJOR/MINOR/PATCH, release steps). README links to both.
- On a `v*` tag, `build.yml` checks that the tag is a valid version, that every wheel and sdist carries it
  and that CHANGELOG.md has its section; then publishes to TestPyPI and PyPI and creates a GitHub Release
  with those notes.

Done when: CI is green. Done.

### 6. Lockable colour levels (`feature/lock-levels`, into `feature/versioning`)

A level mode switch: **Adaptive** (levels follow each view, as now) or **Locked** (vmin, vmax and the
colour bar stay the same across every view, segment and TOF bin, so slices can be compared by eye).
Tests for both modes and a CHANGELOG line.

Done when: CI is green.

### 7. Desktop apps (`feature/macos-app`, #4)

A double-clickable build that includes conda-forge `stir`, made with PyInstaller: a `.app` for macOS, a one-folder
`.exe` for Windows and a one-folder build for Linux. `app.yml` builds all three on the standard GitHub-hosted
runners (`macos-latest`, `windows-latest`, `ubuntu-24.04`) and uploads them as artifacts.
Unsigned at first: on macOS, the first launch needs right-click > Open.

Done when: the three app builds are green. Done.

### 8. Docs cleanup (`port/docs`)

- Move `PLAN.md` to `docs/PLAN.md` and keep it as the design record and roadmap.
- README: the opening says what the project is on its own, not "a rewrite of a STIR example". Install
  section in this order: conda (`conda install -c conda-forge petprojectiondatavisualization`, once step 11
  is done), pip (and how to point it at STIR), from source. Remove the STIR-CMake install paragraph. Add CI badges.
- `CHANGELOG.md` and `CONTRIBUTING.md` already come from step 5; add the layering rules to `CONTRIBUTING.md`.

Done when: CI is green and every README link resolves.

### 9. STIR setup window and `--check-stir` (`feature/stir-setup`)

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

### 10. First release, 1.0.0

1. On test.pypi.org and pypi.org, add a trusted publisher for this repository: workflow `build.yml`,
   environments `testpypi` and `pypi`. Create both environments in the repository settings, with a
   required reviewer on `pypi`.
2. Rename CHANGELOG.md's Unreleased section to `[1.0.0]`, then tag `v1.0.0` on `main`. `build.yml` runs
   the release checks, publishes to TestPyPI, then PyPI, and creates the GitHub Release.
3. Check `pip install PETProjectionDataVisualization` in a clean venv on each OS and run `--demo`.

### 11. conda-forge recipe (`recipe/conda-forge`, #5)

- `recipe/recipe.yaml` (noarch: python), with the PyPI 1.0.0 sdist as the source and its sha256 filled in
  after step 10. Host requirements need `hatch-vcs` as well as `hatchling` (step 5); the sdist carries its
  version in PKG-INFO, so no git metadata is needed. Run requirements `python >=3.11`, `numpy`, `pyside6`,
  `pyqtgraph >=0.13.7` and `stir`. Tests: import and `--help`; add `--check-stir` once step 9 adds it
  (it does not exist yet).
- Build it locally with `rattler-build` to check, then open a pull request on
  `conda-forge/staged-recipes` from your fork. After it is merged, the feedstock bot opens a pull request
  for each new PyPI release.

### 12. STIR side

On `robbietuk/STIR`, depending on the decision above: remove `examples/python/projdata_viewer`, the CMake
install rule and the docs that describe it, and add a short section to `examples/python/README.md`
pointing at this package. Then open an issue on UCL/STIR proposing the pointer.

## Not verified yet

- Memory use and speed on large TOF data.
- That the image orientation matches the old `stir.projdata_visualisation` tool.
- That the unsigned desktop apps open on other machines (only CI runners so far).
- The recipe build with `rattler-build`.

CI on GitHub's runners is verified: all workflows pass there, real STIR included.

## CI cost

Every workflow uses only standard GitHub-hosted runners and free actions. For a public repository these have no
minute limit. No larger runners or paid services.
