"""WSGI entry point for Hugging Face Spaces (Docker SDK) via gunicorn.

``create_app()`` (re-exported from ``tep_studio.ui``) returns a Dash app; gunicorn
needs a module-level WSGI callable, which is the underlying Flask server exposed as
``app.server``. Serve with:  ``gunicorn ... wsgi:server``
"""

from __future__ import annotations

from tep_studio.ui import create_app

# Build the Dash app once at import time (a single gunicorn worker imports this).
app = create_app()

# The WSGI callable gunicorn binds to: ``wsgi:server``.
server = app.server


if __name__ == "__main__":
    # Local fallback (not used by gunicorn): bind 0.0.0.0:7860 to mirror HF Spaces.
    import os

    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "7860")),
        debug=False,
    )
