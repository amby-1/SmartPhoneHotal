"""Plotly figure helpers for the simulation UI."""

from __future__ import annotations

import time

import numpy as np
import plotly.graph_objects as go

from ..model import display_positions, order_parameter

FIREFLY_DIM = "#1a3d2a"
FIREFLY_GLOW = "#6dffb0"
FIREFLY_CORE = "#c8ffe0"
GLOW_DURATION_S = 0.1


def empty_fig(title: str = "") -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=title,
        margin=dict(l=40, r=20, t=40, b=40),
        height=320,
        template="plotly_dark",
        paper_bgcolor="#0b1a14",
        plot_bgcolor="#0b1a14",
        font=dict(color="#e8f5ee"),
    )
    return fig


def histogram_grouped(
    series: list[tuple[str, np.ndarray]],
    title: str = "周波数分布",
    bin_width: float = 0.1,
    colors: list[str] | None = None,
) -> go.Figure:
    """Side-by-side bars at shared frequency bins (not overlaid)."""
    fig = empty_fig(title)
    default_colors = ["#2f8f5f", "#6dffb0", "#f0c674", "#8ab4f8"]
    palette = colors if colors else default_colors
    cleaned: list[tuple[str, np.ndarray]] = []
    for name, values in series:
        vals = np.asarray(values, dtype=float)
        vals = vals[np.isfinite(vals)]
        if len(vals):
            cleaned.append((name, vals))
    if not cleaned:
        fig.add_annotation(text="データなし", showarrow=False)
        return fig

    lo = min(float(np.min(v)) for _, v in cleaned)
    hi = max(float(np.max(v)) for _, v in cleaned)
    if hi <= lo:
        hi = lo + bin_width
    edges = np.arange(lo - bin_width / 2, hi + bin_width, bin_width)
    if len(edges) < 2:
        edges = np.array([lo - bin_width / 2, lo + bin_width / 2])
    centers = 0.5 * (edges[:-1] + edges[1:])
    # categorical labels keep bars aligned across series
    labels = [f"{c:.2f}" for c in centers]

    for i, (name, vals) in enumerate(cleaned):
        counts, _ = np.histogram(vals, bins=edges)
        fig.add_trace(
            go.Bar(
                x=labels,
                y=counts,
                name=name,
                marker_color=palette[i % len(palette)],
            )
        )
    fig.update_layout(
        barmode="group",
        xaxis_title="周波数 (Hz)",
        yaxis_title="人数",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def nodes_figure(
    ids: list[str],
    xy: np.ndarray,
    glow_until: np.ndarray,
    title: str = "振動子配置",
) -> go.Figure:
    fig = empty_fig(title)
    if len(ids) == 0:
        fig.add_annotation(text="データ未読込", showarrow=False)
        return fig
    pos = display_positions(xy)
    now = time.time()
    glowing = (
        now < glow_until
        if len(glow_until) == len(ids)
        else np.zeros(len(ids), dtype=bool)
    )
    colors = [FIREFLY_GLOW if g else FIREFLY_DIM for g in glowing]
    # Smaller markers when the class is large
    base = 12 if len(ids) > 30 else 14
    glow_size = base + 6
    sizes = [glow_size if g else base for g in glowing]
    fig.add_trace(
        go.Scatter(
            x=pos[:, 0],
            y=pos[:, 1],
            mode="markers+text",
            text=ids,
            textposition="top center",
            textfont=dict(size=9 if len(ids) > 30 else 11),
            marker=dict(size=sizes, color=colors, line=dict(width=1, color=FIREFLY_CORE)),
            hovertext=[f"{i}: glow" if g else i for i, g in zip(ids, glowing)],
            hoverinfo="text",
            showlegend=False,
        )
    )
    # Classroom view: +y grows "up the room" in data, but draw with +y downward
    # (row 1 near top of screen) by reversing the axis.
    fig.update_yaxes(scaleanchor="x", scaleratio=1, autorange="reversed")
    fig.update_layout(
        xaxis_title="x (m)",
        yaxis_title="y (m)（上が小・下が大）",
        height=420 if len(ids) > 30 else 360,
    )
    return fig


def tap_raster_figure(
    ids: list[str],
    taps_ms: list[list[float]],
    t0_ms: float,
    t1_ms: float,
    playhead_ms: float | None = None,
    title: str = "タップ時刻（時系列）",
) -> go.Figure:
    """Raster / spike plot of tap times per desk."""
    fig = empty_fig(title)
    if not ids:
        fig.add_annotation(text="データなし", showarrow=False)
        return fig

    for i, desk in enumerate(ids):
        ts = [t / 1000.0 for t in taps_ms[i] if t0_ms <= t <= t1_ms]
        if not ts:
            continue
        fig.add_trace(
            go.Scatter(
                x=ts,
                y=[i] * len(ts),
                mode="markers",
                name=desk,
                marker=dict(size=8, color=FIREFLY_GLOW, symbol="line-ns-open"),
                showlegend=False,
            )
        )

    if playhead_ms is not None:
        t_s = playhead_ms / 1000.0
        fig.add_vline(x=t_s, line_width=2, line_color="#f0c674")

    fig.update_layout(
        xaxis_title="時刻 (s)",
        yaxis=dict(
            tickmode="array",
            tickvals=list(range(len(ids))),
            ticktext=ids,
            title="机",
            autorange="reversed",
        ),
        height=max(280, 28 * len(ids) + 80),
    )
    fig.update_xaxes(range=[t0_ms / 1000.0, t1_ms / 1000.0])
    return fig


def sin_phi_figure(
    hist_t: list[float],
    hist_sin: list[np.ndarray],
    ids: list[str],
    window_s: float,
    max_series: int = 12,
) -> go.Figure:
    fig = empty_fig("sin φ(t)")
    if not hist_t or not hist_sin:
        fig.add_annotation(text="開始すると波形が表示されます", showarrow=False)
        return fig
    t = np.asarray(hist_t)
    t_max = float(t[-1])
    t_min = t_max - window_s
    mask = t >= t_min
    t_plot = t[mask]
    n = hist_sin[0].shape[0]
    show_n = min(n, max_series)
    for i in range(show_n):
        y = np.array([row[i] for row in hist_sin], dtype=float)[mask]
        fig.add_trace(
            go.Scatter(x=t_plot, y=y, mode="lines", name=ids[i], line=dict(width=1.5))
        )
    if n > max_series:
        fig.update_layout(title=f"sin φ(t)（先頭 {max_series}/{n} 本）")
    fig.update_layout(xaxis_title="t (s)", yaxis_title="sin φ", height=300)
    return fig


def R_figure(hist_t: list[float], hist_R: list[float], window_s: float) -> go.Figure:
    fig = empty_fig("秩序パラメータ R(t)")
    if not hist_t:
        fig.add_annotation(text="—", showarrow=False)
        return fig
    t = np.asarray(hist_t)
    r = np.asarray(hist_R)
    t_max = float(t[-1])
    mask = t >= t_max - window_s
    fig.add_trace(go.Scatter(x=t[mask], y=r[mask], mode="lines", line=dict(color=FIREFLY_GLOW)))
    fig.update_layout(
        xaxis_title="t (s)",
        yaxis_title="R",
        yaxis=dict(range=[0, 1.05]),
        height=260,
    )
    return fig


def poincare_figure(
    poincare_n: list[int],
    poincare_diff: list[list[float]],
    ids: list[str],
    max_series: int = 8,
) -> go.Figure:
    fig = empty_fig("ポアンカレ位相差（ID1 断面）")
    if not poincare_n or len(ids) < 2:
        fig.add_annotation(text="ID1 が位相ゼロを通過すると記録されます", showarrow=False)
        return fig
    n_osc = len(poincare_diff[0])
    show = min(n_osc, max_series)
    for j in range(1, show):
        ys = [row[j] for row in poincare_diff]
        fig.add_trace(
            go.Scatter(
                x=poincare_n,
                y=ys,
                mode="markers+lines",
                name=f"{ids[j]}−{ids[0]}",
                marker=dict(size=6),
            )
        )
    fig.update_layout(
        xaxis_title="断面番号",
        yaxis_title="Δφ ∈ [0, 2π)",
        yaxis=dict(range=[0, 2 * np.pi]),
        height=300,
    )
    return fig


def verify_overlay_figure(
    t: np.ndarray,
    sin_sim: np.ndarray,
    sin_theory: np.ndarray,
    label: str,
) -> go.Figure:
    fig = empty_fig(f"検証: {label}")
    fig.add_trace(go.Scatter(x=t, y=sin_sim, mode="lines", name="シミュレーション"))
    fig.add_trace(
        go.Scatter(x=t, y=sin_theory, mode="lines", name="理論", line=dict(dash="dash"))
    )
    fig.update_layout(xaxis_title="t (s)", yaxis_title="sin φ", height=320)
    return fig


def current_R(phi: np.ndarray) -> float:
    return order_parameter(phi) if len(phi) else 0.0
