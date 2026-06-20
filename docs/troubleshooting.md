# Troubleshooting

This page lists common problems and direct fixes.

## `ModuleNotFoundError: No module named 'tep_studio'`

Run commands with `PYTHONPATH=src` from the repository root:

```bash
PYTHONPATH=src python3 your_script.py
```

Or install the package in editable mode:

```bash
python3 -m pip install -e .
```

## Native extension is missing

If import fails because the CFFI extension is missing, build it (requires
`setuptools>=68`):

```bash
python3 -m pip install -U "setuptools>=68"
python3 setup.py build_ext --inplace
```

Then rerun your script with:

```bash
PYTHONPATH=src python3 your_script.py
```

The compiled extension is platform-specific and is not tracked in version control,
so it must be rebuilt after moving the repository to a different machine or
operating system. An extension built for another platform will fail to import with
an architecture-mismatch error.

## Wrong-architecture extension

If the import error says the extension *is present but failed to load on this
platform* (and reports your OS and CPU), the compiled file was built for a different
operating system or CPU architecture — for example, a macOS arm64 build checked out
on Linux. Reinstall the matching prebuilt wheel:

```bash
python3 -m pip install --force-reinstall tep-studio
```

or rebuild from source on this machine:

```bash
python3 -m pip install -e .
```

## `error: could not create '.../_tep_native.abi3.so': No such file or directory`

`python3 setup.py build_ext --inplace` raises this when `setuptools` is older than
version 68. Old versions ignore the `src/` package layout and try to copy the
compiled artifact to a `tep_studio/` directory relative to the current working
directory, which does not exist. Upgrade `setuptools` and rebuild:

```bash
python3 -m pip install -U "setuptools>=68"
python3 setup.py build_ext --inplace
```

The editable install (`python3 -m pip install -e .`) avoids this because build
isolation provisions a compliant `setuptools` automatically.

## Build fails because no compiler is available

Install a C compiler for your platform.

On macOS, install Xcode command line tools:

```bash
xcode-select --install
```

Then retry:

```bash
python3 -m pip install -U "setuptools>=68"
python3 setup.py build_ext --inplace
```

## `ValueError: Expected shape (12,), got ...`

The action passed to `advance()` must be exactly 12 values:

```python
result = sim.advance(action, control_interval=0.01)
```

Check:

```python
print(np.asarray(action).shape)
```

Expected:

```text
(12,)
```

## `ValueError: Expected shape (28,), got ...`

The disturbance vector must be exactly 28 values:

```python
disturbances = np.zeros(28)
result = sim.advance(action, control_interval=0.01, disturbances=disturbances)
```

## `NotImplementedError` for operating modes

The high-level `reset(mode=...)` API currently supports `mode="mode1"` by default. For another operating point, supply an explicit 50-state `initial_state`.

## `NotImplementedError` for action level

The current `advance()` implementation supports:

```python
action_level="direct_mv"
```

Other authority levels, such as regulatory setpoints or economic targets, are not implemented yet.

## Parquet export fails

`TrajectoryDataset.to_parquet()` needs a Parquet engine.

Install one:

```bash
python3 -m pip install pyarrow
```

Or use CSV:

```python
dataset.to_csv("trajectory.csv")
```

## MkDocs is not installed

Install it:

```bash
python3 -m pip install mkdocs
```

Then preview:

```bash
python3 -m mkdocs serve
```

If network access is blocked, you can still edit the Markdown files under `docs/` and build later when package installation is available.

## The simulator shuts down

A shutdown can be expected behavior. Inspect:

```python
print(result.shutdown_status)
print(result.events)
print(result.constraint_margins)
```

For the R12 open-loop example, high reactor pressure shutdown near `1.07 h` is expected.
