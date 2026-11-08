# Contributing

## Development setup

```sh
git clone git@github.com:robbietuk/PETProjectionDataVisualization.git
cd PETProjectionDataVisualization
python -m venv .venv && . .venv/bin/activate      # Python 3.11 or newer
pip install -e ".[test]"
pre-commit install                                  # optional: pip install pre-commit
QT_QPA_PLATFORM=offscreen pytest                    # the same command CI runs
```

The real-STIR tests run only where `import stir` works. Use a conda environment with conda-forge
`stir` and point the tests at a file with `STIR_TEST_PROJDATA=/path/to/file.hs`.

### VS Code

`.vscode/launch.json` adds three configurations to the **Run and Debug** panel (Ctrl+Shift+D / Cmd+Shift+D).
Pick one from the drop-down and press F5:

- **Viewer: demo data** starts the viewer on the built-in synthetic data set (`--demo`, needs no STIR).
- **Viewer: pick a file** asks for the path to a `.hs` or `.npy` file, then opens the viewer on it.
- **Pytest: current file** runs pytest on the test file open in the editor. Only this configuration sets
  `QT_QPA_PLATFORM=offscreen`; the viewer configurations open real windows.

VS Code offers the recommended extensions from `.vscode/extensions.json` (Python and Python Debugger) when
you open the folder. Every configuration runs `${workspaceFolder}/.venv/bin/python`, the environment from
the setup above. If you use conda instead (for example to have `stir`), either select the conda
environment with **Python: Select Interpreter** and delete the `"python"` lines from your local copy of
`launch.json`, or change them to your environment's interpreter, such as
`~/miniforge3/envs/stir/bin/python`; do not commit that change. On Windows the venv interpreter is
`.venv\Scripts\python.exe`. Other files in `.vscode/`, such as `settings.json`, are git-ignored.

## Type checking

`src/`, `scripts/` and `packaging/` are type-checked with [Pyrefly](https://pyrefly.org) in strict mode, as a
pre-commit hook (so also in CI). The settings are in `pyproject.toml` under `[tool.pyrefly]`:

```sh
pre-commit run pyrefly-check --all-files            # the same check CI runs (pinned Pyrefly and dependencies)
pip install pyrefly==1.4.1 && pyrefly check         # or directly, against the active environment
```

The hook checks against numpy 2.4 (the newest numpy that installs on Python 3.11); a direct run uses the
numpy of the active environment, whose stubs can differ slightly. CI runs the hook.

What strict means here:

- Every function and method annotates all parameters and its return type; generic classes get their type
  arguments (`frozenset[str]`, `npt.NDArray[np.float32]`, `ChoiceOptions[SliceMode]`), and overriding methods
  carry `@override` (from `view/_compat.py`, since `typing.override` needs Python 3.12).
- No `Any`, written or inferred. The one exception is the `StirObject` alias in
  `stir_interface/swig_gateway.py`: the SWIG `stir` module has no type information, and that file converts
  everything it returns to plain Python and numpy types.
- pyqtgraph has no type information either. `typings/pyqtgraph/` holds stubs for the part of its API the
  view uses; extend them when the view starts using more of pyqtgraph.
- A suppression is narrow and says why: `# pyrefly: ignore[<error-kind>]  # <reason>`. Unused suppressions
  are errors.

The tests are not type-checked: they read optional view-model state and monkeypatch fakes on purpose,
which would need an `assert` or a suppression on most lines.

## Pull requests

All changes go to `main` through pull requests. Nothing is pushed to `main` directly.

1. Branch from `main`, named for the kind of change: `feature/...`, `fix/...`, `ci/...`, `docs/...`,
   `port/...`.
2. Add a line for every user-visible change under **Unreleased** in [CHANGELOG.md](CHANGELOG.md),
   under Added, Changed, Deprecated, Removed, Fixed or Security.
3. The pull request description says what changed and why, how it was tested, and anything that
   was not tested.
4. CI must be green: pre-commit, the tests on all three operating systems, real STIR, and the build.

## Agents

Claude agents triage issues, implement what the maintainer approves with `/approve`, review every pull
request and fix the findings. They never merge. How it works, the commands and the one-time setup are in
[docs/AGENT_WORKFLOW.md](docs/AGENT_WORKFLOW.md); the rules agents follow are in [CLAUDE.md](CLAUDE.md).

## Versioning

The project follows [Semantic Versioning](https://semver.org/). The **git tag is the only source of
truth** for the version. No file in the repository holds a version number: `pyproject.toml` declares
`dynamic = ["version"]`, and hatch-vcs reads it from the latest `vMAJOR.MINOR.PATCH` tag when the
package is built or installed. `pet-projection-data-visualization --version` and
`pet_projection_data_visualization.__version__` report the same value.

| Change | Bump | Example |
| --- | --- | --- |
| Incompatible change to the command line, the Python API (`launch`, the sources), or supported file layouts | MAJOR | 1.4.2 -> 2.0.0 |
| New feature, backwards compatible | MINOR | 1.4.2 -> 1.5.0 |
| Bug fix only | PATCH | 1.4.2 -> 1.4.3 |

A build between tags gets a development version such as `1.4.3.dev5+g1a2b3c4`. Pre-releases use tags
like `v2.0.0rc1`, `v2.0.0b1` or `v2.0.0a1` (no dash or dot before the suffix; the same rule is in
`pyproject.toml` and `scripts/release_notes.py`). A pre-release is published to PyPI as a pre-release
(pip installs it only with `--pre` or an explicit version), and its GitHub Release is marked as a
pre-release; its notes come from `## [X.Y.ZrcN]` if present, otherwise from `## [Unreleased]`.
The first release is `v1.0.0`.

## Releasing

1. Open a pull request that renames `## [Unreleased]` in CHANGELOG.md to `## [X.Y.Z] - YYYY-MM-DD`,
   adds a new empty `## [Unreleased]` above it, and updates the compare links at the bottom. Merge it.
2. Tag the merge commit on `main` and push the tag:

   ```sh
   git switch main && git pull
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```

3. `build.yml` checks that the tag is a valid semantic version, that the built packages report the same
   version, and that CHANGELOG.md has a `## [X.Y.Z]` section. It then publishes to TestPyPI, then PyPI,
   and creates a GitHub Release with that changelog section as its notes.

Before the first release, set up the publishing side once:

- Add a trusted publisher on test.pypi.org and on pypi.org: owner `robbietuk`, repository
  `PETProjectionDataVisualization`, workflow `build.yml`, environments `testpypi` and `pypi`.
- In the repository settings, under Environments, create `testpypi` and `pypi`. Give `pypi` a required
  reviewer, so a release waits for a click.
