# conda-forge recipe

`recipe.yaml` is the conda-forge recipe for `petprojectiondatavisualization`,
in the v1 (rattler-build) format that
[conda-forge/staged-recipes](https://github.com/conda-forge/staged-recipes) accepts.
It builds a `noarch: python` package from the PyPI sdist and depends on the
conda-forge `stir` package, so a single

```bash
conda install -c conda-forge petprojectiondatavisualization
```

installs the viewer, Qt and STIR together. This copy is the source of truth until
the feedstock exists; after that, change the recipe in the feedstock instead.

## Before submitting

1. `LICENSE` must be in the repository (Step 4 of `docs/PORT_PLAN.md`; not added yet);
   the recipe's `license_file: LICENSE` fails without it.
2. Version 1.0.0 must be on PyPI as an sdist named
   `petprojectiondatavisualization-1.0.0.tar.gz` (hatchling's normalised name).

## Submit to staged-recipes

1. Fork https://github.com/conda-forge/staged-recipes on GitHub and clone your fork:

   ```bash
   git clone git@github.com:robbietuk/staged-recipes.git
   ```

   ```bash
   cd staged-recipes && git checkout -b petprojectiondatavisualization
   ```

2. Copy the recipe in (the folder name is the conda package name):

   ```bash
   mkdir -p recipes/petprojectiondatavisualization
   ```

   ```bash
   cp /path/to/PETProjectionDataVisualization/recipe/recipe.yaml recipes/petprojectiondatavisualization/
   ```

   Do not copy this README; staged-recipes wants only the recipe.

3. Fill in the sha256. Take it from the "Download files" page of
   https://pypi.org/project/PETProjectionDataVisualization/#files ("view hashes"
   next to the `.tar.gz`), or compute it from the published file:

   ```bash
   curl -sL https://pypi.org/packages/source/p/petprojectiondatavisualization/petprojectiondatavisualization-1.0.0.tar.gz | shasum -a 256
   ```

   Replace the all-zero `sha256:` and delete the placeholder comment above it.

4. Optionally build locally first (needs [rattler-build](https://rattler.build) or
   Docker): from the staged-recipes root, `python build-locally.py` and pick a
   platform, or `rattler-build build -r recipes/petprojectiondatavisualization -c conda-forge`.

5. Commit, push and open a pull request against `conda-forge/staged-recipes:main`,
   filling in its checklist. Title it e.g. "Add petprojectiondatavisualization".

6. The linter bot (`conda-forge-admin`) comments on the PR with any lint
   problems; fix them and push until it reports the recipe is in excellent
   condition and CI is green. Then comment
   `@conda-forge/help-python, ready for review!` to ask for a review.

7. A reviewer merges the PR. conda-forge then creates
   `conda-forge/petprojectiondatavisualization-feedstock`, adds `robbietuk` as a
   maintainer (from `extra.recipe-maintainers`) and publishes the package to the
   `conda-forge` channel, usually within an hour of the feedstock's first build.

## After the feedstock exists

- The auto-update bot (`regro-cf-autotick-bot`) watches PyPI. When a new version
  is released it opens a PR on the feedstock bumping `version` and `sha256`;
  check the dependencies still match `pyproject.toml`, then merge it.
- For recipe-only fixes, bump `build.number` in the feedstock and open a PR there.
- Keep `run` requirements in step with `[project].dependencies` in
  `pyproject.toml`, plus `stir`, which is not on PyPI and so is listed only here.
