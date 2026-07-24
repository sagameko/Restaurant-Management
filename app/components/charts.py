"""Shared Plotly styling.

Palette validated with the dataviz skill's `validate_palette.js` (fixed
hue order, ALL CHECKS PASS on adjacent-pair colorblind separation).
Categorical hues are always assigned in this order — never re-cycled or
re-sorted per chart — so a series' color stays stable across pages.
"""

from __future__ import annotations

import plotly.graph_objects as go

CATEGORICAL = [
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#4a3aa7",  # violet
    "#e34948",  # red
]

SEQUENTIAL_BLUE = [
    "#cde2fb",
    "#9ec5f4",
    "#6da7ec",
    "#3987e5",
    "#256abf",
    "#184f95",
    "#0d366b",
]

DIVERGING_BLUE_RED = ["#0d366b", "#6da7ec", "#f0efec", "#e87878", "#8a1f1f"]

STATUS = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",
}

GRIDLINE = "#e1e0d9"
MUTED_TEXT = "#898781"


def style_fig(fig: go.Figure, *, legend: bool = True) -> go.Figure:
    """Apply consistent chrome: transparent surfaces, recessive gridlines,
    legend placement. Never sets a second y-axis — every chart here uses
    one axis; two differently-scaled measures get two charts instead.
    """
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=CATEGORICAL,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02} if legend else None,
        showlegend=legend,
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
        font_color=MUTED_TEXT,
    )
    fig.update_xaxes(gridcolor=GRIDLINE, zeroline=False)
    fig.update_yaxes(gridcolor=GRIDLINE, zeroline=False)
    return fig
