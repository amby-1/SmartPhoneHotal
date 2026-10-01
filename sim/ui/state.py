"""Shared session / simulation state for the NiceGUI app."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class AppState:
    data: dict[str, Any] | None = None
    source_label: str = "未読込"

    # Windowed experiment review (ms)
    review_experiment: str = "experiment1"
    window_t0_ms: float = 0.0
    window_t1_ms: float = 10000.0
    window_t0_exp2_ms: float = 0.0
    window_t1_exp2_ms: float = 10000.0

    # Adopted ω for simulation
    ids: list[str] = field(default_factory=list)
    xy: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    omega: np.ndarray = field(default_factory=lambda: np.zeros(0))
    natural_hz: np.ndarray = field(default_factory=lambda: np.zeros(0))
    omega_adopted: bool = False
    adopt_note: str = "ω 未採用（実験確認で窓を指定して採用してください）"

    # Common params
    a: float = 1.0
    dt: float = 0.01
    method: str = "rk4"

    # Independent initial phases
    phi_evo: np.ndarray = field(default_factory=lambda: np.zeros(0))
    phi_ana: np.ndarray = field(default_factory=lambda: np.zeros(0))

    # Evolution runtime
    evo_running: bool = False
    evo_paused: bool = False
    evo_t: float = 0.0
    evo_speed: float = 1.0
    evo_window_s: float = 10.0
    glow_until: np.ndarray = field(default_factory=lambda: np.zeros(0))
    hist_t: list[float] = field(default_factory=list)
    hist_sin: list[np.ndarray] = field(default_factory=list)
    hist_R: list[float] = field(default_factory=list)
    poincare_n: list[int] = field(default_factory=list)
    poincare_diff: list[list[float]] = field(default_factory=list)
    poincare_count: int = 0

    # Analysis
    t_transient: float = 20.0
    t_measure: float = 10.0

    # Experiment review playback
    review_playing: bool = False
    review_paused: bool = False
    review_t_ms: float = 0.0
    review_speed: float = 1.0
    review_ids: list[str] = field(default_factory=list)
    review_xy: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    review_glow_until: np.ndarray = field(default_factory=lambda: np.zeros(0))
    review_taps: list[list[float]] = field(default_factory=list)
    review_events: list[tuple[float, int]] = field(default_factory=list)
    review_event_i: int = 0
    review_last_wall: float = 0.0

    def n(self) -> int:
        return len(self.ids)

    def ensure_phases(self, rng: np.random.Generator | None = None) -> None:
        n = self.n()
        if n == 0:
            self.phi_evo = np.zeros(0)
            self.phi_ana = np.zeros(0)
            self.glow_until = np.zeros(0)
            return
        rng = rng or np.random.default_rng()
        if len(self.phi_evo) != n:
            self.phi_evo = rng.uniform(0, 2 * np.pi, size=n)
        if len(self.phi_ana) != n:
            self.phi_ana = rng.uniform(0, 2 * np.pi, size=n)
        if len(self.glow_until) != n:
            self.glow_until = np.zeros(n)

    def randomize_evo(self, seed: int | None = None) -> None:
        rng = np.random.default_rng(seed)
        n = self.n()
        self.phi_evo = rng.uniform(0, 2 * np.pi, size=n) if n else np.zeros(0)
        self.reset_evo_history()

    def randomize_ana(self, seed: int | None = None) -> None:
        rng = np.random.default_rng(seed)
        n = self.n()
        self.phi_ana = rng.uniform(0, 2 * np.pi, size=n) if n else np.zeros(0)

    def reset_evo_history(self) -> None:
        self.evo_t = 0.0
        self.hist_t.clear()
        self.hist_sin.clear()
        self.hist_R.clear()
        self.poincare_n.clear()
        self.poincare_diff.clear()
        self.poincare_count = 0
        self.glow_until = np.zeros(self.n())
