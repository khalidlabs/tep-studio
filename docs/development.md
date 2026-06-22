# Development

## Common Commands

Build the native extension (requires `setuptools>=68`; older versions mis-place the
compiled artifact under the `src/` layout):

```bash
python3 -m pip install -U "setuptools>=68"
python3 setup.py build_ext --inplace
```

Run tests:

```bash
PYTHONPATH=src python3 -m pytest -q
```

Run validation:

```bash
PYTHONPATH=src python3 -m tep_studio.simulation.validation run --suite all --solvers RK23 RK45
PYTHONPATH=src python3 -m tep_studio.simulation.validation figures
PYTHONPATH=src python3 -m tep_studio.simulation.validation report
```

Build documentation:

```bash
python3 -m mkdocs build --strict
```

Serve documentation locally:

```bash
python3 -m mkdocs serve
```

## Documentation Structure

```text
mkdocs.yml
docs/
  index.md
  getting-started.md
  first-simulation.md
  cookbook.md
  concepts.md
  architecture.md
  user-guide.md
  data.md
  gymnasium.md
  optimization.md
  control.md
  ui.md
  validation.md
  troubleshooting.md
  development.md
  assets/
    figures/
  reference/
    api.md
    schema.md
```

The docs summarize the public API and supplemental technical material. Keep the beginner path practical and command-driven. Keep detailed validation claims conservative and tied to generated artifacts.

## Publishing Documentation

The repository includes a GitHub Actions workflow for GitHub Pages. Enable Pages for the repository with "GitHub Actions" as the source, then push to `main`. The workflow installs the package, installs MkDocs, builds the site, and uploads the generated static files.

## Releasing (wheels + PyPI)

Cross-platform wheels and the PyPI upload are automated by `.github/workflows/wheels.yml`
(cibuildwheel). The workflow runs on a version tag (`v*`) or manual dispatch: it builds
wheels for Linux, macOS, and Windows on CPython 3.10–3.13 plus an sdist, smoke-tests that
each wheel imports and loads the native extension, and publishes to PyPI via Trusted
Publishing (OIDC, no stored token).

Before the first real release:

1. Confirm the PyPI project name `tep-studio` is available (or already yours).
2. Configure a PyPI Trusted Publisher for this repository and the `wheels` workflow.
3. Declare the license in `pyproject.toml` (e.g. `license = "BSD-3-Clause"`), add a
   `LICENSE` file, and fill in `[project.urls]`. Confirm and honor the upstream license
   of the bundled `temexd_mod/temexd_mod.c` (Bathelt, Ricker & Jelali, 2015).
4. Dry-run to TestPyPI first, then `pip install` from TestPyPI in a clean
   environment to confirm the wheel works end to end.

To cut a release: bump `version` in `pyproject.toml`, tag `vX.Y.Z`, and push the tag.
