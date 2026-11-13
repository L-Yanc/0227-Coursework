# the measures Part 1 reports, for every Part 3 run
import copy
import csv
import glob
import json
import os
import re
import sys

import cv2
import numpy as np
from evo.core.trajectory import PosePath3D

runs_csv, out_csv, datasets = sys.argv[1], sys.argv[2], sys.argv[3:]
SETTINGS = {"rgbd_dataset_freiburg3_long_office_household": ("settings/TUM3.yaml", 5000.0),
            "replica_room0_tum": ("settings/REPLICA.yaml", 6553.5)}
TRACK = re.compile(r"Tracking: elapsed_time:\s*([0-9.eE+-]+)")


def run_dir(r):
    hits = glob.glob(os.path.join(r["folder"], "**", r["mode"], r["seq"], f"iteration_{r['run']}"), recursive=True)
    return hits[0] if hits else None


def rpe_1s(data, frame_t, delta=1.0, tol=0.06):
    ids = np.asarray(data["trajectory_id"], dtype=int)
    times = frame_t[ids]
    gt = PosePath3D(poses_se3=[np.asarray(T, dtype=float) for T in data["trajectory_gt"]])
    est = copy.deepcopy(PosePath3D(poses_se3=[np.asarray(T, dtype=float) for T in data["trajectory_est"]]))
    est.align(gt, correct_scale=True)
    err = []
    for i in range(len(ids)):
        j = int(np.searchsorted(times, times[i] + delta))
        cand = [k for k in (j - 1, j) if i < k < len(ids)]
        if not cand:
            continue
        k = min(cand, key=lambda c: abs(times[c] - times[i] - delta))
        if abs(times[k] - times[i] - delta) > tol or ids[k] - ids[i] != k - i:
            continue
        rel_gt = np.linalg.inv(gt.poses_se3[i]) @ gt.poses_se3[k]
        rel_est = np.linalg.inv(est.poses_se3[i]) @ est.poses_se3[k]
        err.append(np.linalg.norm((np.linalg.inv(rel_gt) @ rel_est)[:3, 3]))
    return (float(np.sqrt(np.mean(np.square(err)))), len(err)) if err else (float("nan"), 0)


def track_ms(d):
    vals = []
    for f in glob.glob(os.path.join(d, "**", "*"), recursive=True):
        if os.path.isfile(f) and f.endswith((".log", ".txt", ".out")) and os.path.getsize(f) < 3e8:
            with open(f, errors="ignore") as fh:
                vals += [float(m.group(1)) for m in TRACK.finditer(fh.read())]
    return (1000.0 * float(np.mean(vals)), len(vals)) if vals else (float("nan"), 0)


def intrinsics(path):
    v = {}
    for line in open(path):
        m = re.match(r"\s*Camera[1]?\.(fx|fy|cx|cy):\s*([0-9.eE+-]+)", line)
        if m:
            v[m.group(1)] = float(m.group(2))
    return v["fx"], v["fy"], v["cx"], v["cy"]


def depth_files(seq_dir):
    files = []
    for line in open(os.path.join(seq_dir, "associations.txt")):
        p = line.split()
        if len(p) >= 4 and not line.startswith("#"):
            files.append(os.path.join(seq_dir, p[3]))
    return files


def map_mae(d, seq, seq_dir, scale):
    hits = glob.glob(os.path.join(d, "**", "map_dump.npz"), recursive=True)
    if seq not in SETTINGS or seq_dir is None or not hits:
        return float("nan"), 0
    path = hits[0]
    fx, fy, cx, cy = intrinsics(SETTINGS[seq][0])
    factor, files = SETTINGS[seq][1], depth_files(seq_dir)
    m = np.load(path)
    cache, err = {}, []
    for k, p in m["observations"]:
        T = m["kf_Tcw"][k]
        X = T[:3, :3] @ m["points"][p] + T[:3, 3]
        if X[2] <= 0:
            continue
        img = int(m["kf_img_id"][k])
        if img not in cache:
            cache[img] = cv2.imread(files[img], cv2.IMREAD_UNCHANGED) if img < len(files) else None
        D = cache[img]
        if D is None:
            continue
        u, v = int(round(fx * X[0] / X[2] + cx)), int(round(fy * X[1] / X[2] + cy))
        if not (0 <= u < D.shape[1] and 0 <= v < D.shape[0]) or D[v, u] == 0:
            continue
        z_true = D[v, u] / factor
        if 0.1 <= z_true <= 5.0:
            err.append(abs(X[2] * scale - z_true))
    return (float(np.mean(err)), len(err)) if err else (float("nan"), 0)


_times = {}


def frame_times(seq_dir):
    if seq_dir not in _times:
        f = os.path.join(seq_dir, "associations.txt")
        if not os.path.exists(f):
            f = os.path.join(seq_dir, "rgb.txt")
        _times[seq_dir] = np.array([float(l.split()[0]) for l in open(f) if l.strip() and not l.startswith("#")])
    return _times[seq_dir]


seq_dirs = {os.path.basename(os.path.normpath(p)): p for p in datasets}
rows = list(csv.DictReader(open(runs_csv)))
out = []
for n, r in enumerate(rows):
    d = run_dir(r)
    res = dict(config=r["config"], mode=r["mode"], seq=r["seq"], run=r["run"])
    if d is None:
        print("no folder for", r["config"], r["mode"], r["run"])
        out.append(res)
        continue
    data = json.load(open(os.path.join(d, "plot", "trajectory_final.json")
                          if os.path.exists(os.path.join(d, "plot", "trajectory_final.json"))
                          else glob.glob(os.path.join(d, "**", "trajectory_final.json"), recursive=True)[0]))
    res["rpe_1s_m"], res["rpe_pairs"] = rpe_1s(data, frame_times(seq_dirs[r["seq"]]))
    res["track_ms"], res["track_frames"] = track_ms(d)
    rgbd = r["mode"] in ("rgbd", "pseudo-rgbd") or r["config"] == "kitti_A"
    res["map_depth_mae_m"], res["map_obs"] = map_mae(d, r["seq"], seq_dirs.get(r["seq"]), 1.0 if rgbd else float(r["scale"]))
    out.append(res)
    print(f"{n + 1}/{len(rows)} {r['config']} {r['mode']} {r['run']}: RPE 1 s {res['rpe_1s_m']:.4f}, "
          f"track {res['track_ms']:.1f} ms ({res['track_frames']}), map MAE {res['map_depth_mae_m']:.4f} ({res['map_obs']})")

keys = ["config", "mode", "seq", "run", "rpe_1s_m", "rpe_pairs", "track_ms", "track_frames", "map_depth_mae_m", "map_obs"]
with open(out_csv, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=keys)
    w.writeheader()
    w.writerows(out)
print("->", out_csv)