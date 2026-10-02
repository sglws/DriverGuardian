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

Record a log (on the Pi):
    DG_RISK_LOG=1 python -m app.main          # monitor/test, then quit
Check it:
    python tools/check_update_rate.py [path/to/risk_updates_*.csv] [--min-hz 1] [--min-avg-hz 12]
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
    ap.add_argument("--min-avg-hz", type=float, default=12.0,
                    help="required average update rate (default 12)")
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

    # Monitoring pauses (calibration, waiting for the seatbelt) are not gaps:
    # the app numbers each continuous stretch of classifications as a segment.
    segments = {}
    for r in rows:
        segments.setdefault(r.get("segment") or "1", []).append(float(r["t_monotonic"]))
    gaps, worst, active = [], (0.0, None, 0.0), 0.0
    for seg, ts in segments.items():
        active += ts[-1] - ts[0]
        for a_t, b_t in zip(ts, ts[1:]):
            gaps.append(b_t - a_t)
            if b_t - a_t > worst[0]:
                worst = (b_t - a_t, seg, a_t - ts[0])
    if not gaps:
        sys.exit(f"{path}: no consecutive classifications to measure.")
    limit = 1.0 / args.min_hz
    s = sorted(gaps)
    avg_rate = len(gaps) / active if active > 0 else 0.0

    counts = {}
    for r in rows:
        counts[r["risk"]] = counts.get(r["risk"], 0) + 1

    print(f"Log:              {path}")
    print(f"Classifications:  {len(rows)} over {active:.1f} s of monitoring "
          f"({len(segments)} segment{'s' if len(segments) != 1 else ''})")
    print("Levels seen:      " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"Average rate:     {avg_rate:.2f} Hz")
    print(f"Gap median/p99:   {percentile(s, 50) * 1000:.0f} / {percentile(s, 99) * 1000:.0f} ms")
    print(f"Longest gap:      {worst[0] * 1000:.0f} ms (segment {worst[1]}, {worst[2]:.1f} s into it)")
    print(f"Gaps > {limit * 1000:.0f} ms:   {sum(g > limit for g in gaps)}")
    ok_rate = avg_rate >= args.min_avg_hz
    ok_gap = worst[0] <= limit
    print()
    print(f"Average update rate >= {args.min_avg_hz:g} Hz:  {avg_rate:.1f} Hz  {'PASS' if ok_rate else 'FAIL'}")
    print(f"Every gap <= {limit * 1000:.0f} ms:          {worst[0] * 1000:.0f} ms  {'PASS' if ok_gap else 'FAIL'}")
    sys.exit(0 if ok_rate and ok_gap else 1)


if __name__ == "__main__":
    main()
