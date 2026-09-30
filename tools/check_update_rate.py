"""Verify the risk-classification update-rate requirement from a session log.

Requirement: "The system shall ... compute a driver risk level with a
classification update rate of at least 12 Hz on average, with no gap between
updates exceeding 1 s (Low, Medium, High)."

The gap limit means a new classification at least every 1 s. The worst
case is what matters, so this checks the LONGEST gap between consecutive
classifications, not just the average rate.

Input is the per-classification log written by the app when
config.RISK_UPDATE_LOG = True (logs/risk_updates_<session>.csv, columns
t_monotonic, risk, case). With no argument the newest such log is used.

Usage:
    python tools/check_update_rate.py [path/to/risk_updates_*.csv] [--min-hz 1]
"""
import argparse
import csv
import glob
import os
import sys

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")


def percentile(sorted_vals, p):
    """Nearest-rank percentile (same convention as bt_latency_benchmark)."""
    k = max(0, min(len(sorted_vals) - 1, int(round(p / 100 * len(sorted_vals) + 0.5)) - 1))
    return sorted_vals[k]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("path", nargs="?", help="risk_updates_*.csv (default: newest in logs/)")
    ap.add_argument("--min-hz", type=float, default=1.0,
                    help="worst-case rate: max gap = 1/this (default 1 -> 1 s)")
    args = ap.parse_args()

    path = args.path
    if path is None:
        logs = sorted(glob.glob(os.path.join(LOGS_DIR, "risk_updates_*.csv")), key=os.path.getmtime)
        if not logs:
            sys.exit(f"No risk_updates_*.csv in {LOGS_DIR} - set RISK_UPDATE_LOG = True "
                     f"in app/config.py and run the app first.")
        path = logs[-1]

    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) < 2:
        sys.exit(f"{path}: need at least 2 classifications, found {len(rows)}.")

    t = [float(r["t_monotonic"]) for r in rows]
    gaps = [b - a for a, b in zip(t, t[1:])]
    worst_i = max(range(len(gaps)), key=gaps.__getitem__)
    duration = t[-1] - t[0]
    limit = 1.0 / args.min_hz
    s = sorted(gaps)

    counts = {}
    for r in rows:
        counts[r["risk"]] = counts.get(r["risk"], 0) + 1

    print(f"Log:              {path}")
    print(f"Classifications:  {len(rows)} over {duration:.1f} s")
    print(f"Levels seen:      " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"Average rate:     {(len(rows) - 1) / duration:.2f} Hz" if duration > 0 else "")
    print(f"Gap median/p99:   {percentile(s, 50) * 1000:.0f} / {percentile(s, 99) * 1000:.0f} ms")
    print(f"Longest gap:      {gaps[worst_i] * 1000:.0f} ms "
          f"(between #{worst_i + 1} and #{worst_i + 2}, {t[worst_i] - t[0]:.1f} s into the log)")
    over = sum(g > limit for g in gaps)
    print(f"Gaps > {limit:.0f} s:       {over}")
    ok = gaps[worst_i] <= limit
    print(f"\nRequirement >= {args.min_hz:g} Hz (every gap <= {limit * 1000:.0f} ms): "
          f"{'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
