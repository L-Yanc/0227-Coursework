#!/usr/bin/env python3
"""COMP0227 CW1 Part 2: where does the predicted depth go wrong?

Compares the depth maps written by `depth-prediction --save NAME` with the sequence's own
depth images, pixel by pixel, and breaks the error down by
  - true depth (bins in metres),
  - depth edges (pixels near a jump in the true depth) vs flat surfaces,
  - image region (outer border vs centre).
Every breakdown is given twice:
  raw    = the network's depth as it comes (metric),
  scaled = after one scale per frame, s = median(true / predicted).
The per-frame scale uses ground truth, so it is a DIAGNOSTIC (how much error is just scale),
never part of a method.

Works on a sequence in TUM layout (associations.txt), also while a --save run is still going.

Example:
  pixi run -e depth-cpu python scripts/part2/part2_depth_errors.py \
      --seq data/tum/rgbd_dataset_freiburg3_long_office_household --name dav2b \
      --factor 5000 --step 5 --out results/part2/tum_dav2b
Replica (once in TUM layout): --factor 6553.5
"""
import argparse
import csv
import json
import os
import sys

import cv2
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

DEPTH_BINS = [0.0, 1.0, 2.0, 3.0, 4.0, 6.0, 100.0]


# ---------------------------------------------------------------- frames
def read_assoc(path):
    """Rows of an associations file: [t_rgb, rgb_path, t_depth, depth_path]."""
    rows = []
    with open(path) as f:
        for line in f:
            if line.startswith("#"):
                continue
            p = line.split()
            if len(p) >= 4:
                rows.append(p[:4])
    return rows


def stem(p):
    return os.path.splitext(os.path.basename(p))[0]


def pair_frames(seq, name):
    """[(index, rgb_rel, true_depth_rel, pred_depth_rel)] for every frame with a saved map."""
    gt_rows = read_assoc(os.path.join(seq, "associations.txt"))
    pred_assoc = os.path.join(seq, f"associations_{name}.txt")
    pairs = []
    if os.path.exists(pred_assoc):  # the run has finished: use its own list
        pred_by_rgb = {r[1]: r[3] for r in read_assoc(pred_assoc)}
        for i, r in enumerate(gt_rows):
            p = pred_by_rgb.get(r[1])
            if p and os.path.exists(os.path.join(seq, p)):
                pairs.append((i, r[1], r[3], p))
    else:  # still running: match the saved maps by file name
        pred_dir = os.path.join(seq, f"depth_{name}")
        saved = {stem(f): f for f in os.listdir(pred_dir) if f.endswith(".png")}
        for i, r in enumerate(gt_rows):
            for key in (stem(r[1]), stem(r[3]), r[0], r[2], f"{i:06d}", str(i)):
                if key in saved:
                    pairs.append((i, r[1], r[3], os.path.join(f"depth_{name}", saved[key])))
                    break
        if not pairs and saved:
            print("Could not match saved maps to frames. Example saved names:",
                  sorted(saved)[:3], "example rgb:", gt_rows[0][1], file=sys.stderr)
    return pairs


def load_depth(path, factor):
    d = cv2.imread(path, cv2.IMREAD_ANYDEPTH)
    if d is None:
        raise FileNotFoundError(path)
    return d.astype(np.float32) / factor


# ---------------------------------------------------------------- masks
def depth_edges(gt, valid, rel_jump, dilate):
    """Pixels within `dilate` px of a jump of more than rel_jump (relative) in the true depth."""
    dx = np.zeros_like(gt)
    dy = np.zeros_like(gt)
    okx = np.zeros_like(valid)
    oky = np.zeros_like(valid)
    dx[:, :-1] = np.abs(gt[:, 1:] - gt[:, :-1])
    dy[:-1, :] = np.abs(gt[1:, :] - gt[:-1, :])
    okx[:, :-1] = valid[:, 1:] & valid[:, :-1]
    oky[:-1, :] = valid[1:, :] & valid[:-1, :]
    jump = np.maximum(np.where(okx, dx, 0), np.where(oky, dy, 0)) / np.maximum(gt, 1e-3)
    edges = (jump > rel_jump).astype(np.uint8)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * dilate + 1, 2 * dilate + 1))
    return cv2.dilate(edges, k) > 0


def border_mask(h, w, frac):
    m = np.zeros((h, w), bool)
    bh, bw = int(round(h * frac)), int(round(w * frac))
    m[:bh, :] = m[-bh:, :] = True
    m[:, :bw] = m[:, -bw:] = True
    return m


# ---------------------------------------------------------------- accumulation
class Acc:
    """Running sums, so no pixel arrays are kept across frames."""

    def __init__(self):
        self.n = 0
        self.absrel = self.abs = self.sq = 0.0
        self.d125 = 0

    def add(self, pred, gt):
        if pred.size == 0:
            return
        err = pred - gt
        self.n += pred.size
        self.absrel += float(np.sum(np.abs(err) / gt))
        self.abs += float(np.sum(np.abs(err)))
        self.sq += float(np.sum(err * err))
        self.d125 += int(np.sum(np.maximum(pred / gt, gt / pred) < 1.25))

    def row(self):
        n = max(self.n, 1)
        return {"pixels": self.n, "absrel": self.absrel / n, "mae_m": self.abs / n,
                "rmse_m": (self.sq / n) ** 0.5, "delta125": self.d125 / n}


def frame_absrel(pred, gt):
    return float(np.mean(np.abs(pred - gt) / gt)) if gt.size else float("nan")


# ---------------------------------------------------------------- figures
def plot_example(seq, pair, a, title, path):
    i, rgb_rel, gt_rel, pred_rel = pair
    rgb = cv2.cvtColor(cv2.imread(os.path.join(seq, rgb_rel)), cv2.COLOR_BGR2RGB)
    gt = load_depth(os.path.join(seq, gt_rel), a.factor)
    pred = load_depth(os.path.join(seq, pred_rel), a.pred_factor or a.factor)
    if pred.shape != gt.shape:
        pred = cv2.resize(pred, (gt.shape[1], gt.shape[0]), interpolation=cv2.INTER_NEAREST)
    valid = (gt > a.min_depth) & (gt < a.max_depth) & (pred > 0) & np.isfinite(pred)
    s = float(np.median(gt[valid] / pred[valid])) if valid.any() else 1.0
    err = np.full(gt.shape, np.nan, np.float32)
    err[valid] = np.abs(pred[valid] * s - gt[valid]) / gt[valid]
    vmax = float(np.percentile(gt[valid], 98)) if valid.any() else 5.0
    fig, ax = plt.subplots(1, 4, figsize=(16, 3.6))
    ax[0].imshow(rgb); ax[0].set_title(f"RGB (frame {i})")
    ax[1].imshow(np.where(valid, gt, np.nan), vmin=0, vmax=vmax, cmap="viridis"); ax[1].set_title("true depth")
    ax[2].imshow(pred * s, vmin=0, vmax=vmax, cmap="viridis"); ax[2].set_title(f"predicted x {s:.2f}")
    im = ax[3].imshow(err, vmin=0, vmax=0.5, cmap="magma"); ax[3].set_title("|rel. error| after scale")
    fig.colorbar(im, ax=ax[3], fraction=0.046)
    for x in ax:
        x.axis("off")
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def plot_breakdowns(rows, path):
    groups = [("depth", "true depth (m)"), ("edge", "depth edges"), ("region", "image region")]
    fig, ax = plt.subplots(1, 3, figsize=(15, 3.8))
    for k, (g, label) in enumerate(groups):
        labels = [r["label"] for r in rows if r["group"] == g and r["mode"] == "raw"]
        raw = [r["absrel"] for r in rows if r["group"] == g and r["mode"] == "raw"]
        sc = [r["absrel"] for r in rows if r["group"] == g and r["mode"] == "scaled"]
        x = np.arange(len(labels))
        ax[k].bar(x - 0.2, raw, 0.4, label="raw (metric)", color="0.6")
        ax[k].bar(x + 0.2, sc, 0.4, label="scale removed", color="tab:blue")
        ax[k].set_xticks(x)
        ax[k].set_xticklabels(labels)
        ax[k].set_xlabel(label)
        ax[k].set_ylabel("AbsRel")
    ax[0].legend()
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def plot_over_time(per_frame, path):
    idx = [r["frame"] for r in per_frame]
    fig, ax = plt.subplots(2, 1, figsize=(12, 5), sharex=True)
    ax[0].plot(idx, [r["absrel_raw"] for r in per_frame], color="0.6", label="raw (metric)")
    ax[0].plot(idx, [r["absrel_scaled"] for r in per_frame], color="tab:blue", label="scale removed")
    ax[0].set_ylabel("AbsRel per frame")
    ax[0].legend()
    ax[1].plot(idx, [r["scale"] for r in per_frame], color="tab:blue")
    ax[1].axhline(1.0, color="0.3", lw=0.8)
    ax[1].set_ylabel("scale true/pred")
    ax[1].set_xlabel("frame index")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seq", required=True, help="sequence folder in TUM layout")
    ap.add_argument("--name", required=True, help="the NAME given to depth-prediction --save")
    ap.add_argument("--factor", type=float, default=5000.0, help="true depth PNG units per metre (TUM 5000, Replica 6553.5)")
    ap.add_argument("--pred-factor", type=float, default=None, help="predicted PNG units per metre (default: same as --factor)")
    ap.add_argument("--step", type=int, default=5, help="use every Nth saved frame")
    ap.add_argument("--min-depth", type=float, default=0.1)
    ap.add_argument("--max-depth", type=float, default=10.0)
    ap.add_argument("--edge-jump", type=float, default=0.05, help="relative depth jump between neighbours that counts as an edge")
    ap.add_argument("--edge-width", type=int, default=3, help="pixels either side of an edge")
    ap.add_argument("--border", type=float, default=0.1, help="fraction of width/height counted as border")
    ap.add_argument("--out", required=True, help="output folder")
    a = ap.parse_args()

    pairs = pair_frames(a.seq, a.name)[:: a.step]
    if not pairs:
        sys.exit("No predicted maps matched. Check --seq and --name.")
    os.makedirs(a.out, exist_ok=True)
    pf = a.pred_factor or a.factor

    acc = {}

    def add(mode, group, label, pred, gt):
        acc.setdefault((mode, group, label), Acc()).add(pred, gt)

    per_frame = []
    warned = False
    for n, pair in enumerate(pairs):
        i, rgb_rel, gt_rel, pred_rel = pair
        gt = load_depth(os.path.join(a.seq, gt_rel), a.factor)
        pred = load_depth(os.path.join(a.seq, pred_rel), pf)
        if pred.shape != gt.shape:
            if not warned:
                print(f"note: predicted {pred.shape} != true {gt.shape}; resizing (nearest)")
                warned = True
            pred = cv2.resize(pred, (gt.shape[1], gt.shape[0]), interpolation=cv2.INTER_NEAREST)
        valid = (gt > a.min_depth) & (gt < a.max_depth) & (pred > 0) & np.isfinite(pred)
        if valid.sum() < 100:
            continue
        s = float(np.median(gt[valid] / pred[valid]))
        edges = depth_edges(gt, valid, a.edge_jump, a.edge_width)
        border = border_mask(*gt.shape, a.border)
        for mode, p in (("raw", pred), ("scaled", pred * s)):
            add(mode, "all", "all", p[valid], gt[valid])
            for lo, hi in zip(DEPTH_BINS[:-1], DEPTH_BINS[1:]):
                m = valid & (gt >= lo) & (gt < hi)
                lab = f"{lo:g}-{hi:g}" if hi < 100 else f">{lo:g}"
                add(mode, "depth", lab, p[m], gt[m])
            add(mode, "edge", "edge", p[valid & edges], gt[valid & edges])
            add(mode, "edge", "flat", p[valid & ~edges], gt[valid & ~edges])
            add(mode, "region", "centre", p[valid & ~border], gt[valid & ~border])
            add(mode, "region", "border", p[valid & border], gt[valid & border])
        per_frame.append({"frame": i, "rgb": rgb_rel, "valid_frac": float(valid.mean()), "scale": s,
                          "absrel_raw": frame_absrel(pred[valid], gt[valid]),
                          "absrel_scaled": frame_absrel(pred[valid] * s, gt[valid]),
                          "edge_frac": float((valid & edges).sum() / valid.sum())})
        if (n + 1) % 50 == 0:
            print(f"  {n + 1}/{len(pairs)} frames")

    if not per_frame:
        sys.exit("No frame had enough valid pixels.")

    # tables
    order = {"all": 0, "depth": 1, "edge": 2, "region": 3}
    rows = [{"mode": m, "group": g, "label": l, **v.row()} for (m, g, l), v in acc.items() if v.n > 0]
    rows.sort(key=lambda r: (r["mode"], order[r["group"]]))
    with open(os.path.join(a.out, "breakdown.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(a.out, "per_frame.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per_frame[0]))
        w.writeheader()
        w.writerows(per_frame)

    scales = np.array([r["scale"] for r in per_frame])
    summary = {
        "sequence": a.seq, "name": a.name, "frames_scored": len(per_frame), "step": a.step,
        "valid_pixels_mean_frac": float(np.mean([r["valid_frac"] for r in per_frame])),
        "scale_median": float(np.median(scales)),
        "scale_p10_p90": [float(np.percentile(scales, 10)), float(np.percentile(scales, 90))],
        "settings": {k: v for k, v in vars(a).items()},
    }
    for r in rows:
        if r["group"] == "all":
            summary[f"{r['mode']}_all"] = {k: r[k] for k in ("absrel", "mae_m", "rmse_m", "delta125")}
    with open(os.path.join(a.out, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    # figures
    plot_breakdowns(rows, os.path.join(a.out, "breakdown.png"))
    plot_over_time(per_frame, os.path.join(a.out, "over_time.png"))
    ranked = sorted(per_frame, key=lambda r: r["absrel_scaled"])
    by_idx = {p[0]: p for p in pairs}
    for tag, r in (("typical", ranked[len(ranked) // 2]), ("worst", ranked[-1])):
        plot_example(a.seq, by_idx[r["frame"]], a,
                     f"{tag} frame: AbsRel raw {r['absrel_raw']:.2f}, scale removed {r['absrel_scaled']:.2f}",
                     os.path.join(a.out, f"example_{tag}.png"))

    # printout
    print(f"\n{len(per_frame)} frames scored (--step {a.step}); "
          f"valid pixels {summary['valid_pixels_mean_frac']:.0%} per frame")
    print(f"per-frame scale true/pred: median {summary['scale_median']:.2f} "
          f"(10-90%: {summary['scale_p10_p90'][0]:.2f}-{summary['scale_p10_p90'][1]:.2f})")
    if not 0.3 < summary["scale_median"] < 3:
        print("WARNING: scale far from 1 - check --factor / --pred-factor")
    print(f"\n{'mode':7} {'group':7} {'label':7} {'AbsRel':>7} {'MAE m':>7} {'RMSE m':>7} {'d<1.25':>7} {'pixels':>11}")
    for r in rows:
        print(f"{r['mode']:7} {r['group']:7} {r['label']:7} {r['absrel']:7.3f} {r['mae_m']:7.3f} "
              f"{r['rmse_m']:7.3f} {r['delta125']:7.3f} {r['pixels']:11d}")
    print(f"\nwritten to {a.out}: breakdown.csv, per_frame.csv, summary.json, "
          "breakdown.png, over_time.png, example_typical.png, example_worst.png")


if __name__ == "__main__":
    main()
