"""Central design tokens, reusable style dicts, and the shared Plotly template.

Single source of truth for the interface look so colors/spacing/typography are not
re-spelled inline across ``layout.py``/``widgets.py``/``callbacks.py``. Pure data
plus one Plotly template registration (plotly is a ``ui`` dependency). The pseudo
states buttons/inputs need (``:hover``/``:focus``/``:disabled``) live in the global
CSS in ``app.py`` -- inline styles cannot express them -- and reference the same
values via CSS variables, so this module and that CSS must stay in sync.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

# -- color tokens (light theme) -------------------------------------------
BG = "#eef1f5"  # app background (matches the original body)
SURFACE = "#ffffff"  # cards
SURFACE_ALT = "#f6f8fa"  # code/pre, table header, hover fills
BORDER = "#e2e6ec"
BORDER_STRONG = "#cfd5de"
TEXT = "#1f2733"
TEXT_MUTED = "#5a6573"
TEXT_FAINT = "#99a0ab"
TITLE = "#16202e"
PRIMARY = "#6c4cf0"  # the existing accent (tabs)
PRIMARY_HOVER = "#5a3ce0"
PRIMARY_ACTIVE = "#4a2fc0"
SUCCESS = "#2f6f4e"
WARNING = "#b26a00"
DANGER = "#b22222"
DANGER_BG = "#fdeeee"
SUCCESS_BG = "#eef6f1"
WARNING_BG = "#fff6e8"
FOCUS_RING = "rgba(108,76,240,0.35)"

# -- plot palette (sourced by figures.py) ---------------------------------
BLUE = "#1f77b4"
RED = "#b22222"
PALETTE = ["#1f77b4", "#2f6f4e", "#d2691e", "#7b3fa0", "#c2185b", "#00838f", "#555555"]
GRID = "#eef1f5"

# -- typography -----------------------------------------------------------
FONT_FAMILY = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'
FONT_MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
FS_XS = "11px"
FS_SM = "12px"
FS_MD = "13px"
FS_LG = "15px"
FS_XL = "20px"

# -- spacing scale --------------------------------------------------------
SP_1 = "4px"
SP_2 = "8px"
SP_3 = "12px"
SP_4 = "16px"
SP_5 = "24px"

# -- radius / shadow ------------------------------------------------------
RADIUS = "8px"
RADIUS_SM = "6px"
SHADOW = "0 1px 2px rgba(16,32,46,0.04)"
SHADOW_MD = "0 4px 12px rgba(16,32,46,0.10)"


# -- reusable style dicts -------------------------------------------------
CARD = {
    "border": f"1px solid {BORDER}",
    "borderRadius": RADIUS,
    "padding": SP_4,
    "marginBottom": SP_3,
    "backgroundColor": SURFACE,
    "boxShadow": SHADOW,
}
COL_LEFT = {"flex": "0 0 360px", "maxWidth": "360px"}
COL_RIGHT = {"flex": "1 1 auto", "minWidth": "0"}
ROW = {"display": "flex", "gap": SP_3, "alignItems": "flex-start"}

TAB = {
    "padding": "9px 16px",
    "fontWeight": "500",
    "border": "none",
    "borderBottom": "3px solid transparent",
    "backgroundColor": "transparent",
    "color": TEXT_MUTED,
}
TAB_SELECTED = {
    **TAB,
    "fontWeight": "700",
    "borderBottom": f"3px solid {PRIMARY}",
    "backgroundColor": SURFACE,
    "color": PRIMARY,
}

# Buttons carry a className (so the CSS pseudo-states in app.py apply) plus a
# minimal inline dict for per-instance layout (width/margins).
BTN_PRIMARY_CLASS = "tep-btn tep-btn--primary"
BTN_SECONDARY_CLASS = "tep-btn tep-btn--secondary"
BTN_PRIMARY = {"width": "100%", "padding": SP_2, "fontWeight": "600"}
BTN_SECONDARY = {"padding": "6px 12px", "fontWeight": "500"}

INPUT = {"width": "120px"}
INPUT_WIDE = {"width": "100%"}

HIDDEN = {"display": "none"}

_STATUS_COLORS = {"muted": TEXT_MUTED, "success": SUCCESS, "warning": WARNING, "danger": DANGER, "running": PRIMARY}
_BANNER_BG = {"danger": DANGER_BG, "warning": WARNING_BG, "success": SUCCESS_BG}
_BANNER_FG = {"danger": DANGER, "warning": WARNING, "success": SUCCESS}


def status_style(kind: str = "muted") -> dict:
    """Inline style for the small one-line status text under a Run button."""
    return {"fontSize": FS_SM, "marginTop": SP_2, "color": _STATUS_COLORS.get(kind, TEXT_MUTED)}


def banner_style(kind: str = "danger") -> dict:
    """Inline style for a visible feedback banner (errors / warnings / success)."""
    fg = _BANNER_FG.get(kind, DANGER)
    return {
        "backgroundColor": _BANNER_BG.get(kind, DANGER_BG),
        "color": fg,
        "border": f"1px solid {fg}",
        "borderRadius": RADIUS_SM,
        "padding": "8px 12px",
        "fontSize": FS_SM,
        "marginTop": SP_2,
        "display": "block",
    }


# High-resolution PNG export via the Plotly modebar (no extra dependency).
GRAPH_CONFIG = {
    "displaylogo": False,
    "displayModeBar": True,
    "toImageButtonOptions": {"format": "png", "scale": 2, "filename": "tep_plot"},
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
}


# -- Plotly template ------------------------------------------------------
def _register_template() -> None:
    """Register the shared ``"tep"`` template once at import.

    A bare ``Template()`` carries no ``uirevision``, so figure builders keep their
    ``uirevision=None`` default (asserted by ``test_figures``).
    """
    tpl = go.layout.Template()
    tpl.layout.font = dict(family=FONT_FAMILY, size=12, color=TEXT)
    tpl.layout.paper_bgcolor = "rgba(0,0,0,0)"
    tpl.layout.plot_bgcolor = SURFACE
    tpl.layout.colorway = PALETTE
    axis = dict(gridcolor=GRID, zerolinecolor=BORDER, linecolor=BORDER_STRONG, ticks="outside", tickcolor=BORDER_STRONG)
    tpl.layout.xaxis = dict(axis)
    tpl.layout.yaxis = dict(axis)
    tpl.layout.legend = dict(bgcolor="rgba(255,255,255,0.6)", borderwidth=0)
    tpl.layout.title = dict(font=dict(size=14, color=TITLE), x=0.01, xanchor="left")
    pio.templates["tep"] = tpl


_register_template()
