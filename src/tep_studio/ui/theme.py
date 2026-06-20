"""Central design tokens, reusable style dicts, and the shared Plotly template.

Single source of truth for the interface look. Design principles: a neutral base
(near-white surfaces, dark-grey text, light-grey borders) with one accent colour used
only for interactive states (active tab, primary button, focus ring, selected items);
one spacing scale applied uniformly; every control the same height/border/radius; a
restrained typographic hierarchy from one sans-serif family; bounded cards with subtle
borders, not heavy shadows. The pseudo-states controls need (``:hover``/``:focus``/
``:disabled``) and the chrome live in the global CSS in ``app.py`` and reference the
same values via CSS variables, so this module and that CSS must stay in sync.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

# -- neutral base ---------------------------------------------------------
BG = "#f6f7f9"  # near-white page
SURFACE = "#ffffff"  # cards
SURFACE_ALT = "#f3f4f6"  # table header / code / hover fills
BORDER = "#e5e7eb"  # light grey
BORDER_STRONG = "#d1d5db"
TEXT = "#1f2937"  # dark grey body text (not pure black)
TITLE = "#111827"  # headings
TEXT_MUTED = "#6b7280"
TEXT_FAINT = "#9ca3af"

# -- single accent (interactive states only) ------------------------------
PRIMARY = "#4f46e5"
PRIMARY_HOVER = "#4338ca"
PRIMARY_ACTIVE = "#3730a3"
PRIMARY_SOFT = "#eef2ff"  # the accent at low intensity (selected/hover tint)
FOCUS_RING = "rgba(79,70,229,0.35)"

# -- semantic feedback (banners only; not decoration) ---------------------
SUCCESS = "#15803d"
WARNING = "#b45309"
DANGER = "#b91c1c"
SUCCESS_BG = "#f0fdf4"
WARNING_BG = "#fffbeb"
DANGER_BG = "#fef2f2"

# -- muted plot sequence (data series, applied via the Plotly template) ----
BLUE = "#4c72b0"  # primary single-trace colour
RED = "#c44e52"  # constraint-limit lines
PALETTE = ["#4c72b0", "#dd8452", "#55a868", "#c44e52", "#8172b3", "#937860", "#7f7f7f"]
GRID = "#eef0f3"

# -- typography (one family; size + weight deliberate) --------------------
FONT_FAMILY = 'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
FONT_MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
FS_XS = "11px"
FS_SM = "12px"
FS_MD = "13px"
FS_LG = "15px"
FS_XL = "20px"

# -- one spacing scale ----------------------------------------------------
SP_1 = "4px"
SP_2 = "8px"
SP_3 = "12px"
SP_4 = "16px"
SP_5 = "24px"

# -- radius / control height / shadow -------------------------------------
RADIUS = "10px"  # cards
RADIUS_SM = "6px"  # controls
CONTROL_HEIGHT = "34px"
SHADOW = "0 1px 2px rgba(17,24,39,0.04)"  # whisper; cards lean on borders


# -- reusable style dicts -------------------------------------------------
CARD = {
    "border": f"1px solid {BORDER}",
    "borderRadius": RADIUS,
    "padding": SP_4,
    "marginBottom": SP_3,
    "backgroundColor": SURFACE,
    "boxShadow": SHADOW,
}
COL_LEFT = {"flex": "0 0 340px", "maxWidth": "340px"}
COL_RIGHT = {"flex": "1 1 auto", "minWidth": "0"}
ROW = {"display": "flex", "gap": SP_4, "alignItems": "flex-start"}

# Tabs: a bottom-bordered bar with an accent underline on the active tab.
TAB = {
    "padding": "10px 14px",
    "fontWeight": "500",
    "fontSize": FS_MD,
    "border": "none",
    "borderBottom": "2px solid transparent",
    "backgroundColor": "transparent",
    "color": TEXT_MUTED,
}
TAB_SELECTED = {**TAB, "fontWeight": "600", "color": PRIMARY, "borderBottom": f"2px solid {PRIMARY}"}

# Buttons carry a className (CSS owns colour/height/states); the dict is layout-only.
BTN_PRIMARY_CLASS = "tep-btn tep-btn--primary"
BTN_SECONDARY_CLASS = "tep-btn tep-btn--secondary"
BTN_PRIMARY = {"width": "100%"}
BTN_SECONDARY = {}

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


# -- Plotly template (one template, applied everywhere) -------------------
def _register_template() -> None:
    """Register the shared ``"tep"`` template once at import: transparent background,
    light gridlines, bottom/left spines only, consistent margins, muted colourway.

    A bare ``Template()`` carries no ``uirevision``, so figure builders keep their
    ``uirevision=None`` default.
    """
    tpl = go.layout.Template()
    tpl.layout.font = dict(family=FONT_FAMILY, size=12, color=TEXT)
    tpl.layout.paper_bgcolor = "rgba(0,0,0,0)"
    tpl.layout.plot_bgcolor = "rgba(0,0,0,0)"
    tpl.layout.colorway = PALETTE
    tpl.layout.margin = dict(l=56, r=16, t=40, b=44)
    axis = dict(
        gridcolor=GRID,
        zeroline=False,
        showline=True,
        linecolor=BORDER_STRONG,
        linewidth=1,
        mirror=False,  # no top / right spine
        ticks="outside",
        ticklen=4,
        tickcolor=BORDER_STRONG,
        tickfont=dict(size=11, color=TEXT_MUTED),
        title_font=dict(size=12, color=TEXT_MUTED),
    )
    tpl.layout.xaxis = dict(axis)
    tpl.layout.yaxis = dict(axis)
    tpl.layout.legend = dict(bgcolor="rgba(0,0,0,0)", borderwidth=0, font=dict(size=11, color=TEXT_MUTED))
    tpl.layout.title = dict(font=dict(size=13, color=TITLE), x=0.0, xanchor="left")
    pio.templates["tep"] = tpl


_register_template()
