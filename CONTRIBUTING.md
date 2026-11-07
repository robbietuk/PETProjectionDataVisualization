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

## Pull requests

All changes go to `main` through pull requests. Nothing is pushed to `main` directly.

1. Branch from `main`, named for the kind of change: `feature/...`, `fix/...`, `ci/...`, `docs/...`,
   `port/...`.
2. Add a line for every user-visible change under **Unreleased** in [CHANGELOG.md](CHANGELOG.md),
   under Added, Changed, Deprecated, Removed, Fixed or Security.
3. The pull request description says what changed and why, how it was tested, and anything that
   was not tested.
4. CI must be green: pre-commit, the tests on all three operating systems, real STIR, and the build.

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
like `v2.0.0rc1`. The first release is `v1.0.0`.

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
