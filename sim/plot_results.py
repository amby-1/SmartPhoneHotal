"""Optional plots comparing natural vs effective frequency histograms."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "results_json",
        nargs="?",
        default=str(Path(__file__).parent / "output" / "last_run.json"),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path(__file__).parent / "output" / "comparison.png",
    )
    args = parser.parse_args()

    data = json.loads(Path(args.results_json).read_text(encoding="utf-8"))
    cases = data["cases"]
    n = len(cases)
    fig, axes = plt.subplots(1, n, figsize=(4 * n, 3.5), sharey=True)
    if n == 1:
        axes = [axes]

    for ax, case in zip(axes, cases):
        natural = np.asarray(case["natural_hz"], dtype=float)
        effective = np.asarray(case["effective_hz"], dtype=float)
        effective = effective[np.isfinite(effective)]
        bins = np.linspace(
            min(natural.min(), effective.min() if len(effective) else natural.min()) - 0.1,
            max(natural.max(), effective.max() if len(effective) else natural.max()) + 0.1,
            16,
        )
        ax.hist(natural, bins=bins, alpha=0.45, label="natural ω/2π", color="#2f8f5f")
        ax.hist(effective, bins=bins, alpha=0.55, label="effective", color="#6dffb0")
        ax.set_title(f"a = {case['a']}  (R≈{case['order_parameter_final']:.2f})")
        ax.set_xlabel("Frequency (Hz)")
        ax.legend(fontsize=8)

    axes[0].set_ylabel("Count")
    fig.suptitle("Hotaru simulation — frequency distributions")
    fig.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=140)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
