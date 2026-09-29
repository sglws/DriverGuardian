"""
plot_latency.py
---------------
Turns the per-sample CSV from bt_latency_benchmark.py into a report figure:
a histogram (shape of the distribution) beside a CDF (share of round trips
completed within X ms), with median / p95 / p99 marked on both.

Usage (on the laptop - matplotlib isn't needed on the Pi):
    scp dms@pi5:~/DriverGuardian/bt_latency_samples.csv .
    python tools/plot_latency.py bt_latency_samples.csv
    -> bt_latency.png (300 dpi) and bt_latency.pdf (vector, best for a report)
"""

import argparse
import csv
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

# Light-mode roles from the reference palette - a printed report is light.
SURFACE = "#fcfcfb"
SERIES = "#2a78d6"          # single series, so one hue and no legend box
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
MUTED = "#898781"           # axis ticks/labels
GRID = "#e1e0d9"            # hairline, solid
BASELINE = "#c3c2b7"


def load(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows or "rtt_ms" not in rows[0]:
        sys.exit(f"{path}: expected a 'rtt_ms' column (from bt_latency_benchmark.py)")
    return [float(r["rtt_ms"]) for r in rows]


def nearest_rank(sorted_vals, p):
    # Same definition as bt_latency_benchmark.py, so the figure and the
    # printed report agree to the digit.
    k = max(1, int(round(p / 100.0 * len(sorted_vals))))
    return sorted_vals[k - 1]


def style_axes(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(BASELINE)
        ax.spines[side].set_linewidth(1)
    ax.tick_params(colors=MUTED, labelcolor=TEXT_SECONDARY, length=0, labelsize=9)
    ax.grid(True, axis="y", color=GRID, linewidth=0.8, linestyle="-")
    ax.set_axisbelow(True)


def mark_lines(ax, marks, top):
    """Histogram: thin muted reference lines (recessive - the bars are the
    data), each labelled at its own height so p95/p99 never collide."""
    for i, (label, x, _) in enumerate(marks):
        ax.axvline(x, color=MUTED, linewidth=0.9, zorder=1)
        ax.annotate(f"{label} {x:.1f} ms", xy=(x, top * (0.96 - 0.14 * i)),
                    xytext=(5, 0), textcoords="offset points", va="center",
                    ha="left", fontsize=8.5, color=TEXT_PRIMARY, zorder=4,
                    bbox=dict(boxstyle="square,pad=0.15", fc=SURFACE, ec="none"))


def mark_points(ax, marks):
    """CDF: each percentile IS a point on the curve (x = time, y = share), so
    mark it there with a surface-ringed dot. p95 and p99 are only 4 points
    apart vertically, so their labels go below and above respectively."""
    offsets = [(10, 0), (10, -11), (10, 9)]
    for (label, x, q), (dx, dy) in zip(marks, offsets):
        ax.plot([x], [q], marker="o", markersize=7, color=SERIES,
                markeredgecolor=SURFACE, markeredgewidth=2, zorder=5)
        ax.annotate(f"{label} {x:.1f} ms", xy=(x, q), xytext=(dx, dy),
                    textcoords="offset points", va="center", ha="left",
                    fontsize=8.5, color=TEXT_PRIMARY, zorder=6)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="?", default="bt_latency_samples.csv")
    ap.add_argument("--out", default="bt_latency", help="output path without extension")
    ap.add_argument("--bin-ms", type=float, default=1.25,
                    help="histogram bin width. Classic Bluetooth round trips are "
                         "quantized to 1.25 ms (one 2-slot TX/RX frame), so the default "
                         "is exactly one frame per bin, phase-aligned to the data. Bins "
                         "of a different width alias against the frame grid - e.g. 1 ms "
                         "bins leave a fake empty bin every 5 ms.")
    ap.add_argument("--title", default="Pi ↔ ESP32 Bluetooth SPP round-trip latency")
    args = ap.parse_args()

    rtts = load(args.csv)
    s = sorted(rtts)
    n = len(s)
    p50, p95, p99 = nearest_rank(s, 50), nearest_rank(s, 95), nearest_rank(s, 99)
    marks = [("median", p50, 0.50), ("p95", p95, 0.95), ("p99", p99, 0.99)]

    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none"})
    fig, (ax_h, ax_c) = plt.subplots(1, 2, figsize=(10, 4.2), facecolor=SURFACE,
                                     gridspec_kw={"wspace": 0.28})
    x_max = s[-1] * 1.05

    # --- Histogram: one bar per 1.25 ms Bluetooth frame. Edges are offset half
    # a frame from the fastest sample, so each quantized cluster sits in the
    # middle of its own bin rather than straddling an edge (which would split
    # it across two bars, or leave fake-empty bins). White edge = surface gap.
    w = args.bin_ms
    start = s[0] - w / 2
    nbins = int((s[-1] - start) / w) + 2
    bins = [start + i * w for i in range(nbins + 1)]
    counts, _, _ = ax_h.hist(rtts, bins=bins, color=SERIES, edgecolor=SURFACE,
                             linewidth=1.0, zorder=2)
    style_axes(ax_h)
    ax_h.set_xlim(0, x_max)
    ax_h.set_title("Distribution", loc="left", fontsize=11, color=TEXT_PRIMARY, pad=8)
    ax_h.set_xlabel("Round-trip time (ms)", fontsize=9, color=TEXT_SECONDARY)
    ax_h.set_ylabel(f"Samples per {w:g} ms bin" + (" (1 BT frame)" if w == 1.25 else ""), fontsize=9, color=TEXT_SECONDARY)
    mark_lines(ax_h, marks, top=max(counts))

    # --- CDF: share of round trips completed within x ms ---
    ys = [(i + 1) / n for i in range(n)]
    ax_c.step(s, ys, where="post", color=SERIES, linewidth=2, zorder=2)
    style_axes(ax_c)
    ax_c.set_xlim(0, x_max)
    ax_c.set_ylim(0, 1.06)
    ax_c.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax_c.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax_c.set_title("Cumulative (CDF)", loc="left", fontsize=11, color=TEXT_PRIMARY, pad=8)
    ax_c.set_xlabel("Round-trip time (ms)", fontsize=9, color=TEXT_SECONDARY)
    ax_c.set_ylabel("Round trips completed", fontsize=9, color=TEXT_SECONDARY)
    mark_points(ax_c, marks)

    fig.suptitle(args.title, x=0.06, ha="left", fontsize=13, color=TEXT_PRIMARY, y=1.04)
    fig.text(0.06, 0.965, f"n = {n} round trips  ·  min {s[0]:.1f} ms  ·  "
             f"max {s[-1]:.1f} ms", fontsize=9, color=TEXT_SECONDARY, ha="left")

    for ext, kw in (("png", {"dpi": 300}), ("pdf", {})):
        fig.savefig(f"{args.out}.{ext}", bbox_inches="tight", facecolor=SURFACE, **kw)
    print(f"Wrote {args.out}.png and {args.out}.pdf  "
          f"(n={n}, median {p50:.2f}, p95 {p95:.2f}, p99 {p99:.2f} ms)")


if __name__ == "__main__":
    main()
