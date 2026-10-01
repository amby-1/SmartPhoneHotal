"""Load exported スマホ蛍 JSON and derive ω_i, positions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from .model import frequency_stats_in_window_ms


def load_session(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_session_bytes(data: bytes) -> dict[str, Any]:
    return json.loads(data.decode("utf-8"))


def desk_map(data: dict[str, Any]) -> dict[str, tuple[float, float]]:
    return {d["id"]: (float(d["x"]), float(d["y"])) for d in data.get("desks", [])}


def experiment_time_range_ms(data: dict[str, Any], experiment: str) -> tuple[float, float]:
    taps: list[float] = []
    for row in data.get(experiment, []):
        taps.extend(row.get("taps_ms", []))
    if not taps:
        return 0.0, 1000.0
    return float(min(taps)), float(max(taps))


def default_window_ms(data: dict[str, Any], experiment: str) -> tuple[float, float]:
    """Latter half of the recorded span (skip early transient)."""
    t0, t1 = experiment_time_range_ms(data, experiment)
    if t1 <= t0:
        return t0, t1
    mid = t0 + 0.5 * (t1 - t0)
    return mid, t1


def extract_frequencies_windowed(
    data: dict[str, Any],
    experiment: str,
    t0_ms: float,
    t1_ms: float,
) -> tuple[list[str], np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Return ids, mean f_hz, std f_hz, xy, and warnings for skipped desks."""
    desks = desk_map(data)
    ids: list[str] = []
    freqs: list[float] = []
    stds: list[float] = []
    xy_list: list[tuple[float, float]] = []
    warnings: list[str] = []

    for row in data.get(experiment, []):
        desk_id = row["deskId"]
        if desk_id not in desks:
            warnings.append(f"{desk_id}: 座標なし")
            continue
        stats = frequency_stats_in_window_ms(row.get("taps_ms", []), t0_ms, t1_ms)
        if stats is None:
            warnings.append(f"{desk_id}: 窓内タップ不足")
            continue
        hz, std = stats
        ids.append(desk_id)
        freqs.append(hz)
        stds.append(std)
        xy_list.append(desks[desk_id])

    return (
        ids,
        np.asarray(freqs, dtype=float),
        np.asarray(stds, dtype=float),
        np.asarray(xy_list, dtype=float),
        warnings,
    )


def extract_omega_and_xy(
    data: dict[str, Any],
    source_experiment: str = "experiment1",
    t0_ms: float | None = None,
    t1_ms: float | None = None,
) -> tuple[list[str], np.ndarray, np.ndarray]:
    """Build ω_i = 2π f_i from taps (optionally windowed) and desk coordinates."""
    if t0_ms is None or t1_ms is None:
        t0_ms, t1_ms = experiment_time_range_ms(data, source_experiment)
    ids, freqs, _stds, xy, _ = extract_frequencies_windowed(
        data, source_experiment, t0_ms, t1_ms
    )
    if not ids:
        raise ValueError(
            f"No usable oscillators from {source_experiment}. "
            "Need ≥2 taps per desk inside the window and matching coordinates."
        )
    return ids, 2 * np.pi * freqs, xy


def freq_map_windowed(
    data: dict[str, Any],
    experiment: str,
    t0_ms: float,
    t1_ms: float,
) -> dict[str, float]:
    ids, freqs, _stds, _, _ = extract_frequencies_windowed(
        data, experiment, t0_ms, t1_ms
    )
    return dict(zip(ids, freqs.tolist()))


def _col_letters(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA."""
    n = index
    letters = ""
    while True:
        letters = chr(ord("A") + n % 26) + letters
        n = n // 26 - 1
        if n < 0:
            break
    return letters


def make_demo_session(n_cols: int = 10, n_rows: int = 5, seed: int = 1) -> dict[str, Any]:
    """Synthetic classroom matching lecture geometry (2 m desk grid).

    Default 10×5 = 50 seats (typical class size).
    """
    rng = np.random.default_rng(seed)
    desks = []
    exp1 = []
    exp2 = []
    natural = []
    for r in range(1, n_rows + 1):
        for c in range(n_cols):
            desk_id = f"{_col_letters(c)}{r}"
            x, y = c * 2.0, (r - 1) * 2.0
            desks.append({"id": desk_id, "x": x, "y": y})
            hz = float(rng.uniform(1.5, 2.5))
            natural.append(hz)
            period_ms = 1000.0 / hz
            taps1 = [k * period_ms + float(rng.normal(0, 8)) for k in range(30)]
            exp1.append({"deskId": desk_id, "taps_ms": taps1})

    # Experiment2: after ~5s, converge toward mean frequency
    mean_hz = float(np.mean(natural))
    for i, desk in enumerate(desks):
        hz0 = natural[i]
        taps2: list[float] = []
        t = float(rng.uniform(0, 50))
        while t < 15000:
            blend = min(1.0, max(0.0, (t - 5000) / 5000))
            hz = (1 - blend) * hz0 + blend * mean_hz
            taps2.append(t)
            t += 1000.0 / hz + float(rng.normal(0, 5))
        exp2.append({"deskId": desk["id"], "taps_ms": taps2})

    return {
        "sessionId": "DEMO50",
        "createdAt": "2026-01-01T00:00:00Z",
        "desks": desks,
        "experiment1": exp1,
        "experiment2": exp2,
        "meta": {
            "volumeExperiment1": 0.05,
            "volumeExperiment2": 1.0,
            "note": f"synthetic demo ({n_cols}x{n_rows}={n_cols * n_rows} seats)",
        },
    }
