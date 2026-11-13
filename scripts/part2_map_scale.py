#!/usr/bin/env python3
"""COMP0227 CW1 Part 2: bring the predicted depth to the scale of a monocular SLAM map.

A monocular map is in arbitrary units: metres = s x map units. This script estimates s from the
predicted depth WITHOUT ground truth, and then checks the estimate with ground truth.

Input: one or more monocular runs that exported map_observations.csv (frame_id = img_id, u, v,
map_depth = camera Z of the map point in map units; Part 1 patch) and plot/trajectory_final.json,
and the predicted depth maps of the same sequence (depth-prediction --save NAME, TUM layout).
The sequence may have true depth (associations.txt: TUM, Replica) or not (rgb.txt only: KITTI).

For every keyframe k: read the predicted depth d at each observed (u, v) (bilinear), with the
Part 2 uncertainty model (part2_keypoint_uncertainty.py) giving sigma and valid; the ratio
r = d / map_depth is the keyframe's scale seen by one point. Robust per-keyframe scale s_k:
weighted median of r (weights 1/sigma_local^2) over valid points, after dropping points more than
3 robust standard deviations from the median in log r. Deployable estimates:
  global      the median of s_k over all keyframes (one scale for the map),
  causal      the median of s_k over the last --window keyframes up to k (what SLAM could do online),
  keyframe    s_k itself.
Checks (ground truth is used ONLY here):
  oracle      the run's Sim(3) trajectory scale (coursework_rpe.json fitted_scale),
  traj_k      the LOCAL true scale at keyframe k: true / estimated camera path length over
              +-(--traj-window) frames around it, from the ground-truth trajectory; its spread
              over k is SLAM's own scale drift (works without true depth, e.g. on KITTI),
  gt_k        (true depth only) the per-keyframe median with the TRUE depth instead of the
              prediction: the map's true scale at keyframe k,
  bias        global / true scale: the network's metric bias as seen through the map,
  vs distance the network bias in bins of metric distance (map depth x traj_k),
  map depth   (true depth only) AbsRel and MAE of map_depth x S against the true depth
              (0.1-5 m, as Part 1) for S = oracle, global, causal, keyframe, gt_k.
Note: map_observations.csv is the FINAL map (after bundle adjustment and loop closure), so the
causal estimate is an approximation of what SLAM would see online.

Examples:
  # TUM (5 Part 1 mono runs)
  pixi run -e depth-cpu python scripts/part2_map_scale.py \\
      --seq data/tum/rgbd_dataset_freiburg3_long_office_household --name dav2b --factor 5000 \\
      --model results/part2/tum_dav2b_uncertainty/model.json \\
      --runs teammate_part1/results/*/ORB2/rgbd_dataset_freiburg3_long_office_household/iteration_* \\
      --out results/part2/tum_dav2b_scale
  # KITTI (no true depth; predicted maps saved with factor 256)
  pixi run -e depth-cpu python scripts/part2_map_scale.py --seq data/kitti06_tum --name dav2b \\
      --pred-factor 256 --model results/part2/kitti_sigma_model/model.json --max-depth 100 \\
      --runs results/eval_2026_11_08-15_01_39/ORB2/video_color.mp4/iteration_* --out results/part2/kitti_dav2b_scale
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from part2_keypoint_uncertainty import bilinear, depth_sigma_at_keypoints, load_model  # noqa: E402

DIST_BINS = [0, 1, 2, 3, 5, 10, 20, 40, 80, 1e9]


def read_list(path, ncols):
    rows = []
    with open(path) as f:
        for line in f:
            if not line.startswith("#") and len(line.split()) >= ncols:
                rows.append(line.split())
    return rows


def load_depth(path, factor):
    d = cv2.imread(path, cv2.IMREAD_ANYDEPTH)
    if d is None:
        raise FileNotFoundError(path)
    return d.astype(np.float64) / factor


def wmedian(x, w):
    o = np.argsort(x)
    x, w = x[o], w[o]
    c = np.cumsum(w)
    return float(x[np.searchsorted(c, 0.5 * c[-1])])


def robust_scale(r, w):
    """Weighted median of r after rejecting outliers in log r. Returns (scale, points kept)."""
    lr = np.log(r)
    m = wmedian(lr, w)
    mad = 1.4826 * np.median(np.abs(lr - m))
    keep = np.abs(lr - m) <= 3 * max(mad, 1e-3)
    return float(np.exp(wmedian(lr[keep], w[keep]))), int(keep.sum())


def load_trajectory(run):
    p = os.path.join(run, "plot", "trajectory_final.json")
    if not os.path.exists(p):
        return None
    d = json.load(open(p))
    ids = np.asarray(d["trajectory_id"], int)
    E = np.array([np.asarray(T)[:3, 3] for T in d["trajectory_est"]])
    G = np.array([np.asarray(T)[:3, 3] for T in d["trajectory_gt"]])
    return ids, E, G


def oracle_scale(run, traj):
    p = os.path.join(run, "coursework_rpe.json")
    if os.path.exists(p):
        return float(json.load(open(p))["fitted_scale"])
    if traj is None:
        sys.exit(f"{run}: no coursework_rpe.json and no plot/trajectory_final.json")
    _, E, G = traj  # Umeyama similarity of the estimated to the true camera positions
    Ec, Gc = E - E.mean(0), G - G.mean(0)
    U, S, Vt = np.linalg.svd(Gc.T @ Ec / len(E))
    D = np.diag([1, 1, np.sign(np.linalg.det(U @ Vt))])
    return float(np.trace(np.diag(S) @ D) / (Ec ** 2).sum(1).mean())


def local_traj_scale(traj, img_id, half, min_chord):
    """True / estimated straight-line camera displacement between the poses half before and half after
    img_id (metres per map unit). A chord, not the summed path: summing many small steps lets
    trajectory jitter inflate the length when the camera moves slowly (TUM). NaN when the true
    displacement is shorter than min_chord metres (e.g. the camera mostly rotates)."""
    if traj is None:
        return np.nan
    ids, E, G = traj
    i = int(np.searchsorted(ids, img_id))
    if i >= len(ids) or ids[i] != img_id:
        i = int(np.argmin(np.abs(ids - img_id)))
    lo, hi = max(0, i - half), min(len(ids) - 1, i + half)
    lg = np.linalg.norm(G[hi] - G[lo])
    le = np.linalg.norm(E[hi] - E[lo])
    return float(lg / le) if le > 1e-9 and lg >= min_chord else np.nan


def errors(z, gt, S):
    zm = z * S
    return float(np.mean(np.abs(zm - gt) / gt)), float(np.mean(np.abs(zm - gt)))


def rel_err(S, ref):
    ok = np.isfinite(S) & np.isfinite(ref)
    return float(np.median(np.abs(S[ok] / ref[ok] - 1))) if ok.any() else np.nan


def analyse_run(run, frames, has_gt, a, model):
    obs = defaultdict(list)
    with open(os.path.join(run, "map_observations.csv")) as f:
        for r in csv.DictReader(f):
            obs[int(r["frame_id"])].append((float(r["u"]), float(r["v"]), float(r["map_depth"]), int(r["point_id"])))
    traj = load_trajectory(run)
    kf_rows, pts = [], []  # pts: (k index, z, d, gt, valid, point id)
    for img_id in sorted(obs):
        if img_id >= len(frames):
            sys.exit(f"{run}: frame_id {img_id} beyond the {len(frames)} frames of {a.seq}")
        gt_path, pred_path = frames[img_id]
        o = np.array(obs[img_id])
        kps, z, pid = o[:, :2], o[:, 2], o[:, 3]
        pred = load_depth(os.path.join(a.seq, pred_path), a.pred_factor or a.factor)
        g = np.zeros(len(z))
        if has_gt:
            gt_img = load_depth(os.path.join(a.seq, gt_path), a.factor)
            if pred.shape != gt_img.shape:
                pred = cv2.resize(pred, (gt_img.shape[1], gt_img.shape[0]), interpolation=cv2.INTER_NEAREST)
            g = bilinear(np.where((gt_img > a.min_depth) & (gt_img < a.max_depth), gt_img, 0.0), kps)
        if model:
            d, _, valid, s_rel = depth_sigma_at_keypoints(pred, kps, model)
            s_loc = np.sqrt(np.maximum(s_rel ** 2 - model["scale_sigma"] ** 2, 1e-6))
            w = 1.0 / s_loc ** 2
        else:
            d = bilinear(pred, kps)
            valid, w = (d > a.min_depth) & (d < a.max_depth), np.ones(len(d))
        ok = valid & (d > 0) & (z > 0)
        row = {"img_id": img_id, "points": len(z), "used": 0, "s_k": np.nan, "s_k_unweighted": np.nan,
               "gt_k": np.nan, "traj_k": local_traj_scale(traj, img_id, a.traj_window, a.min_chord)}
        if ok.sum() >= a.min_points:
            row["s_k"], row["used"] = robust_scale(d[ok] / z[ok], w[ok])
            pos = (d > 0) & (z > 0)
            row["s_k_unweighted"] = robust_scale(d[pos] / z[pos], np.ones(int(pos.sum())))[0]
        okg = (g > 0) & (z > 0)
        if okg.sum() >= a.min_points:
            row["gt_k"] = robust_scale(g[okg] / z[okg], np.ones(int(okg.sum())))[0]
        k = len(kf_rows)
        kf_rows.append(row)
        pts.append(np.stack([np.full(len(z), k), z, d, g, ok, pid], 1))
    P = np.vstack(pts)
    s_k = np.array([r["s_k"] for r in kf_rows])
    gt_k = np.array([r["gt_k"] for r in kf_rows])
    traj_k = np.array([r["traj_k"] for r in kf_rows])
    good = np.isfinite(s_k)
    s_global = float(np.median(s_k[good]))
    s_global_unw = float(np.nanmedian([r["s_k_unweighted"] for r in kf_rows]))
    causal = np.full(len(kf_rows), np.nan)
    for k in range(len(kf_rows)):
        past = s_k[max(0, k - a.window + 1): k + 1]
        if np.isfinite(past).any():
            causal[k] = np.nanmedian(past)
    for k, r in enumerate(kf_rows):
        r["s_causal"] = causal[k]
    S = oracle_scale(run, traj)

    res = {"run": run, "keyframes": len(kf_rows), "keyframes_scaled": int(good.sum()),
           "points_used_per_keyframe": float(np.mean([r["used"] for r in kf_rows])),
           "oracle": S, "global": s_global, "global_unweighted": s_global_unw,
           "global_err_pct": 100 * (s_global / S - 1), "global_unweighted_err_pct": 100 * (s_global_unw / S - 1)}
    # same-point stability: one static 3D map point seen from several keyframes should get the same
    # predicted/map ratio. change = |r / median_point(r) - 1|; flicker = the same after dividing each r
    # by its keyframe's s_k (removes whole-frame scale jumps). Includes SLAM map error, so an upper bound.
    ki = P[:, 0].astype(int)
    okp = (P[:, 4] > 0) & np.isfinite(s_k[ki])
    r_all = P[okp, 2] / P[okp, 1]
    r_fl = r_all / s_k[ki][okp]
    pid = P[okp, 5].astype(np.int64)
    order = np.argsort(pid, kind="stable")
    pid, r_all, r_fl = pid[order], r_all[order], r_fl[order]
    starts = np.flatnonzero(np.r_[True, pid[1:] != pid[:-1]])
    counts = np.diff(np.r_[starts, len(pid)])
    ch, fl = [], []
    for s0, c in zip(starts, counts):
        if c >= 3:
            ra, rf = r_all[s0:s0 + c], r_fl[s0:s0 + c]
            ch.append(np.median(np.abs(ra / np.median(ra) - 1)))
            fl.append(np.median(np.abs(rf / np.median(rf) - 1)))
    if ch:
        res.update({"same_point_points": len(ch), "same_point_obs_median": float(np.median(counts[counts >= 3])),
                    "same_point_change": float(np.median(ch)), "same_point_flicker": float(np.median(fl))})
    # SLAM drift and the estimates against the LOCAL true scale (ground-truth trajectory)
    if np.isfinite(traj_k).sum() >= 5:
        res.update({
            "traj_drift_p10_p90": [float(np.nanpercentile(traj_k / S, 10)), float(np.nanpercentile(traj_k / S, 90))],
            "network_bias_traj": s_global / float(np.nanmedian(traj_k)),
            "vs_local_oracle_const": rel_err(np.full(len(traj_k), S), traj_k),
            "vs_local_global": rel_err(np.full(len(traj_k), s_global), traj_k),
            "vs_local_causal": rel_err(causal, traj_k), "vs_local_keyframe": rel_err(s_k, traj_k)})
        # the network bias by metric distance: with true depth, d / true depth at the same pixel;
        # without, d / (map depth x local true scale)
        ki = P[:, 0].astype(int)
        if has_gt:
            okd = (P[:, 4] > 0) & (P[:, 3] > 0)
            dist = P[okd, 3]
            res["bias_by_distance_reference"] = "true depth"
        else:
            okd = (P[:, 4] > 0) & np.isfinite(traj_k[ki])
            dist = P[okd, 1] * traj_k[ki][okd]
            res["bias_by_distance_reference"] = "map depth x local true scale (GT trajectory)"
        ratio = P[okd, 2] / dist
        res["bias_by_distance"] = []
        for lo, hi in zip(DIST_BINS[:-1], DIST_BINS[1:]):
            m = (dist >= lo) & (dist < hi)
            if m.sum() >= 50:
                res["bias_by_distance"].append({"from_m": lo, "to_m": hi if hi < 1e8 else None, "points": int(m.sum()),
                                                "median_ratio": float(np.median(ratio[m]))})
    if has_gt and np.isfinite(gt_k).any():
        gt_global = float(np.nanmedian(gt_k))
        ki = P[:, 0].astype(int)
        z, g = P[:, 1], P[:, 3]
        ev = (g >= 0.1) & (g <= 5.0) & np.isfinite(causal[ki]) & np.isfinite(s_k[ki]) & np.isfinite(gt_k[ki])
        res.update({"gt_global": gt_global, "gt_global_vs_oracle_pct": 100 * (gt_global / S - 1),
                    "network_bias": s_global / gt_global,
                    "gt_drift_p10_p90": [float(np.nanpercentile(gt_k / gt_global, 10)), float(np.nanpercentile(gt_k / gt_global, 90))],
                    "eval_points": int(ev.sum())})
        for name, scale in (("oracle", np.full(ev.sum(), S)), ("global", np.full(ev.sum(), s_global)),
                            ("causal", causal[ki][ev]), ("keyframe", s_k[ki][ev]), ("gt_keyframe", gt_k[ki][ev])):
            res[f"absrel_{name}"], res[f"mae_m_{name}"] = errors(z[ev], g[ev], scale)
    return res, kf_rows


def plot_keyframes(kf, res, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    x = [r["img_id"] for r in kf]
    fig, ax = plt.subplots(figsize=(11, 3.8))
    ax.plot(x, [r["s_k"] for r in kf], ".", color="tab:blue", ms=4, alpha=0.6, label="per keyframe, predicted depth")
    ax.plot(x, [r["s_causal"] for r in kf], "-", color="tab:blue", lw=1.5, label="causal running median")
    if np.isfinite([r["gt_k"] for r in kf]).any():
        ax.plot(x, [r["gt_k"] for r in kf], "-", color="0.4", lw=1, label="per keyframe, true depth")
    if np.isfinite([r["traj_k"] for r in kf]).any():
        ax.plot(x, [r["traj_k"] for r in kf], "-", color="tab:green", lw=1, label="local true scale (GT trajectory)")
    ax.axhline(res["oracle"], color="tab:red", lw=1, ls="--", label=f"oracle (GT trajectory) {res['oracle']:.2f}")
    ax.axhline(res["global"], color="tab:blue", lw=1, ls=":", label=f"global {res['global']:.2f}")
    ax.set_xlabel("image index (img_id)")
    ax.set_ylabel("scale (metres per map unit)")
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seq", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--factor", type=float, default=5000.0, help="true depth PNG units per metre (TUM 5000, Replica 6553.5)")
    ap.add_argument("--pred-factor", type=float, help="predicted PNG units per metre (default --factor; KITTI 256)")
    ap.add_argument("--model", help="model.json of part2_keypoint_uncertainty.py (sigma weights and valid flag)")
    ap.add_argument("--runs", nargs="+", required=True, help="run folders with map_observations.csv")
    ap.add_argument("--window", type=int, default=10, help="keyframes in the causal running median")
    ap.add_argument("--traj-window", type=int, default=50, help="poses either side for the local true scale")
    ap.add_argument("--min-chord", type=float, default=0.2,
                    help="minimum true camera displacement (m) over the window for a local true scale")
    ap.add_argument("--min-points", type=int, default=20)
    ap.add_argument("--min-depth", type=float, default=0.1)
    ap.add_argument("--max-depth", type=float, default=10.0, help="depth range used (KITTI: 100)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    pp = os.path.join(a.seq, f"associations_{a.name}.txt")
    if not os.path.exists(pp):
        sys.exit(f"{pp} not found: run depth-prediction --save {a.name} on the whole sequence first")
    pred_of = {r[1]: r[3] for r in read_list(pp, 4)}
    assoc = os.path.join(a.seq, "associations.txt")
    has_gt = os.path.exists(assoc)
    if has_gt:
        rows = read_list(assoc, 4)
        frames = [(r[3], pred_of.get(r[1])) for r in rows]
    else:  # monocular sequence (KITTI): no true depth
        rows = read_list(os.path.join(a.seq, "rgb.txt"), 2)
        frames = [(None, pred_of.get(r[1])) for r in rows]
    if any(p is None for _, p in frames):
        sys.exit(f"{sum(p is None for _, p in frames)} of {len(frames)} frames have no predicted map: incomplete --save run")
    model = load_model(a.model) if a.model else None
    print(f"{len(frames)} frames, {'with' if has_gt else 'WITHOUT'} true depth")

    runs = sorted(r for r in a.runs if os.path.exists(os.path.join(r, "map_observations.csv")))
    if not runs:
        sys.exit("no run folder with map_observations.csv")
    results = []
    for i, run in enumerate(runs):
        res, kf = analyse_run(run, frames, has_gt, a, model)
        results.append(res)
        with open(os.path.join(a.out, f"keyframes_run{i}.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(kf[0]))
            w.writeheader()
            w.writerows(kf)
        line = (f"run {i}: {res['keyframes']} keyframes, oracle {res['oracle']:.3f}, global {res['global']:.3f} "
                f"({res['global_err_pct']:+.1f}%)")
        if "network_bias" in res:
            line += f", true-depth scale {res['gt_global']:.3f} ({res['gt_global_vs_oracle_pct']:+.1f}% vs oracle)"
        if "traj_drift_p10_p90" in res:
            line += f", SLAM drift 10-90% {res['traj_drift_p10_p90'][0]:.2f}-{res['traj_drift_p10_p90'][1]:.2f}"
        print(line)
        if i == 0:
            plot_keyframes(kf, res, os.path.join(a.out, "scale_run0.png"))

    with open(os.path.join(a.out, "runs.csv"), "w", newline="") as f:
        flat = [{k: (json.dumps(v) if isinstance(v, list) else v) for k, v in r.items()} for r in results]
        keys = list(dict.fromkeys(k for r in flat for k in r))
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(flat)

    def ms(key):
        v = np.array([r[key] for r in results if key in r], float)
        if not len(v):
            return None
        return {"mean": float(v.mean()), "sd": float(v.std(ddof=1)) if len(v) > 1 else 0.0}

    keys = ["oracle", "global", "global_err_pct", "global_unweighted_err_pct", "gt_global_vs_oracle_pct", "network_bias",
            "network_bias_traj", "same_point_change", "same_point_flicker", "vs_local_oracle_const", "vs_local_global", "vs_local_causal", "vs_local_keyframe",
            "absrel_oracle", "absrel_global", "absrel_causal", "absrel_keyframe", "absrel_gt_keyframe",
            "mae_m_oracle", "mae_m_global", "mae_m_causal", "mae_m_keyframe", "mae_m_gt_keyframe"]
    summary = {"sequence": a.seq, "name": a.name, "runs": len(results), "has_true_depth": has_gt, "window": a.window,
               "traj_window": a.traj_window, "model": a.model, **{k: ms(k) for k in keys if ms(k)}}
    pooled = defaultdict(list)
    for r in results:
        for b in r.get("bias_by_distance", []):
            pooled[(b["from_m"], b["to_m"])].append(b["median_ratio"])
    summary["bias_by_distance"] = [{"from_m": lo, "to_m": hi, "median_ratio_mean": float(np.mean(v)), "runs": len(v)}
                                   for (lo, hi), v in sorted(pooled.items())]
    with open(os.path.join(a.out, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    f = lambda k, p=3: f"{summary[k]['mean']:.{p}f} +- {summary[k]['sd']:.{p}f}"  # noqa: E731
    print(f"\n{len(results)} runs (mean +- SD over runs)")
    print(f"  oracle scale (GT trajectory)       {f('oracle')}")
    print(f"  global scale from predicted depth  {f('global')}   error {f('global_err_pct', 1)} %  "
          f"(unweighted: {f('global_unweighted_err_pct', 1)} %)")
    if "network_bias" in summary:
        print(f"  true-depth scale vs oracle         {f('gt_global_vs_oracle_pct', 1)} %   (map vs trajectory consistency)")
        print(f"  network metric bias (true depth)   x{f('network_bias')}")
    if "network_bias_traj" in summary:
        print(f"  network metric bias (trajectory)   x{f('network_bias_traj')}")
        print(f"  median |scale / local true scale - 1| (local true scale: GT / estimated displacement over "
              f"+-{a.traj_window} poses, >= {a.min_chord:g} m):")
        for k, lab in (("vs_local_oracle_const", "oracle constant (SLAM drift alone)"), ("vs_local_global", "global (deployable)"),
                       ("vs_local_causal", f"causal {a.window}-keyframe (deployable)"), ("vs_local_keyframe", "per keyframe (deployable)")):
            print(f"    {lab:38s} {f(k)}")
    if "same_point_change" in summary:
        print(f"  same 3D point across keyframes: change {f('same_point_change')}, after removing each keyframe's "
              f"scale {f('same_point_flicker')}   (median |r/median - 1|; includes SLAM map error)")
    if summary["bias_by_distance"]:
        print(f"  network bias by metric distance (predicted / {results[0].get('bias_by_distance_reference', '')}):")
        print("    " + ", ".join(f"{b['from_m']:g}-{b['to_m']:g} m: x{b['median_ratio_mean']:.2f}" if b["to_m"] else
                                 f">{b['from_m']:g} m: x{b['median_ratio_mean']:.2f}" for b in summary["bias_by_distance"]))
    if "absrel_oracle" in summary:
        print("  map depth (true 0.1-5 m), scaled by:   AbsRel          MAE m")
        for n, lab in (("oracle", "oracle (GT trajectory)"), ("global", "global (pred, deployable)"),
                       ("causal", f"causal {a.window}-keyframe (deployable)"), ("keyframe", "per keyframe (deployable)"),
                       ("gt_keyframe", "true depth per keyframe (best case)")):
            print(f"    {lab:38s} {f('absrel_' + n)}   {f('mae_m_' + n)}")
    print(f"\nwritten to {a.out}: runs.csv, keyframes_run*.csv, summary.json, scale_run0.png")


if __name__ == "__main__":
    main()
