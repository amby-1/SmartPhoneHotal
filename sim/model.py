"""Phase-oscillator (Kuramoto-like) simulation for スマホ蛍.

Model (lecture notes):
  dφ_i/dt = ω_i + Σ_j a_ij sin(φ_j - φ_i)
  a_ij = a / r_ij
  φ = 0 corresponds to a tap.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class SimConfig:
    a: float = 1.0
    dt: float = 0.01
    t_end: float = 30.0
    seed: int = 0


def pairwise_distances(xy: np.ndarray) -> np.ndarray:
    """Return NxN distance matrix with large diagonal to avoid self-coupling."""
    diff = xy[:, None, :] - xy[None, :, :]
    dist = np.linalg.norm(diff, axis=-1)
    np.fill_diagonal(dist, np.inf)
    return dist


def coupling_matrix(xy: np.ndarray, a: float) -> np.ndarray:
    dist = pairwise_distances(xy)
    with np.errstate(divide="ignore"):
        mat = a / dist
    mat[~np.isfinite(mat)] = 0.0
    return mat


def rhs(phi: np.ndarray, omega: np.ndarray, aij: np.ndarray) -> np.ndarray:
    delta = phi[None, :] - phi[:, None]
    return omega + np.sum(aij * np.sin(delta), axis=1)


def rk4_step(phi: np.ndarray, omega: np.ndarray, aij: np.ndarray, dt: float) -> np.ndarray:
    k1 = rhs(phi, omega, aij)
    k2 = rhs(phi + 0.5 * dt * k1, omega, aij)
    k3 = rhs(phi + 0.5 * dt * k2, omega, aij)
    k4 = rhs(phi + dt * k3, omega, aij)
    return phi + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)


def euler_step(phi: np.ndarray, omega: np.ndarray, aij: np.ndarray, dt: float) -> np.ndarray:
    return phi + dt * rhs(phi, omega, aij)


def wrap(phi: np.ndarray) -> np.ndarray:
    return np.mod(phi, 2 * np.pi)


def order_parameter(phi: np.ndarray) -> float:
    """Kuramoto order parameter R = |⟨e^{iφ}⟩|."""
    return float(np.abs(np.mean(np.exp(1j * phi))))


def phase_cross_zero(prev: np.ndarray, phi: np.ndarray) -> np.ndarray:
    """Boolean mask: wrapped across 0 between prev and phi."""
    return (prev > 1.5 * np.pi) & (phi < 0.5 * np.pi)


def step_once(
    phi: np.ndarray,
    omega: np.ndarray,
    xy: np.ndarray,
    a: float,
    dt: float,
    method: str = "rk4",
) -> tuple[np.ndarray, np.ndarray]:
    """Advance one step. Returns (new_phi, crossed_zero_mask)."""
    aij = coupling_matrix(xy, a)
    step_fn = rk4_step if method == "rk4" else euler_step
    prev = phi
    new_phi = wrap(step_fn(phi, omega, aij, dt))
    return new_phi, phase_cross_zero(prev, new_phi)


def display_positions(xy: np.ndarray, min_sep: float = 0.35) -> np.ndarray:
    """Jitter near-duplicate coordinates so nodes do not overlap on the plot."""
    out = np.asarray(xy, dtype=float).copy()
    n = len(out)
    if n == 0:
        return out
    for i in range(n):
        for j in range(i):
            d = np.linalg.norm(out[i] - out[j])
            if d < min_sep:
                angle = (i * 2.4 + j) % (2 * np.pi)
                out[i] = out[j] + min_sep * np.array([np.cos(angle), np.sin(angle)])
    return out


def wrap_diff(phi_j: float, phi_ref: float) -> float:
    """(φ_j - φ_ref) wrapped into [0, 2π)."""
    return float(np.mod(phi_j - phi_ref, 2 * np.pi))


@dataclass
class SimResult:
    t: np.ndarray
    phi: np.ndarray
    R: np.ndarray
    tap_times: list[list[float]]
    effective_hz: np.ndarray


def simulate(
    omega: np.ndarray,
    xy: np.ndarray,
    config: SimConfig,
    method: str = "rk4",
    phi0: np.ndarray | None = None,
) -> SimResult:
    rng = np.random.default_rng(config.seed)
    n = len(omega)
    phi = (
        np.asarray(phi0, dtype=float).copy()
        if phi0 is not None
        else rng.uniform(0, 2 * np.pi, size=n)
    )
    aij = coupling_matrix(xy, config.a)

    steps = int(config.t_end / config.dt)
    t = np.linspace(0.0, steps * config.dt, steps + 1)
    traj = np.zeros((steps + 1, n))
    R = np.zeros(steps + 1)
    traj[0] = phi
    R[0] = order_parameter(phi)

    step_fn = rk4_step if method == "rk4" else euler_step
    prev = phi.copy()
    tap_times: list[list[float]] = [[] for _ in range(n)]

    for k in range(1, steps + 1):
        phi = wrap(step_fn(phi, omega, aij, config.dt))
        traj[k] = phi
        R[k] = order_parameter(phi)
        crossed = phase_cross_zero(prev, phi)
        for i in np.where(crossed)[0]:
            tap_times[int(i)].append(float(t[k]))
        prev = phi

    effective_hz = effective_hz_from_taps(tap_times)
    return SimResult(t=t, phi=traj, R=R, tap_times=tap_times, effective_hz=effective_hz)


def effective_hz_from_taps(tap_times: list[list[float]]) -> np.ndarray:
    return np.array(
        [
            (len(ts) - 1) / (ts[-1] - ts[0]) if len(ts) >= 2 else np.nan
            for ts in tap_times
        ]
    )


def analyze_frequencies(
    omega: np.ndarray,
    xy: np.ndarray,
    phi0: np.ndarray,
    a: float,
    dt: float,
    t_transient: float,
    t_measure: float,
    method: str = "rk4",
) -> tuple[np.ndarray, float, list[list[float]]]:
    """Run transient then measure; return (effective_hz, R_final, tap_times)."""
    aij = coupling_matrix(xy, a)
    step_fn = rk4_step if method == "rk4" else euler_step
    phi = np.asarray(phi0, dtype=float).copy()
    prev = phi.copy()

    steps_tr = max(0, int(t_transient / dt))
    for _ in range(steps_tr):
        phi = wrap(step_fn(phi, omega, aij, dt))
        prev = phi

    tap_times: list[list[float]] = [[] for _ in range(len(omega))]
    steps_m = max(1, int(t_measure / dt))
    t = 0.0
    for _ in range(steps_m):
        phi = wrap(step_fn(phi, omega, aij, dt))
        t += dt
        crossed = phase_cross_zero(prev, phi)
        for i in np.where(crossed)[0]:
            tap_times[int(i)].append(t)
        prev = phi

    return effective_hz_from_taps(tap_times), order_parameter(phi), tap_times


def _valid_intervals_ms(taps_ms: list[float]) -> np.ndarray:
    if len(taps_ms) < 2:
        return np.array([], dtype=float)
    arr = np.sort(np.asarray(taps_ms, dtype=float))
    intervals = np.diff(arr)
    return intervals[(intervals > 80) & (intervals < 5000)]


def frequencies_from_taps_ms(taps_ms: list[float]) -> float | None:
    intervals = _valid_intervals_ms(taps_ms)
    if len(intervals) == 0:
        return None
    return float(1000.0 / np.mean(intervals))


def frequency_stats_from_taps_ms(taps_ms: list[float]) -> tuple[float, float] | None:
    """Mean and std of instantaneous frequencies (Hz) from inter-tap intervals.

    Each interval dt (ms) contributes f = 1000/dt. Std uses sample ddof=1
    when there are ≥2 intervals; otherwise std=0.
    """
    intervals = _valid_intervals_ms(taps_ms)
    if len(intervals) == 0:
        return None
    freqs = 1000.0 / intervals
    mean_hz = float(np.mean(freqs))
    std_hz = float(np.std(freqs, ddof=1)) if len(freqs) >= 2 else 0.0
    return mean_hz, std_hz


def frequencies_in_window_ms(
    taps_ms: list[float],
    t0_ms: float,
    t1_ms: float,
) -> float | None:
    clipped = [t for t in taps_ms if t0_ms <= t <= t1_ms]
    return frequencies_from_taps_ms(clipped)


def frequency_stats_in_window_ms(
    taps_ms: list[float],
    t0_ms: float,
    t1_ms: float,
) -> tuple[float, float] | None:
    clipped = [t for t in taps_ms if t0_ms <= t <= t1_ms]
    return frequency_stats_from_taps_ms(clipped)
