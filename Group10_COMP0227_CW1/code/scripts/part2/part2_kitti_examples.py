#!/usr/bin/env python3
"""COMP0227 CW1 Part 2: what can be said about the predicted depth on KITTI 06, which has no true depth.

Two outputs, from the saved predicted maps only (depth-prediction --save NAME on data/kitti06_tum):
  examples.png   for a few frames: the image, the predicted depth (log colour scale) and the relative
                 depth spread in a small window (where step 5a found the error doubles: depth edges)
  per_frame.csv  and along_sequence.png, for every --step-th frame: median, 5th and 95th percentile
                 of the predicted depth, the share of pixels at the network's far limit (sky, distant
                 road: no depth can be checked there), and the share of 'edge' pixels (spread > 0.1)
Plausibility checks that need no true depth: the road should get deeper towards the top of the image,
the sky should sit at the far limit, and the median depth should change smoothly along the drive.

Example:
  pixi run -e depth-cpu python scripts/part2/part2_kitti_examples.py --seq data/kitti06_tum --name dav2b \
      --pred-factor 256 --out results/part2/kitti_dav2b_examples
"""
import argparse
import csv
import os
import sys

import cv2
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LogNorm  # noqa: E402


def read_list(path, ncols):
    out = []
    with open(path) as f:
        for line in f:
            if not line.startswith("#") and len(line.split()) >= ncols:
                out.append(line.split())
    return out


def spread(pred, window):
    k = np.ones((window, window), np.uint8)
    p = pred.astype(np.float32)
    return (cv2.dilate(p, k) - cv2.erode(p, k)) / np.maximum(p, 1e-3)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seq", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--pred-factor", type=float, default=256.0)
    ap.add_argument("--frames", type=int, nargs="+", default=[0, 275, 550, 825, 1100])
    ap.add_argument("--step", type=int, default=5)
    ap.add_argument("--far", type=float, default=75.0, help="depth (m) counted as the network's far limit")
    ap.add_argument("--window", type=int, default=5)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    rows = read_list(os.path.join(a.seq, f"associations_{a.name}.txt"), 4)
    if not rows:
        sys.exit("no predicted maps listed")

    def load(i):
        t, rgb, _, dp = rows[i]
        img = cv2.cvtColor(cv2.imread(os.path.join(a.seq, rgb)), cv2.COLOR_BGR2RGB)
        d = cv2.imread(os.path.join(a.seq, dp), cv2.IMREAD_ANYDEPTH).astype(np.float64) / a.pred_factor
        return float(t), img, d

    frames = [i for i in a.frames if i < len(rows)]
    fig, ax = plt.subplots(len(frames), 3, figsize=(17, 1.75 * len(frames) + 0.6), squeeze=False)
    for r, i in enumerate(frames):
        t, img, d = load(i)
        sp = spread(d, a.window)
        ax[r, 0].imshow(img)
        ax[r, 0].set_ylabel(f"frame {i}", fontsize=9)
        im1 = ax[r, 1].imshow(np.clip(d, 1, 100), norm=LogNorm(vmin=3, vmax=100), cmap="magma_r")
        im2 = ax[r, 2].imshow(np.clip(sp, 0, 0.5), vmin=0, vmax=0.5, cmap="viridis")
        for c in range(3):
            ax[r, c].set_xticks([])
            ax[r, c].set_yticks([])
        ax[r, 1].set_title(f"predicted depth, median {np.median(d):.1f} m", fontsize=9)
        ax[r, 2].set_title(f"relative spread ({a.window}x{a.window}): {np.mean(sp > 0.1):.0%} > 0.1", fontsize=9)
    fig.colorbar(im1, ax=ax[:, 1], fraction=0.02, label="m (log)")
    fig.colorbar(im2, ax=ax[:, 2], fraction=0.02, label="relative spread")
    fig.savefig(os.path.join(a.out, "examples.png"), dpi=110, bbox_inches="tight")
    plt.close(fig)

    stats = []
    for i in range(0, len(rows), a.step):
        t, _, d = load(i)
        sp = spread(d, a.window)
        h = d.shape[0]
        stats.append({"frame": i, "time": t, "median_m": float(np.median(d)), "p5_m": float(np.percentile(d, 5)),
                      "p95_m": float(np.percentile(d, 95)), "far_fraction": float(np.mean(d >= a.far)),
                      "edge_fraction": float(np.mean(sp > 0.1)),
                      "bottom_row_median_m": float(np.median(d[int(0.9 * h):])),
                      "mid_row_median_m": float(np.median(d[int(0.45 * h):int(0.55 * h)]))})
    with open(os.path.join(a.out, "per_frame.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(stats[0]))
        w.writeheader()
        w.writerows(stats)

    x = [s["frame"] for s in stats]
    fig, ax = plt.subplots(2, 1, figsize=(11, 5), sharex=True)
    ax[0].fill_between(x, [s["p5_m"] for s in stats], [s["p95_m"] for s in stats], color="tab:blue", alpha=0.2, label="5-95%")
    ax[0].plot(x, [s["median_m"] for s in stats], color="tab:blue", label="median")
    ax[0].plot(x, [s["bottom_row_median_m"] for s in stats], color="0.4", lw=0.8, label="bottom 10% of image (road)")
    ax[0].set_ylabel("predicted depth (m)")
    ax[0].legend(fontsize=8)
    ax[1].plot(x, [s["far_fraction"] for s in stats], color="tab:red", label=f"at far limit (>= {a.far:g} m)")
    ax[1].plot(x, [s["edge_fraction"] for s in stats], color="tab:green", label="edge pixels (spread > 0.1)")
    ax[1].set_ylabel("share of pixels")
    ax[1].set_xlabel("frame (img_id)")
    ax[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(a.out, "along_sequence.png"), dpi=110)
    plt.close(fig)

    med = np.array([s["median_m"] for s in stats])
    jumps = np.abs(np.diff(np.log(med)))
    print(f"{len(stats)} frames (every {a.step}th of {len(rows)})")
    print(f"  median depth: {np.median(med):.1f} m (5-95% over frames {np.percentile(med, 5):.1f}-{np.percentile(med, 95):.1f} m)")
    print(f"  bottom 10% of image (road just ahead): median {np.median([s['bottom_row_median_m'] for s in stats]):.1f} m; "
          f"middle rows: {np.median([s['mid_row_median_m'] for s in stats]):.1f} m")
    print(f"  pixels at the far limit (>= {a.far:g} m): {np.mean([s['far_fraction'] for s in stats]):.1%}; "
          f"edge pixels: {np.mean([s['edge_fraction'] for s in stats]):.1%}")
    print(f"  frame-to-frame change of the median depth (every {a.step}th frame): median {np.median(jumps):.1%}, "
          f"95th percentile {np.percentile(jumps, 95):.1%}")
    print(f"written to {a.out}: examples.png, along_sequence.png, per_frame.csv")


if __name__ == "__main__":
    main()
