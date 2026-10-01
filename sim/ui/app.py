"""スマホ蛍シミュレーション UI (NiceGUI)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
from nicegui import events, ui

from ..io import (
    default_window_ms,
    desk_map,
    experiment_time_range_ms,
    extract_frequencies_windowed,
    freq_map_windowed,
    load_session,
    load_session_bytes,
    make_demo_session,
)
from ..model import (
    analyze_frequencies,
    order_parameter,
    simulate,
    step_once,
    wrap_diff,
    SimConfig,
)
from .plots import (
    GLOW_DURATION_S,
    R_figure,
    histogram_grouped,
    nodes_figure,
    poincare_figure,
    sin_phi_figure,
    tap_raster_figure,
    verify_overlay_figure,
)
from .state import AppState

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "shared" / "sample-session.json"

state = AppState()


def _notify(msg: str, typ: str = "info") -> None:
    ui.notify(msg, type=typ)  # type: ignore[arg-type]


def apply_session(data: dict[str, Any], label: str) -> None:
    state.data = data
    state.source_label = label
    t0, t1 = default_window_ms(data, "experiment1")
    state.window_t0_ms, state.window_t1_ms = t0, t1
    if data.get("experiment2"):
        state.window_t0_exp2_ms, state.window_t1_exp2_ms = default_window_ms(
            data, "experiment2"
        )
    else:
        state.window_t0_exp2_ms, state.window_t1_exp2_ms = 0.0, 1.0
    state.omega_adopted = False
    state.ids = []
    state.omega = np.zeros(0)
    state.natural_hz = np.zeros(0)
    state.xy = np.zeros((0, 2))
    state.adopt_note = "ω 未採用 — 実験確認タブで窓を指定し「ω を採用」してください"
    state.reset_evo_history()
    state.evo_running = False
    refresh_header()
    try:
        _sync_window_sliders()
    except NameError:
        pass
    refresh_review()
    refresh_evo_static()


def adopt_omega_from_review() -> None:
    if state.data is None:
        _notify("先に JSON を読み込んでください", "warning")
        return
    ids, freqs, _stds, xy, warnings = extract_frequencies_windowed(
        state.data,
        "experiment1",
        state.window_t0_ms,
        state.window_t1_ms,
    )
    if not ids:
        _notify("窓内に有効な振動子がありません", "negative")
        return
    state.ids = ids
    state.natural_hz = freqs
    state.omega = 2 * np.pi * freqs
    state.xy = xy
    state.omega_adopted = True
    state.adopt_note = (
        f"採用済: 実験1 窓 {state.window_t0_ms:.0f}–{state.window_t1_ms:.0f} ms / {len(ids)} 人"
    )
    state.ensure_phases()
    state.randomize_evo()
    state.randomize_ana()
    for w in warnings[:8]:
        _notify(w, "warning")
    _notify(f"ω を採用しました（{len(ids)} 振動子）", "positive")
    refresh_header()
    refresh_evo_static()


def require_omega() -> bool:
    if state.omega_adopted and state.n() > 0:
        return True
    _notify("先に実験確認で ω を採用してください", "warning")
    return False


# --- UI element refs (filled in build) ---
header_label: ui.label
adopt_label: ui.label
review_hist: ui.plotly
review_table: ui.table
review_warn: ui.label
review_stats: ui.label
review_nodes: ui.plotly
review_raster: ui.plotly
review_time_label: ui.label
win_range_exp1: ui.range
win_range_exp2: ui.range
win_label_exp1: ui.label
win_label_exp2: ui.label
evo_nodes: ui.plotly
evo_sin: ui.plotly
evo_R: ui.plotly
evo_poincare: ui.plotly
ana_hist: ui.plotly
ana_table: ui.table
ana_R_label: ui.label
verify_plot: ui.plotly
verify_note: ui.markdown


def _review_window() -> tuple[float, float]:
    if state.review_experiment == "experiment1":
        return state.window_t0_ms, state.window_t1_ms
    return state.window_t0_exp2_ms, state.window_t1_exp2_ms


def _rebuild_review_playback() -> None:
    """Rebuild layout / tap events for the current experiment + window."""
    state.review_playing = False
    state.review_paused = False
    state.review_events = []
    state.review_event_i = 0
    state.review_taps = []
    if state.data is None:
        state.review_ids = []
        state.review_xy = np.zeros((0, 2))
        state.review_glow_until = np.zeros(0)
        state.review_t_ms = 0.0
        return

    t0, t1 = _review_window()
    state.review_t_ms = t0
    desks = desk_map(state.data)
    ids: list[str] = []
    xy_list: list[tuple[float, float]] = []
    taps: list[list[float]] = []
    events: list[tuple[float, int]] = []

    for row in state.data.get(state.review_experiment, []):
        desk_id = row["deskId"]
        if desk_id not in desks:
            continue
        all_taps = [float(t) for t in row.get("taps_ms", [])]
        win_taps = [t for t in all_taps if t0 <= t <= t1]
        idx = len(ids)
        ids.append(desk_id)
        xy_list.append(desks[desk_id])
        taps.append(all_taps)
        for t in win_taps:
            events.append((t, idx))

    events.sort(key=lambda e: e[0])
    state.review_ids = ids
    state.review_xy = np.asarray(xy_list, dtype=float) if xy_list else np.zeros((0, 2))
    state.review_taps = taps
    state.review_events = events
    state.review_glow_until = np.zeros(len(ids))
    state.review_event_i = 0
    state.review_last_wall = time.time()


def refresh_header() -> None:
    n = len(state.data.get("desks", [])) if state.data else 0
    header_label.set_text(
        f"読込: {state.source_label}  |  desks={n}  |  session={state.data.get('sessionId') if state.data else '-'}"
    )
    adopt_label.set_text(state.adopt_note)


def refresh_review_viz() -> None:
    t0, t1 = _review_window()
    review_nodes.update_figure(
        nodes_figure(
            state.review_ids,
            state.review_xy,
            state.review_glow_until,
            "実験再生・振動子配置（緑=タップ発光）",
        )
    )
    review_raster.update_figure(
        tap_raster_figure(
            state.review_ids,
            state.review_taps,
            t0,
            t1,
            playhead_ms=state.review_t_ms,
            title="タップ時刻（黄線=再生位置）",
        )
    )
    review_time_label.set_text(
        f"再生時刻: {state.review_t_ms:.0f} ms  "
        f"（窓 {t0:.0f}–{t1:.0f} ms）"
    )


def _freq_stats_text(label: str, freqs: np.ndarray) -> str:
    vals = np.asarray(freqs, dtype=float)
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return f"{label}: データなし"
    mean = float(np.mean(vals))
    std = float(np.std(vals, ddof=1)) if len(vals) >= 2 else 0.0
    return f"{label}: 平均 {mean:.3f} Hz / 標準偏差 {std:.3f} Hz（n={len(vals)}）"


def _sync_window_sliders() -> None:
    """Update range-slider min/max from loaded session spans."""
    if state.data is None:
        return
    r0, r1 = experiment_time_range_ms(state.data, "experiment1")
    step = max(1.0, (r1 - r0) / 200.0)
    win_range_exp1._props["min"] = r0  # noqa: SLF001
    win_range_exp1._props["max"] = r1  # noqa: SLF001
    win_range_exp1._props["step"] = step  # noqa: SLF001
    win_range_exp1.value = {
        "min": float(np.clip(state.window_t0_ms, r0, r1)),
        "max": float(np.clip(state.window_t1_ms, r0, r1)),
    }
    win_range_exp1.update()
    win_label_exp1.set_text(
        f"実験1 窓: {state.window_t0_ms:.0f} – {state.window_t1_ms:.0f} ms"
    )

    if state.data.get("experiment2"):
        e0, e1 = experiment_time_range_ms(state.data, "experiment2")
        step2 = max(1.0, (e1 - e0) / 200.0)
        win_range_exp2._props["min"] = e0  # noqa: SLF001
        win_range_exp2._props["max"] = e1  # noqa: SLF001
        win_range_exp2._props["step"] = step2  # noqa: SLF001
        win_range_exp2.value = {
            "min": float(np.clip(state.window_t0_exp2_ms, e0, e1)),
            "max": float(np.clip(state.window_t1_exp2_ms, e0, e1)),
        }
        win_range_exp2.update()
        win_label_exp2.set_text(
            f"実験2 窓: {state.window_t0_exp2_ms:.0f} – {state.window_t1_exp2_ms:.0f} ms"
        )
    else:
        win_label_exp2.set_text("実験2 窓: （データなし）")


def refresh_review() -> None:
    if state.data is None:
        review_hist.update_figure(histogram_grouped([]))
        review_table.rows = []
        review_warn.set_text("")
        review_stats.set_text("")
        _rebuild_review_playback()
        refresh_review_viz()
        return

    t0, t1 = _review_window()
    ids, freqs, stds, _, warnings = extract_frequencies_windowed(
        state.data, state.review_experiment, t0, t1
    )

    series: list[tuple[str, np.ndarray]] = []
    colors: list[str] = []
    stats_parts: list[str] = []

    if state.review_experiment == "experiment2":
        # Show experiment1 (its own window) in gray beside experiment2
        _, f1, _, _, _ = extract_frequencies_windowed(
            state.data,
            "experiment1",
            state.window_t0_ms,
            state.window_t1_ms,
        )
        if len(f1):
            series.append(("実験1（窓内）", f1))
            colors.append("#9ca3af")  # gray
            stats_parts.append(_freq_stats_text("実験1", f1))
        series.append(("実験2（窓内）", freqs))
        colors.append("#6dffb0")
        stats_parts.append(_freq_stats_text("実験2", freqs))
        title = "実験2 周波数分布（灰色=実験1）"
    else:
        series.append(("実験1（窓内）", freqs))
        colors.append("#2f8f5f")
        stats_parts.append(_freq_stats_text("実験1", freqs))
        title = "実験1 周波数分布（窓内）"

    review_hist.update_figure(histogram_grouped(series, title, colors=colors))
    review_stats.set_text("  |  ".join(stats_parts))
    review_table.rows = [
        {
            "desk": i,
            "hz": f"{f:.3f}",
            "std": f"{s:.3f}",
            "omega": f"{2 * np.pi * f:.3f}",
        }
        for i, f, s in zip(ids, freqs, stds)
    ]
    review_table.update()
    review_warn.set_text(" / ".join(warnings[:12]) if warnings else "問題なし")
    win_label_exp1.set_text(
        f"実験1 窓: {state.window_t0_ms:.0f} – {state.window_t1_ms:.0f} ms"
    )
    win_label_exp2.set_text(
        f"実験2 窓: {state.window_t0_exp2_ms:.0f} – {state.window_t1_exp2_ms:.0f} ms"
    )
    _rebuild_review_playback()
    refresh_review_viz()


def review_tick() -> None:
    if not state.review_playing or state.review_paused or not state.review_ids:
        return
    now = time.time()
    if state.review_last_wall <= 0:
        state.review_last_wall = now
    dt_wall = now - state.review_last_wall
    state.review_last_wall = now
    t0, t1 = _review_window()
    prev = state.review_t_ms
    state.review_t_ms = min(t1, state.review_t_ms + dt_wall * 1000.0 * state.review_speed)

    # Fire glow for taps crossed in this advance
    while (
        state.review_event_i < len(state.review_events)
        and state.review_events[state.review_event_i][0] <= state.review_t_ms
    ):
        t_ev, idx = state.review_events[state.review_event_i]
        if t_ev >= prev:
            state.review_glow_until[idx] = now + GLOW_DURATION_S
        state.review_event_i += 1

    if state.review_t_ms >= t1:
        state.review_playing = False
        state.review_paused = False

    refresh_review_viz()


def refresh_evo_static() -> None:
    evo_nodes.update_figure(
        nodes_figure(state.ids, state.xy, state.glow_until, "振動子配置（緑=発光）")
    )
    evo_sin.update_figure(
        sin_phi_figure(state.hist_t, state.hist_sin, state.ids, state.evo_window_s)
    )
    evo_R.update_figure(R_figure(state.hist_t, state.hist_R, state.evo_window_s))
    evo_poincare.update_figure(
        poincare_figure(state.poincare_n, state.poincare_diff, state.ids)
    )


def evo_tick() -> None:
    if not state.evo_running or state.evo_paused or state.n() == 0:
        return

    # Advance substeps per UI frame according to speed
    n_steps = max(1, int(round(state.evo_speed * 3)))
    for _ in range(n_steps):
        new_phi, crossed = step_once(
            state.phi_evo, state.omega, state.xy, state.a, state.dt, state.method
        )
        state.evo_t += state.dt
        # glow on zero-crossing (wall-clock)
        now = time.time()
        for i in np.where(crossed)[0]:
            state.glow_until[i] = now + GLOW_DURATION_S
        # Poincaré when ID1 crosses
        if crossed[0]:
            state.poincare_count += 1
            diffs = [wrap_diff(float(new_phi[j]), float(new_phi[0])) for j in range(state.n())]
            state.poincare_n.append(state.poincare_count)
            state.poincare_diff.append(diffs)
            # keep last 200 sections
            if len(state.poincare_n) > 200:
                state.poincare_n = state.poincare_n[-200:]
                state.poincare_diff = state.poincare_diff[-200:]
        state.phi_evo = new_phi

    state.hist_t.append(state.evo_t)
    state.hist_sin.append(np.sin(state.phi_evo))
    state.hist_R.append(order_parameter(state.phi_evo))
    # trim history to ~3 windows
    keep_after = state.evo_t - max(state.evo_window_s * 3, 30.0)
    while state.hist_t and state.hist_t[0] < keep_after:
        state.hist_t.pop(0)
        state.hist_sin.pop(0)
        state.hist_R.pop(0)

    refresh_evo_static()


def run_analysis() -> None:
    if not require_omega():
        return
    eff, r_final, _ = analyze_frequencies(
        state.omega,
        state.xy,
        state.phi_ana,
        state.a,
        state.dt,
        state.t_transient,
        state.t_measure,
        state.method,
    )
    series: list[tuple[str, np.ndarray]] = [
        ("自然周波数（採用ω）", state.natural_hz),
        ("シミュレーション実効", eff),
    ]
    exp2_map: dict[str, float] = {}
    if state.data and state.data.get("experiment2"):
        exp2_map = freq_map_windowed(
            state.data,
            "experiment2",
            state.window_t0_exp2_ms,
            state.window_t1_exp2_ms,
        )
        vals = np.array([exp2_map.get(i, np.nan) for i in state.ids], dtype=float)
        series.append(("実験2実測（窓）", vals))

    ana_hist.update_figure(histogram_grouped(series, "分析モード 周波数分布"))
    rows = []
    for i, desk in enumerate(state.ids):
        rows.append(
            {
                "desk": desk,
                "natural": f"{state.natural_hz[i]:.3f}",
                "eff": f"{eff[i]:.3f}" if np.isfinite(eff[i]) else "—",
                "exp2": f"{exp2_map[desk]:.3f}" if desk in exp2_map else "—",
            }
        )
    ana_table.rows = rows
    ana_table.update()
    ana_R_label.set_text(f"計測末 R ≈ {r_final:.3f}  /  a={state.a}")
    _notify("分析完了", "positive")


def run_verify_c1() -> None:
    if not require_omega():
        return
    t_end = 5.0
    phi0 = state.phi_evo.copy() if state.n() else np.zeros(0)
    cfg = SimConfig(a=0.0, dt=state.dt, t_end=t_end, seed=0)
    result = simulate(state.omega, state.xy, cfg, method=state.method, phi0=phi0)
    # Compare first oscillator
    i = 0
    sin_sim = np.sin(result.phi[:, i])
    sin_th = np.sin(phi0[i] + state.omega[i] * result.t)
    verify_plot.update_figure(
        verify_overlay_figure(result.t, sin_sim, sin_th, f"C1 a=0 / {state.ids[i]}")
    )
    err = float(np.max(np.abs(sin_sim - sin_th)))
    verify_note.set_content(
        f"**C1 結合なし**\n\n"
        f"理論: phi_i(t) = phi_i(0) + omega_i * t\n\n"
        f"先頭 `{state.ids[i]}` の sin(phi) 最大誤差 ≈ **{err:.2e}** "
        f"（数値誤差程度なら OK）"
    )


def run_verify_c2() -> None:
    if not require_omega():
        return
    if state.n() < 2:
        _notify("振動子が2つ以上必要です", "warning")
        return
    idx = [0, 1]
    ids = [state.ids[i] for i in idx]
    omega = state.omega[idx]
    xy = state.xy[idx]
    phi0 = state.phi_evo[idx] if len(state.phi_evo) >= 2 else np.random.uniform(0, 2 * np.pi, 2)
    dist = float(np.linalg.norm(xy[0] - xy[1]))
    coup = state.a / dist if dist > 0 else 0.0
    d_omega = abs(float(omega[0] - omega[1]))
    cfg = SimConfig(a=state.a, dt=state.dt, t_end=20.0, seed=0)
    result = simulate(omega, xy, cfg, method=state.method, phi0=phi0)
    # Phase difference over time (not Poincaré) for clarity
    dphi = np.mod(result.phi[:, 1] - result.phi[:, 0], 2 * np.pi)
    fig = verify_overlay_figure(
        result.t,
        np.sin(result.phi[:, 0]),
        np.sin(result.phi[:, 1]),
        f"C2 2振動子 {ids[0]} & {ids[1]}",
    )
    verify_plot.update_figure(fig)
    lock = "同期しやすい" if coup > d_omega else "ドリフトしやすい（結合が周波数差より小さい）"
    verify_note.set_content(
        f"**C2 2振動子結合**\n\n"
        f"- 選出: `{ids[0]}`, `{ids[1]}`\n"
        f"- 距離 r ≈ {dist:.2f} m → 結合 a/r ≈ **{coup:.3f}**\n"
        f"- |ω₁−ω₂| ≈ **{d_omega:.3f}** rad/s\n"
        f"- 目安: a/r ≳ |Δω| なら位相差が引き込みやすい → 今は **{lock}**\n\n"
        f"上図は両振動子の sin(phi)。重なってくれば同期の兆候です。"
        f"（位相差の最終付近 mean≈{float(np.mean(dphi[-100:])):.2f} rad）"
    )


def build() -> None:
    global header_label, adopt_label
    global review_hist, review_table, review_warn, review_stats
    global review_nodes, review_raster, review_time_label
    global win_range_exp1, win_range_exp2, win_label_exp1, win_label_exp2
    global evo_nodes, evo_sin, evo_R, evo_poincare
    global ana_hist, ana_table, ana_R_label
    global verify_plot, verify_note

    ui.dark_mode().enable()
    ui.colors(primary="#2f8f5f", secondary="#6dffb0")

    with ui.header().classes("items-center justify-between"):
        ui.label("スマホ蛍シミュレーション").classes("text-h5")
        header_label = ui.label("読込: 未読込").classes("text-caption")

    with ui.row().classes("w-full items-end q-gutter-md"):
        async def on_upload(e: events.UploadEventArguments) -> None:
            content = await e.file.read()
            try:
                data = load_session_bytes(content)
                apply_session(data, e.file.name or "upload.json")
                _notify("JSON を読み込みました", "positive")
            except Exception as ex:  # noqa: BLE001
                _notify(f"読込失敗: {ex}", "negative")

        ui.upload(label="セッション JSON", on_upload=on_upload, auto_upload=True).props(
            "accept=.json"
        ).classes("w-64")

        def load_demo() -> None:
            data = make_demo_session()
            SAMPLE.parent.mkdir(parents=True, exist_ok=True)
            SAMPLE.write_text(
                __import__("json").dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            apply_session(data, "DEMO（内蔵）")
            _notify("デモデータを読み込みました", "positive")

        def load_sample_file() -> None:
            if SAMPLE.exists():
                apply_session(load_session(SAMPLE), str(SAMPLE.name))
                _notify("sample-session.json を読み込みました", "positive")
            else:
                load_demo()

        ui.button("デモデータ", on_click=load_demo)
        ui.button("sample 読込", on_click=load_sample_file)

        with ui.column():
            ui.label("結合強度 a")
            a_slider = ui.slider(min=0, max=2, step=0.01, value=state.a).props("label")
            a_slider.bind_value(state, "a")

        with ui.column():
            ui.label("dt")
            ui.number(value=state.dt, format="%.3f", step=0.001).bind_value(state, "dt").classes(
                "w-28"
            )

        method = ui.select(["rk4", "euler"], value=state.method, label="積分法")
        method.bind_value(state, "method")

    adopt_label = ui.label(state.adopt_note).classes("text-secondary")

    with ui.tabs().classes("w-full") as tabs:
        tab_review = ui.tab("実験確認")
        tab_evo = ui.tab("時間発展")
        tab_ana = ui.tab("分析")
        tab_ver = ui.tab("検証")

    with ui.tab_panels(tabs, value=tab_review).classes("w-full"):
        # ----- Review -----
        with ui.tab_panel(tab_review):
            with ui.row().classes("items-center q-gutter-md"):
                exp_sel = ui.toggle(
                    {"experiment1": "実験1", "experiment2": "実験2"},
                    value="experiment1",
                ).bind_value(state, "review_experiment")
                exp_sel.on_value_change(lambda _: refresh_review())
                ui.button("再計算", on_click=refresh_review)
                ui.button("この窓で ω を採用（実験1）", on_click=adopt_omega_from_review).props(
                    "primary"
                )

            def on_win1(e) -> None:
                if not e.value:
                    return
                lo, hi = float(e.value["min"]), float(e.value["max"])
                if lo > hi:
                    lo, hi = hi, lo
                state.window_t0_ms, state.window_t1_ms = lo, hi
                refresh_review()

            def on_win2(e) -> None:
                if not e.value:
                    return
                lo, hi = float(e.value["min"]), float(e.value["max"])
                if lo > hi:
                    lo, hi = hi, lo
                state.window_t0_exp2_ms, state.window_t1_exp2_ms = lo, hi
                refresh_review()

            win_label_exp1 = ui.label("実験1 窓: —")
            win_range_exp1 = ui.range(
                min=0,
                max=15000,
                step=50,
                value={"min": state.window_t0_ms, "max": state.window_t1_ms},
                on_change=on_win1,
            ).classes("w-full")
            win_label_exp2 = ui.label("実験2 窓: —")
            win_range_exp2 = ui.range(
                min=0,
                max=15000,
                step=50,
                value={"min": state.window_t0_exp2_ms, "max": state.window_t1_exp2_ms},
                on_change=on_win2,
            ).classes("w-full")

            review_stats = ui.label("").classes("text-subtitle2")
            review_warn = ui.label("")
            with ui.row().classes("w-full"):
                review_hist = ui.plotly(histogram_grouped([])).classes("w-1/2")
                review_table = ui.table(
                    columns=[
                        {"name": "desk", "label": "机", "field": "desk"},
                        {"name": "hz", "label": "平均 f (Hz)", "field": "hz"},
                        {"name": "std", "label": "標準偏差 (Hz)", "field": "std"},
                        {"name": "omega", "label": "ω", "field": "omega"},
                    ],
                    rows=[],
                    row_key="desk",
                ).classes("w-1/2")

            ui.separator()
            ui.label("実験データ再生（振動子配置・タップ発光・時系列）").classes("text-subtitle1")
            with ui.row().classes("items-center q-gutter-sm"):
                def start_review() -> None:
                    if not state.review_ids:
                        _notify("先に JSON を読み込んでください", "warning")
                        return
                    t0, _ = _review_window()
                    if state.review_t_ms >= _review_window()[1] - 1:
                        state.review_t_ms = t0
                        state.review_event_i = 0
                        state.review_glow_until = np.zeros(len(state.review_ids))
                    state.review_playing = True
                    state.review_paused = False
                    state.review_last_wall = time.time()

                ui.button("再生", on_click=start_review).props("primary")
                ui.button(
                    "一時停止",
                    on_click=lambda: setattr(state, "review_paused", not state.review_paused),
                )
                ui.button(
                    "停止/先頭へ",
                    on_click=lambda: (
                        setattr(state, "review_playing", False),
                        setattr(state, "review_paused", False),
                        setattr(state, "review_t_ms", _review_window()[0]),
                        setattr(state, "review_event_i", 0),
                        setattr(
                            state,
                            "review_glow_until",
                            np.zeros(len(state.review_ids)),
                        ),
                        refresh_review_viz(),
                    ),
                )
                with ui.column():
                    ui.label("再生速度")
                    ui.slider(min=0.25, max=10, step=0.25, value=state.review_speed).bind_value(
                        state, "review_speed"
                    ).props("label")
                review_time_label = ui.label("再生時刻: —")

            with ui.row().classes("w-full"):
                review_nodes = ui.plotly(
                    nodes_figure([], np.zeros((0, 2)), np.zeros(0))
                ).classes("w-1/2")
                review_raster = ui.plotly(
                    tap_raster_figure([], [], 0, 1)
                ).classes("w-1/2")

            ui.timer(0.05, review_tick)

        # ----- Evolution -----
        with ui.tab_panel(tab_evo):
            with ui.row().classes("items-center q-gutter-sm"):
                def start_evo() -> None:
                    if not require_omega():
                        return
                    state.evo_running = True
                    state.evo_paused = False
                    if not state.hist_t:
                        state.hist_t.append(state.evo_t)
                        state.hist_sin.append(np.sin(state.phi_evo))
                        state.hist_R.append(order_parameter(state.phi_evo))

                ui.button("開始", on_click=start_evo).props("primary")
                ui.button(
                    "一時停止",
                    on_click=lambda: setattr(state, "evo_paused", not state.evo_paused),
                )
                ui.button(
                    "停止",
                    on_click=lambda: (
                        setattr(state, "evo_running", False),
                        setattr(state, "evo_paused", False),
                    ),
                )
                ui.button(
                    "初期位相ランダム化",
                    on_click=lambda: (
                        state.randomize_evo(),
                        refresh_evo_static(),
                        _notify("初期位相をランダム化しました"),
                    ),
                )
                with ui.column():
                    ui.label("速度")
                    ui.slider(min=0.25, max=10, step=0.25, value=state.evo_speed).bind_value(
                        state, "evo_speed"
                    ).props("label")
                with ui.column():
                    ui.label("表示時間幅 (s)")
                    ui.number(value=state.evo_window_s, format="%.1f", step=0.5).bind_value(
                        state, "evo_window_s"
                    ).classes("w-28")

            ui.label(
                f"a は上部スライダーで実行中も即反映。発光は位相ゼロ通過から実時間 {GLOW_DURATION_S} 秒。"
            )

            with ui.row().classes("w-full"):
                evo_nodes = ui.plotly(
                    nodes_figure([], np.zeros((0, 2)), np.zeros(0))
                ).classes("w-1/2")
                with ui.column().classes("w-1/2"):
                    evo_sin = ui.plotly(sin_phi_figure([], [], [], 10))
                    evo_R = ui.plotly(R_figure([], [], 10))
            evo_poincare = ui.plotly(poincare_figure([], [], []))

            ui.timer(0.05, evo_tick)

        # ----- Analysis -----
        with ui.tab_panel(tab_ana):
            with ui.row().classes("items-center q-gutter-md"):
                ui.number(label="過渡時間 T_transient (s)", value=state.t_transient).bind_value(
                    state, "t_transient"
                ).classes("w-40")
                ui.number(label="計測時間 T_measure (s)", value=state.t_measure).bind_value(
                    state, "t_measure"
                ).classes("w-40")
                ui.button(
                    "初期位相ランダム化",
                    on_click=lambda: (
                        state.randomize_ana(),
                        _notify("分析用初期位相をランダム化"),
                    ),
                )
                ui.button("分析を実行", on_click=run_analysis).classes("primary")
            ana_R_label = ui.label("")
            with ui.row().classes("w-full"):
                ana_hist = ui.plotly(histogram_grouped([])).classes("w-1/2")
                ana_table = ui.table(
                    columns=[
                        {"name": "desk", "label": "机", "field": "desk"},
                        {"name": "natural", "label": "自然 f", "field": "natural"},
                        {"name": "eff", "label": "実効 f", "field": "eff"},
                        {"name": "exp2", "label": "実験2 f", "field": "exp2"},
                    ],
                    rows=[],
                    row_key="desk",
                ).classes("w-1/2")

        # ----- Verify -----
        with ui.tab_panel(tab_ver):
            ui.markdown(
                "段階的に正しさを確認します。**C1（結合なし）→ C2（2振動子）** の順を推奨。"
            )
            with ui.row().classes("q-gutter-md"):
                ui.button("C1 実行 (a=0 vs 理論)", on_click=run_verify_c1).classes("primary")
                ui.button("C2 実行 (2振動子結合)", on_click=run_verify_c2)
            verify_plot = ui.plotly(
                verify_overlay_figure(np.array([0]), np.array([0]), np.array([0]), "—")
            )
            verify_note = ui.markdown("まだ実行していません。")

    # Auto-load sample if present
    if SAMPLE.exists():
        try:
            apply_session(load_session(SAMPLE), SAMPLE.name)
        except Exception:  # noqa: BLE001
            pass


def main() -> None:
    import os

    show = os.environ.get("HOTARU_UI_SHOW", "1") != "0"
    port = int(os.environ.get("HOTARU_UI_PORT", "8089"))
    ui.run(
        root=build,
        title="スマホ蛍シミュレーション",
        reload=False,
        show=show,
        port=port,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
