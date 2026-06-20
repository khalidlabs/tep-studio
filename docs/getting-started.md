# Getting Started

This page gets the simulator running from a fresh checkout.

## 1. Open a terminal in the repository

The commands below assume your terminal is inside the repository root:

```bash
cd "/Users/khalid/Documents/Codex/TEP Studio"
```

You should see files such as `README.md`, `pyproject.toml`, `setup.py`, `src/`, and `temexd_mod/`.

## 2. Use Python 3.10 or newer

Check your Python version:

```bash
python3 --version
```

The package declares `requires-python = ">=3.10"`.

## 3. Install the package

The native CFFI extension is **built automatically** during installation — there is
no separate build step.

From PyPI (once published — prebuilt wheels, so no C compiler is needed):

```bash
python3 -m pip install tep-studio            # core
python3 -m pip install "tep-studio[ui]"      # + the web Simulation Studio
```

From a source checkout (this repository), use an editable install. Build isolation
provisions the required `setuptools>=68` and `cffi` automatically:

```bash
python3 -m pip install -e .                     # core
python3 -m pip install -e ".[ui]"               # + Studio
python3 -m pip install -e ".[ui,docs]"          # + Studio + docs tooling
```

If your environment blocks build isolation (for example, an offline machine),
upgrade the build tools first and append `--no-build-isolation`:

```bash
python3 -m pip install -U "setuptools>=68" wheel cffi
python3 -m pip install -e . --no-build-isolation
```

Installing from source compiles the C kernel, so you need a C compiler (Xcode command
line tools on macOS, `build-essential` on Debian/Ubuntu). The compiled extension is
platform-specific and is not tracked in version control; rebuild it after moving the
repository to a new machine or operating system. If the build fails, see
[Troubleshooting](troubleshooting.md).

## 4. Verify the installation

```bash
python3 -c "import tep_studio as t; print(t.__version__); t.quickstart()"
```

`quickstart()` runs a short closed-loop simulation and prints whether the plant was
stabilized. You can also drive the simulator from the terminal:

```bash
tep version
tep run --horizon 6           # a closed-loop run with a summary
tep list disturbances         # the disturbances you can inject
```

## 5. Run the test suite

If you installed the package (PyPI or editable), run pytest directly:

```bash
python3 -m pytest -q
```

If you are running from a source checkout **without** installing, put `src` on the
path instead: `PYTHONPATH=src python3 -m pytest -q`. The suite checks schema
dimensions, reset and advance behavior, snapshot/restore replay, shutdown mapping,
dataset generation, optimization rollout, linearization, and the Gymnasium API.

## 6. Run the smoke-test example

```bash
python3 -m tep_studio.simulation.examples.r12_open_loop
```

Expected behavior: the script prints the initial reactor pressure and then terminates
near `1.07 h` with a high reactor pressure shutdown — the base-case plant is open-loop
unstable. For a stabilized run, see [Closed-Loop Control](control.md).

## 7. Build this documentation site

Install MkDocs when network access is available:

```bash
python3 -m pip install mkdocs
```

Then build the site:

```bash
python3 -m mkdocs build
```

For live preview:

```bash
python3 -m mkdocs serve
```

Open the printed local URL, usually `http://127.0.0.1:8000`.
