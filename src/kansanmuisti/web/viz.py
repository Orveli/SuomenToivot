"""Riippumaton inline-SVG-visualisointi (ei JS-kirjastoja, ei build-vaihetta).

Kaikki funktiot palauttavat valmiin SVG-merkkijonon, joka upotetaan templateen.
Neutraali yksivärinen sävyasteikko (sininen) — väri koodaa vain suuruutta, ei
poliittista suuntaa.
"""
from __future__ import annotations

import math
from html import escape
from typing import List, Sequence, Tuple

ACCENT = "#1f4e79"
ACCENT_SOFT = "#cfe0f0"
INK = "#1a1c1f"
LINE = "#d9dde2"


def _pt(cx: float, cy: float, r: float, ang: float) -> Tuple[float, float]:
    return cx + r * math.cos(ang), cy + r * math.sin(ang)


def radar_svg(values: Sequence[Tuple[str, float]], size: int = 150,
              show_labels: bool = True) -> str:
    """Tutkakaavio. values = [(lyhyt_label, arvo 0..1), ...]."""
    n = len(values)
    if n < 3:
        return ""
    cx = cy = size / 2
    r = size / 2 - (26 if show_labels else 6)
    step = 2 * math.pi / n
    start = -math.pi / 2  # ylös
    grid = []
    for ring in (0.33, 0.66, 1.0):
        pts = [_pt(cx, cy, r * ring, start + i * step) for i in range(n)]
        grid.append('<polygon points="{}" fill="none" stroke="{}" stroke-width="0.6"/>'.format(
            " ".join(f"{x:.1f},{y:.1f}" for x, y in pts), LINE))
    axes = []
    labels = []
    poly = []
    for i, (label, v) in enumerate(values):
        v = max(0.0, min(1.0, v))
        ang = start + i * step
        ex, ey = _pt(cx, cy, r, ang)
        axes.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="{LINE}" stroke-width="0.5"/>')
        px, py = _pt(cx, cy, r * v, ang)
        poly.append(f"{px:.1f},{py:.1f}")
        if show_labels:
            lx, ly = _pt(cx, cy, r + 11, ang)
            anchor = "middle"
            if lx < cx - 4:
                anchor = "end"
            elif lx > cx + 4:
                anchor = "start"
            labels.append(
                f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="7" fill="#5b6168" '
                f'text-anchor="{anchor}" dominant-baseline="middle">{escape(label)}</text>')
    return (
        f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" role="img">'
        + "".join(grid) + "".join(axes)
        + f'<polygon points="{" ".join(poly)}" fill="{ACCENT}" fill-opacity="0.30" '
          f'stroke="{ACCENT}" stroke-width="1.4"/>'
        + "".join(labels) + "</svg>")


def line_chart_svg(series: List[Tuple[str, List[float]]], xlabels: List[str],
                   width: int = 760, height: int = 300) -> str:
    """Moniviivakaavio. series = [(nimi,[arvot]), ...], xlabels = vuodet."""
    if not series:
        return ""
    pad_l, pad_r, pad_t, pad_b = 38, 120, 14, 28
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    ymax = max((max(v) for _n, v in series if v), default=1) or 1
    n = len(xlabels)
    def X(i): return pad_l + (plot_w * i / max(n - 1, 1))
    def Y(v): return pad_t + plot_h - (plot_h * v / ymax)
    # eri sävyt (sininen→harmaa-asteikko, neutraali)
    palette = ["#1f4e79", "#3d7ab5", "#7aa7cf", "#9aa3ab", "#c08457", "#5a8f6b",
               "#8a6d9b", "#b5894d", "#4f6d8c", "#777"]
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img">']
    # akselit + y-ruudukko
    for frac in (0, 0.5, 1.0):
        yy = Y(ymax * frac)
        parts.append(f'<line x1="{pad_l}" y1="{yy:.1f}" x2="{pad_l+plot_w}" y2="{yy:.1f}" stroke="{LINE}" stroke-width="0.6"/>')
        parts.append(f'<text x="{pad_l-5}" y="{yy+3:.1f}" font-size="9" fill="#5b6168" text-anchor="end">{int(ymax*frac)}</text>')
    for i, xl in enumerate(xlabels):
        parts.append(f'<text x="{X(i):.1f}" y="{height-10}" font-size="9" fill="#5b6168" text-anchor="middle">{escape(str(xl))}</text>')
    for si, (name, vals) in enumerate(series):
        col = palette[si % len(palette)]
        pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vals))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2"/>')
        ly = pad_t + 12 + si * 15
        parts.append(f'<line x1="{pad_l+plot_w+8}" y1="{ly-3}" x2="{pad_l+plot_w+22}" y2="{ly-3}" stroke="{col}" stroke-width="2.5"/>')
        parts.append(f'<text x="{pad_l+plot_w+26}" y="{ly}" font-size="9.5" fill="{INK}">{escape(name)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def scatter_svg(points: List[Tuple[float, float, str]], xlabel: str, ylabel: str,
                width: int = 760, height: int = 420) -> str:
    """Hajontakaavio. points = [(x, y, hover-label), ...]. Neutraalit pisteet."""
    if not points:
        return ""
    pad_l, pad_r, pad_t, pad_b = 48, 16, 14, 40
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    xmax = max(p[0] for p in points) or 1
    ymax = max(p[1] for p in points) or 1
    def X(v): return pad_l + plot_w * v / xmax
    def Y(v): return pad_t + plot_h - plot_h * v / ymax
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img">']
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        yy = Y(ymax * frac)
        parts.append(f'<line x1="{pad_l}" y1="{yy:.1f}" x2="{pad_l+plot_w}" y2="{yy:.1f}" stroke="{LINE}" stroke-width="0.5"/>')
        parts.append(f'<text x="{pad_l-5}" y="{yy+3:.1f}" font-size="9" fill="#5b6168" text-anchor="end">{int(ymax*frac)}</text>')
        xx = X(xmax * frac)
        parts.append(f'<text x="{xx:.1f}" y="{height-22}" font-size="9" fill="#5b6168" text-anchor="middle">{int(xmax*frac)}</text>')
    for x, y, label in points:
        parts.append(
            f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="3.2" fill="{ACCENT}" fill-opacity="0.55" '
            f'stroke="{ACCENT}" stroke-width="0.4"><title>{escape(label)}</title></circle>')
    parts.append(f'<text x="{pad_l+plot_w/2:.0f}" y="{height-6}" font-size="10" fill="{INK}" text-anchor="middle">{escape(xlabel)}</text>')
    parts.append(f'<text x="12" y="{pad_t+plot_h/2:.0f}" font-size="10" fill="{INK}" text-anchor="middle" transform="rotate(-90 12 {pad_t+plot_h/2:.0f})">{escape(ylabel)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def heat_color(v: float) -> str:
    """0..1 -> vaalea→tumma sininen (neutraali, ei puna/vihreä-politiikkaa)."""
    v = max(0.0, min(1.0, v))
    # interpoloi valkoisesta ACCENTtiin
    r = int(255 + (31 - 255) * v)
    g = int(255 + (78 - 255) * v)
    b = int(255 + (121 - 255) * v)
    return f"rgb({r},{g},{b})"
