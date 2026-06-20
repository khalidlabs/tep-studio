# TEP Studio — Hugging Face Spaces (Docker SDK) image.
#
# The native simulation kernel (_tep_native.abi3.so) is git-ignored and NOT in the
# repo, so it must be COMPILED from temexd_mod/temexd_mod.c via the CFFI build during
# the image build. That needs a C toolchain (gcc) and the cffi build dependency,
# installed BEFORE `pip install`. We build as root so the compiled .so and the
# installed package land in a layer the runtime UID-1000 user can read, then switch
# to that user per HF Spaces requirements.

FROM python:3.11-slim

# --- Build toolchain for the CFFI native extension (compiled at install time) ---
# build-essential pulls in gcc; cffi is provisioned by pip from pyproject build-system.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create the non-root user HF Spaces runs as (UID 1000), per HF docs.
RUN useradd -m -u 1000 user

# Don't write .pyc into read-only layers; stream logs unbuffered to the HF logs tab.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Build context: copy the whole repo to the build dir. The CFFI build
# (_cffi_build.py, ROOT=parents[3]) reads temexd_mod/temexd_mod.c relative to this
# tree, so src/, temexd_mod/, setup.py, pyproject.toml and MANIFEST.in must all be here.
WORKDIR /app
COPY . /app

# Upgrade build tooling, install the package (with the UI extra) + gunicorn. This
# compiles _tep_native.abi3.so into the installed package. The final import line is a
# BUILD-TIME smoke test: if the kernel didn't compile or the app can't construct, the
# build fails visibly instead of crash-looping at runtime.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir ".[ui]" gunicorn \
    && python -c "import tep_studio, tep_studio.simulation.native; from tep_studio.ui import create_app; create_app()"

# --- Switch to the non-root runtime user ---
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HOST=0.0.0.0 \
    PORT=7860 \
    XDG_CACHE_HOME=/home/user/.cache \
    MPLCONFIGDIR=/home/user/.cache/matplotlib \
    NUMBA_CACHE_DIR=/home/user/.cache/numba

# wsgi.py lives in /app and exposes `server = app.server`. Run gunicorn from /app so
# `wsgi:server` is importable; the package itself is in site-packages, cwd-independent.
WORKDIR /app
EXPOSE 7860

# Single worker: RunStore is a process-local in-memory OrderedDict, so a second worker
# would not see runs created in the first (Compare/Export would intermittently fail).
# Four threads give safe in-process concurrency — Dash callbacks are short and release
# the GIL inside the native C kernel / scipy solver.
CMD ["gunicorn", "--workers", "1", "--threads", "4", "--timeout", "120", "--bind", "0.0.0.0:7860", "wsgi:server"]
