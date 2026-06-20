"""Central design tokens, reusable style dicts, and the shared Plotly template.

Single source of truth for the interface look so colors/spacing/typography are not
re-spelled inline across ``layout.py``/``widgets.py``/``callbacks.py``. Pure data
plus one Plotly template registration (plotly is a ``ui`` dependency). The pseudo
states buttons/inputs need (``:hover``/``:focus``/``:disabled``) and the richer
chrome (header, pill tabs) live in the global CSS in ``app.py`` -- inline styles
cannot express them -- and reference the same values via CSS variables, so this
module and that CSS must stay in sync.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

# -- color tokens (light theme) -------------------------------------------
BG = "#f4f5fb"  # app background (a CSS gradient overlays this in app.py)
SURFACE = "#ffffff"  # cards
SURFACE_ALT = "#f6f7fc"  # code/pre, table header, metric cards, hover fills
BORDER = "#e7e9f2"
BORDER_STRONG = "#d3d7e6"
TEXT = "#1c2333"
TITLE = "#0f1426"
TEXT_MUTED = "#5b6478"
TEXT_FAINT = "#99a0b4"
PRIMARY = "#6d5cf5"  # indigo accent
PRIMARY_HOVER = "#5b48ec"
PRIMARY_ACTIVE = "#4a39d4"
ACCENT = "#06b6d4"  # cyan, for small highlights
PRIMARY_GRADIENT = "linear-gradient(135deg, #6d5cf5 0%, #8b5cf6 100%)"
SUCCESS = "#0f9d6b"
WARNING = "#b45309"
DANGER = "#d92d20"
DANGER_BG = "#fef3f2"
SUCCESS_BG = "#ecfdf3"
WARNING_BG = "#fffaeb"
FOCUS_RING = "rgba(109,92,245,0.30)"

# -- plot palette (sourced by figures.py) ---------------------------------
BLUE = "#3b6df0"  # primary single-trace color
RED = "#e5484d"  # constraint-limit lines
PALETTE = ["#6d5cf5", "#06b6d4", "#0f9d6b", "#f59e0b", "#ef4444", "#8b5cf6", "#0ea5e9"]
GRID = "#eef0f7"

# -- typography -----------------------------------------------------------
FONT_FAMILY = 'system-ui, -apple-system, "Segoe UI", Roboto, Inter, sans-serif'
FONT_MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
FS_XS = "11px"
FS_SM = "12px"
FS_MD = "13px"
FS_LG = "16px"
FS_XL = "22px"

# -- spacing scale --------------------------------------------------------
SP_1 = "4px"
SP_2 = "8px"
SP_3 = "12px"
SP_4 = "16px"
SP_5 = "24px"

# -- radius / shadow ------------------------------------------------------
RADIUS = "14px"
RADIUS_SM = "9px"
SHADOW = "0 1px 2px rgba(16,24,40,0.04), 0 1px 3px rgba(16,24,40,0.06)"
SHADOW_MD = "0 8px 24px rgba(16,24,40,0.10)"


# -- reusable style dicts -------------------------------------------------
CARD = {
    "border": f"1px solid {BORDER}",
    "borderRadius": RADIUS,
    "padding": "18px",
    "marginBottom": SP_3,
    "backgroundColor": SURFACE,
    "boxShadow": SHADOW,
}
COL_LEFT = {"flex": "0 0 360px", "maxWidth": "360px"}
COL_RIGHT = {"flex": "1 1 auto", "minWidth": "0"}
ROW = {"display": "flex", "gap": SP_4, "alignItems": "flex-start"}

# Tabs render as a segmented pill bar (container styled in app.py CSS via #tabs).
TAB = {
    "padding": "8px 18px",
    "fontWeight": "600",
    "fontSize": FS_MD,
    "border": "none",
    "borderRadius": "10px",
    "backgroundColor": "transparent",
    "color": TEXT_MUTED,
}
TAB_SELECTED = {
    **TAB,
    "color": "#ffffff",
    "backgroundColor": PRIMARY,
    "boxShadow": "0 2px 8px rgba(109,92,245,0.35)",
}

# Buttons carry a className (so the CSS pseudo-states in app.py apply) plus a
# minimal inline dict for per-instance layout (width/margins).
BTN_PRIMARY_CLASS = "tep-btn tep-btn--primary"
BTN_SECONDARY_CLASS = "tep-btn tep-btn--secondary"
BTN_PRIMARY = {"width": "100%", "padding": "10px 14px", "fontWeight": "600"}
BTN_SECONDARY = {"padding": "7px 14px", "fontWeight": "500"}

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
        "padding": "9px 12px",
        "fontSize": FS_SM,
        "fontWeight": "500",
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
    tpl.layout.plot_bgcolor = "rgba(0,0,0,0)"
    tpl.layout.colorway = PALETTE
    axis = dict(
        gridcolor=GRID,
        zerolinecolor=BORDER,
        linecolor=BORDER_STRONG,
        ticks="outside",
        tickcolor=BORDER_STRONG,
        tickfont=dict(size=11, color=TEXT_MUTED),
        title_font=dict(size=12, color=TEXT_MUTED),
    )
    tpl.layout.xaxis = dict(axis)
    tpl.layout.yaxis = dict(axis)
    tpl.layout.legend = dict(bgcolor="rgba(255,255,255,0.65)", borderwidth=0, font=dict(size=11, color=TEXT_MUTED))
    tpl.layout.title = dict(font=dict(size=15, color=TITLE), x=0.01, xanchor="left")
    tpl.layout.colorscale = dict(sequential=[[0, "#eef0fb"], [1, PRIMARY]])
    pio.templates["tep"] = tpl


_register_template()
