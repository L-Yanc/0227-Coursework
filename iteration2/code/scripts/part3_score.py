# scores every run in one or more folder lists: ATE without/with scale, scale, RPE over 1 m, % tracked/lost, time
# usage (from the pyslam folder): python part3_score.py OUT_DIR LIST [LIST ...]
#   LIST = lines of "<config name> <results/eval_... folder>", e.g. cw1/results/part3_folders.txt
# writes OUT_DIR/runs.csv (one row per run), OUT_DIR/summary.csv (median, min, max per config) and
# OUT_DIR/trajectories/<config>_<mode>_<seq>_<run>.txt in TUM format (when the run has timestamps)
import copy
import csv
import glob
import json
import os
import sys

import numpy as np
from evo.core import metrics
from evo.core.trajectory import PosePath3D
from scipy.spatial.transform import Rotation

out = sys.argv[1]
os.makedirs(os.path.join(out, "trajectories"), exist_ok=True)


def ate(gt, est, with_scale):  # same as scripts/trajectory_errors.py
    est = copy.deepcopy(est)
    _, _, scale = est.align(gt, correct_scale=with_scale)
    ape = metrics.APE(metrics.PoseRelation.translation_part)
    ape.process_data((gt, est))
    return ape.get_statistic(metrics.StatisticsType.rmse), scale, est


def rpe_1m(gt, est_sim3):  # translation error over 1 m of travel, after the Sim(3) fit
    try:
        r = metrics.RPE(metrics.PoseRelation.translation_part, delta=1.0, delta_unit=metrics.Unit.meters, all_pairs=False)
        r.process_data((gt, est_sim3))
        return r.get_statistic(metrics.StatisticsType.rmse)
    except Exception:
        return float("nan")


def metrics_file(d):
    m = {}
    p = os.path.join(d, "other_metrics_info.txt")
    if os.path.exists(p):
        for line in open(p):
            if ":" in line:
                k, v = line.split(":", 1)
                try:
                    m[k.strip()] = float(v)
                except ValueError:
                    pass
    return m


def wall_per_frame(d):  # progress.txt: frames, start, end (seconds) - tied to playback speed, not compute time
    p = os.path.join(d, "progress.txt")
    try:
        n, t0, t1 = open(p).read().split()[:3]
        return (float(t1) - float(t0)) / float(n)
    except Exception:
        return float("nan")


rows = []
warned = False
for lst in sys.argv[2:]:
    for line in open(lst):
        if not line.strip():
            continue
        config, folder = line.split()[:2]
        for path in sorted(glob.glob(os.path.join(folder, "**", "trajectory_final.json"), recursive=True)):
            d = os.path.dirname(os.path.dirname(path))  # .../<mode>/<seq>/iteration_k
            mode, seq, it = os.path.relpath(d, folder).split(os.sep)[-3:]
            run = json.load(open(path))
            est = PosePath3D(poses_se3=[np.array(T) for T in run["trajectory_est"]])
            gt = PosePath3D(poses_se3=[np.array(T) for T in run["trajectory_gt"]])
            se3, _, _ = ate(gt, est, False)
            sim3, s, est_s = ate(gt, est, True)
            m = metrics_file(d)
            rows.append(dict(config=config, mode=mode, seq=seq, run=it.split("_")[-1], folder=folder,
                             ate_se3_m=se3, ate_sim3_m=sim3, scale=s, rpe_1m_m=rpe_1m(gt, est_s),
                             pct_tracked=m.get("percent_tracked", float("nan")), pct_lost=m.get("percent_lost", float("nan")),
                             frames=m.get("num_total_frames", float("nan")), poses=len(run["trajectory_est"]),
                             wall_s_per_frame=wall_per_frame(d)))
            ts = run.get("timestamps") or run.get("timestamps_est")
            if ts is not None and len(ts) == len(run["trajectory_est"]):
                with open(os.path.join(out, "trajectories", f"{config}_{mode}_{seq}_{it}.txt"), "w") as f:
                    for t, T in zip(ts, run["trajectory_est"]):
                        T = np.array(T)
                        q = Rotation.from_matrix(T[:3, :3]).as_quat()  # x y z w
                        f.write(f"{t:.6f} {T[0,3]:.6f} {T[1,3]:.6f} {T[2,3]:.6f} {q[0]:.6f} {q[1]:.6f} {q[2]:.6f} {q[3]:.6f}\n")
            elif not warned:
                print("note: no timestamps in trajectory_final.json, keys are", list(run.keys()))
                warned = True

keys = ["config", "mode", "seq", "run", "folder", "ate_se3_m", "ate_sim3_m", "scale", "rpe_1m_m",
        "pct_tracked", "pct_lost", "frames", "poses", "wall_s_per_frame"]
with open(os.path.join(out, "runs.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=keys)
    w.writeheader()
    w.writerows(rows)

num = ["ate_se3_m", "ate_sim3_m", "scale", "rpe_1m_m", "pct_tracked", "pct_lost", "wall_s_per_frame"]
groups = {}
for r in rows:
    groups.setdefault((r["config"], r["mode"], r["seq"]), []).append(r)
with open(os.path.join(out, "summary.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["config", "mode", "seq", "n"] + [f"{k}_{s}" for k in num for s in ("med", "min", "max")])
    for (c, mo, sq), rs in groups.items():
        line = [c, mo, sq, len(rs)]
        for k in num:
            v = np.array([r[k] for r in rs], float)
            line += [np.nanmedian(v), np.nanmin(v), np.nanmax(v)] if np.isfinite(v).any() else ["", "", ""]
        w.writerow(line)
print(f"{len(rows)} runs, {len(groups)} configs -> {out}/runs.csv, summary.csv")
for (c, mo, sq), rs in groups.items():
    v = lambda k: np.nanmedian([r[k] for r in rs])
    print(f"{c:16s} {mo:12s} {sq[:12]:12s} n={len(rs):2d}  SE3 {v('ate_se3_m'):8.4f}  Sim3 {v('ate_sim3_m'):8.4f}  s {v('scale'):6.2f}  RPE {v('rpe_1m_m'):7.4f}  tracked {v('pct_tracked'):6.2f}")
