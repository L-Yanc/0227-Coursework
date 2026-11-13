#!/usr/bin/env python3
"""COMP0227 CW1 Part 2: does the predicted depth of a static surface stay the same between frames?

Comparing the same PIXEL in two frames is wrong: the camera moves, so that pixel sees a different
surface. Instead, for frames i and j = i + gap, this script finds the SAME surface point in both:
  1. a pixel p of frame i with true depth is back-projected to 3D with the true depth,
  2. moved into frame j with the ground-truth camera poses, and projected to pixel p' of frame j,
  3. kept only if frame j's true depth at p' agrees (same surface visible: not occluded, not moved).
Then the PREDICTED depth is tested for consistency on those correspondences:
  frame i's prediction at p, back-projected and moved into frame j, gives the depth z_exp that
  frame j should predict at p' if the network were consistent. The ratio r = pred_j(p') / z_exp is 1
  for a perfectly consistent network.
Reported for each gap:
  - scale jump      median(r) per pair: the whole map getting nearer/farther between frames,
  - flicker         |r / median(r) - 1|: the local change left after removing the scale jump,
  - change          |r - 1|: both together,
  - GT floor        the same test on the true depth: sensor noise and pose error, the best possible,
  - naive           the same-pixel difference, for pred and for true depth, to show it measures
                    camera motion (true depth changes as much), not flicker.
Ground truth (depth and poses) only FINDS the correspondences; this is an analysis, not a method.

Example (TUM, after depth-prediction --save dav2b):
  pixi run -e depth-cpu python scripts/part2_depth_stability.py \
      --seq data/tum/rgbd_dataset_freiburg3_long_office_household --name dav2b \
      --settings settings/TUM3.yaml --factor 5000 --out results/part2/tum_dav2b_stability
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


# ---------------------------------------------------------------- inputs
def read_list(path, ncols):
    rows = []
    with open(path) as f:
        for line in f:
            if line.startswith("#"):
                continue
            p = line.split()
            if len(p) >= ncols:
                rows.append(p)
    return rows


def read_intrinsics(a):
    if a.fx:
        return a.fx, a.fy or a.fx, a.cx, a.cy
    # pySLAM settings are OpenCV-style YAML with keys such as `Camera.fx: 535.4`; read them as text,
    # which works whatever the YAML dialect.
    import re

    text = open(a.settings).read()
    for pre in ("Camera.", "Camera1."):
        vals = []
        for k in ("fx", "fy", "cx", "cy"):
            m = re.search(rf"^\s*{re.escape(pre + k)}\s*:\s*([-+0-9.eE]+)", text, re.M)
            vals.append(float(m.group(1)) if m else None)
        if None not in vals:
            return tuple(vals)
    sys.exit(f"No Camera.fx/fy/cx/cy in {a.settings}: pass --fx --fy --cx --cy instead")


def quat_to_R(qx, qy, qz, qw):
    n = np.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
    x, y, z, w = qx / n, qy / n, qz / n, qw / n
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def load_poses(path):
    """Ground truth as (times, list of 4x4 T_wc): `timestamp tx ty tz qx qy qz qw` per line."""
    rows = read_list(path, 8)
    times = np.array([float(r[0]) for r in rows])
    T = []
    for r in rows:
        tx, ty, tz, qx, qy, qz, qw = map(float, r[1:8])
        M = np.eye(4)
        M[:3, :3] = quat_to_R(qx, qy, qz, qw)
        M[:3, 3] = (tx, ty, tz)
        T.append(M)
    return times, T


def frames_with_poses(seq, name, gt_file, max_dt):
    """[(t, rgb, true_depth, pred_depth, T_wc)] in sequence order, for frames with a pose."""
    assoc = read_list(os.path.join(seq, "associations.txt"), 4)
    pred_path = os.path.join(seq, f"associations_{name}.txt")
    if not os.path.exists(pred_path):
        sys.exit(f"{pred_path} not found: run depth-prediction --save {name} on the whole sequence first")
    pred = {r[1]: r[3] for r in read_list(pred_path, 4)}
    times, T = load_poses(os.path.join(seq, gt_file))
    out = []
    for r in assoc:
        t = float(r[0])
        k = int(np.argmin(np.abs(times - t)))
        if abs(times[k] - t) <= max_dt and r[1] in pred:
            out.append((t, r[1], r[3], pred[r[1]], T[k]))
    return out


def load_depth(path, factor):
    d = cv2.imread(path, cv2.IMREAD_ANYDEPTH)
    if d is None:
        raise FileNotFoundError(path)
    return d.astype(np.float64) / factor


# ---------------------------------------------------------------- one pair
def pair_ratios(Di, Dj, Pi, Pj, T_ji, K, stride, a):
    """Correspondences of frame i in frame j and the ratios. Returns a dict, or None if too few."""
    h, w = Di.shape
    fx, fy, cx, cy = K
    v, u = np.mgrid[stride // 2:h:stride, stride // 2:w:stride]
    u, v = u.ravel(), v.ravel()
    di, pi = Di[v, u], Pi[v, u]
    ok = (di > a.min_depth) & (di < a.max_depth) & (pi > 0)
    u, v, di, pi = u[ok], v[ok], di[ok], pi[ok]
    if len(u) < 50:
        return None
    rays = np.stack([(u - cx) / fx, (v - cy) / fy, np.ones_like(u, dtype=np.float64)])  # z = 1
    R, t = T_ji[:3, :3], T_ji[:3, 3:4]
    Xj = R @ (rays * di) + t  # the true surface point in frame j
    zj = Xj[2]
    front = zj > a.min_depth
    uj = np.rint(fx * Xj[0] / np.where(front, zj, 1) + cx).astype(int)
    vj = np.rint(fy * Xj[1] / np.where(front, zj, 1) + cy).astype(int)
    inside = front & (uj >= 0) & (uj < w) & (vj >= 0) & (vj < h)
    ujc, vjc = np.clip(uj, 0, w - 1), np.clip(vj, 0, h - 1)
    dj, pj = Dj[vjc, ujc], Pj[vjc, ujc]
    same = inside & (dj > 0) & (np.abs(dj - zj) < a.occlusion * zj) & (pj > 0)
    if same.sum() < 50:
        return None
    s = same
    Yj = R @ (rays[:, s] * pi[s]) + t  # frame i's PREDICTED point, moved into frame j
    z_exp = Yj[2]
    keep = z_exp > a.min_depth
    r = pj[s][keep] / z_exp[keep]
    r_gt = dj[s][keep] / zj[s][keep]
    # naive same-pixel change (what NOT to do), on the same pixels of frame i
    pij, dij = Pj[v[s][keep], u[s][keep]], Dj[v[s][keep], u[s][keep]]
    naive_ok = (pij > 0) & (dij > 0)
    return {"r": r, "r_gt": r_gt, "depth": zj[s][keep],
            "naive_pred": np.abs(pij[naive_ok] / pi[s][keep][naive_ok] - 1),
            "naive_gt": np.abs(dij[naive_ok] / di[s][keep][naive_ok] - 1),
            "overlap": float(same.mean())}


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seq", required=True, help="sequence folder in TUM layout")
    ap.add_argument("--name", required=True, help="the NAME given to depth-prediction --save")
    ap.add_argument("--settings", help="camera settings file (Camera.fx, fy, cx, cy)")
    ap.add_argument("--fx", type=float)
    ap.add_argument("--fy", type=float)
    ap.add_argument("--cx", type=float)
    ap.add_argument("--cy", type=float)
    ap.add_argument("--factor", type=float, default=5000.0, help="depth PNG units per metre (TUM 5000, Replica 6553.5)")
    ap.add_argument("--pred-factor", type=float, help="predicted PNG units per metre (default: --factor)")
    ap.add_argument("--groundtruth", default="groundtruth.txt")
    ap.add_argument("--gaps", type=int, nargs="+", default=[1, 10], help="frame gaps to test")
    ap.add_argument("--step", type=int, default=10, help="start a pair every Nth frame")
    ap.add_argument("--stride", type=int, default=4, help="test every Nth pixel in each direction")
    ap.add_argument("--occlusion", type=float, default=0.05, help="max relative true-depth mismatch for the same surface")
    ap.add_argument("--min-depth", type=float, default=0.1)
    ap.add_argument("--max-depth", type=float, default=10.0)
    ap.add_argument("--max-dt", type=float, default=0.02, help="max time between a frame and its pose (s)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if not a.fx and not a.settings:
        sys.exit("pass --settings, or --fx --fy --cx --cy")

    K = read_intrinsics(a)
    frames = frames_with_poses(a.seq, a.name, a.groundtruth, a.max_dt)
    if len(frames) < max(a.gaps) + 2:
        sys.exit(f"only {len(frames)} frames with a pose and a predicted map")
    pf = a.pred_factor or a.factor
    os.makedirs(a.out, exist_ok=True)
    print(f"{len(frames)} frames with pose and prediction; intrinsics fx={K[0]:.1f} fy={K[1]:.1f} cx={K[2]:.1f} cy={K[3]:.1f}")

    cache = {}

    def get(i):
        if i not in cache:
            if len(cache) > 64:
                cache.clear()
            t, rgb, dpath, ppath, T = frames[i]
            cache[i] = (load_depth(os.path.join(a.seq, dpath), a.factor),
                        load_depth(os.path.join(a.seq, ppath), pf), T)
        return cache[i]

    rng = np.random.default_rng(0)
    pair_rows, pooled, summary = [], {}, {"sequence": a.seq, "name": a.name, "settings": vars(a), "gaps": {}}
    for gap in a.gaps:
        pooled[gap] = {"change": [], "flicker": [], "gt": []}
        for i in range(0, len(frames) - gap, a.step):
            j = i + gap
            Di, Pi, Ti = get(i)
            Dj, Pj, Tj = get(j)
            if Pi.shape != Di.shape:
                Pi = cv2.resize(Pi, (Di.shape[1], Di.shape[0]), interpolation=cv2.INTER_NEAREST)
                Pj = cv2.resize(Pj, (Dj.shape[1], Dj.shape[0]), interpolation=cv2.INTER_NEAREST)
            res = pair_ratios(Di, Dj, Pi, Pj, np.linalg.inv(Tj) @ Ti, K, a.stride, a)
            if res is None:
                continue
            r = res["r"]
            jump = float(np.median(r))
            change, flicker, gt = np.abs(r - 1), np.abs(r / jump - 1), np.abs(res["r_gt"] - 1)
            moved = float(np.linalg.norm((np.linalg.inv(Tj) @ Ti)[:3, 3]))
            pair_rows.append({
                "gap": gap, "frame_i": i, "frame_j": j, "time_i": frames[i][0], "camera_moved_m": moved,
                "points": len(r), "overlap": res["overlap"], "scale_jump": jump,
                "change_median": float(np.median(change)), "flicker_median": float(np.median(flicker)),
                "flicker_p90": float(np.percentile(flicker, 90)), "gt_floor_median": float(np.median(gt)),
                "naive_pred_median": float(np.median(res["naive_pred"])) if len(res["naive_pred"]) else float("nan"),
                "naive_gt_median": float(np.median(res["naive_gt"])) if len(res["naive_gt"]) else float("nan")})
            take = rng.choice(len(r), size=min(2000, len(r)), replace=False)
            pooled[gap]["change"].append(change[take])
            pooled[gap]["flicker"].append(flicker[take])
            pooled[gap]["gt"].append(gt[take])
        rows = [p for p in pair_rows if p["gap"] == gap]
        if not rows:
            print(f"gap {gap}: no pair had enough correspondences")
            continue
        ch, fl, g = (np.concatenate(pooled[gap][k]) for k in ("change", "flicker", "gt"))
        jumps = np.array([p["scale_jump"] for p in rows])
        summary["gaps"][str(gap)] = {
            "pairs": len(rows), "points_per_pair": float(np.mean([p["points"] for p in rows])),
            "camera_moved_m_median": float(np.median([p["camera_moved_m"] for p in rows])),
            "change_median": float(np.median(ch)), "change_p90": float(np.percentile(ch, 90)),
            "flicker_median": float(np.median(fl)), "flicker_p90": float(np.percentile(fl, 90)),
            "scale_jump_abs_median": float(np.median(np.abs(jumps - 1))),
            "scale_jump_p10_p90": [float(np.percentile(jumps, 10)), float(np.percentile(jumps, 90))],
            "gt_floor_median": float(np.median(g)), "gt_floor_p90": float(np.percentile(g, 90)),
            "naive_pred_median": float(np.nanmedian([p["naive_pred_median"] for p in rows])),
            "naive_gt_median": float(np.nanmedian([p["naive_gt_median"] for p in rows]))}

    if not pair_rows:
        sys.exit("no pair had enough correspondences: check --factor, --settings and the poses")
    with open(os.path.join(a.out, "pairs.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(pair_rows[0]))
        wr.writeheader()
        wr.writerows(pair_rows)
    with open(os.path.join(a.out, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    # figures: distributions per gap, and the scale jump along the sequence
    gaps = [g for g in a.gaps if str(g) in summary["gaps"]]
    fig, ax = plt.subplots(1, len(gaps) + 1, figsize=(5 * (len(gaps) + 1), 3.8))
    bins = np.linspace(0, 0.3, 61)
    for k, gap in enumerate(gaps):
        for key, lab, col in (("gt", "true depth (noise floor)", "0.6"), ("flicker", "predicted, scale jump removed", "tab:blue"),
                              ("change", "predicted, as it comes", "tab:orange")):
            ax[k].hist(np.concatenate(pooled[gap][key]), bins=bins, histtype="step", density=True, label=lab, color=col)
        ax[k].set_xlabel(f"|relative depth change|, gap {gap} frames")
        ax[k].set_ylabel("density")
    ax[0].legend(fontsize=8)
    for gap in gaps:
        rows = [p for p in pair_rows if p["gap"] == gap]
        ax[-1].plot([p["frame_i"] for p in rows], [p["scale_jump"] for p in rows], lw=0.8, label=f"gap {gap}")
    ax[-1].axhline(1, color="0.3", lw=0.8)
    ax[-1].set_xlabel("frame index")
    ax[-1].set_ylabel("scale jump (median ratio)")
    ax[-1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(a.out, "stability.png"), dpi=110)
    plt.close(fig)

    print(f"\n{'gap':>4} {'pairs':>5} {'moved m':>8} {'change':>7} {'flicker':>8} {'fl. p90':>8} "
          f"{'|jump|':>7} {'jump 10-90%':>13} {'GT floor':>9} {'naive pred':>11} {'naive GT':>9}")
    for gap in gaps:
        s = summary["gaps"][str(gap)]
        print(f"{gap:4d} {s['pairs']:5d} {s['camera_moved_m_median']:8.3f} {s['change_median']:7.3f} "
              f"{s['flicker_median']:8.3f} {s['flicker_p90']:8.3f} {s['scale_jump_abs_median']:7.3f} "
              f"{s['scale_jump_p10_p90'][0]:6.3f}-{s['scale_jump_p10_p90'][1]:.3f} {s['gt_floor_median']:9.3f} "
              f"{s['naive_pred_median']:11.3f} {s['naive_gt_median']:9.3f}")
    print("(all medians of |relative change|; 0.02 = 2%)")
    print(f"\nwritten to {a.out}: pairs.csv, summary.json, stability.png")


if __name__ == "__main__":
    main()
