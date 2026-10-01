"""CLI: run phase-oscillator simulation from exported JSON or demo data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

# Allow `python -m sim.run` from repo root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sim.io import extract_omega_and_xy, load_session, make_demo_session
from sim.model import SimConfig, simulate


def histogram(values: np.ndarray, bin_width: float = 0.1) -> list[dict[str, float]]:
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return []
    start = np.floor(values.min() / bin_width) * bin_width
    end = np.ceil(values.max() / bin_width) * bin_width
    edges = np.arange(start, end + bin_width, bin_width)
    counts, edges = np.histogram(values, bins=edges)
    centers = 0.5 * (edges[:-1] + edges[1:])
    return [
        {"center_hz": float(c), "count": int(n)}
        for c, n in zip(centers, counts)
        if n > 0
    ]


def run_case(
    ids: list[str],
    omega: np.ndarray,
    xy: np.ndarray,
    a: float,
    t_end: float,
    dt: float,
    seed: int,
) -> dict:
    result = simulate(omega, xy, SimConfig(a=a, t_end=t_end, dt=dt, seed=seed))
    return {
        "a": a,
        "deskIds": ids,
        "natural_hz": (omega / (2 * np.pi)).tolist(),
        "effective_hz": result.effective_hz.tolist(),
        "order_parameter_final": float(result.R[-1]),
        "order_parameter_mean_last_5s": float(
            np.mean(result.R[result.t >= max(0.0, t_end - 5.0)])
        ),
        "histogram_effective_hz": histogram(result.effective_hz),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="スマホ蛍 phase-oscillator simulation")
    parser.add_argument(
        "json_path",
        nargs="?",
        help="Exported session JSON from the web app",
    )
    parser.add_argument("--demo", action="store_true", help="Use synthetic classroom data")
    parser.add_argument(
        "--a",
        type=float,
        nargs="+",
        default=[0.0, 0.3, 1.0],
        help="Coupling strengths to sweep (default: 0 0.3 1)",
    )
    parser.add_argument("--t-end", type=float, default=30.0)
    parser.add_argument("--dt", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write full JSON results to this path",
    )
    parser.add_argument(
        "--save-demo",
        type=Path,
        help="When --demo, also write the synthetic session JSON",
    )
    args = parser.parse_args(argv)

    if args.demo or not args.json_path:
        data = make_demo_session()
        if args.save_demo:
            args.save_demo.parent.mkdir(parents=True, exist_ok=True)
            args.save_demo.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"Wrote demo session: {args.save_demo}")
    else:
        data = load_session(args.json_path)

    ids, omega, xy = extract_omega_and_xy(data)
    print(f"Oscillators: {len(ids)}  desks={ids}")
    print(f"Natural freq Hz: {np.round(omega / (2 * np.pi), 3)}")

    cases = [
        run_case(ids, omega, xy, a=a, t_end=args.t_end, dt=args.dt, seed=args.seed)
        for a in args.a
    ]

    for case in cases:
        print(
            f"a={case['a']:>4}: R_final={case['order_parameter_final']:.3f}  "
            f"R_last5s={case['order_parameter_mean_last_5s']:.3f}  "
            f"eff_hz={np.round(case['effective_hz'], 3)}"
        )

    # Compare measured experiment2 if present
    measured = []
    for row in data.get("experiment2", []):
        from sim.model import frequencies_from_taps_ms

        hz = frequencies_from_taps_ms(row.get("taps_ms", []))
        if hz is not None:
            measured.append({"deskId": row["deskId"], "hz": hz})
    if measured:
        print("Measured experiment2 Hz:", measured)

    payload = {
        "sessionId": data.get("sessionId"),
        "source": "demo" if (args.demo or not args.json_path) else str(args.json_path),
        "cases": cases,
        "measured_experiment2": measured,
    }

    out = args.output
    if out is None:
        out = ROOT / "sim" / "output" / "last_run.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote results: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
