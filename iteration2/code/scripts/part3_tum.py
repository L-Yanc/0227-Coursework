# writes every run's trajectory in TUM format (timestamp tx ty tz qx qy qz qw), raw, not aligned
# trajectory_final.json has no timestamps, so we take them from the sequence's groundtruth.txt:
# the json's GT poses are rows of that file, in order, so each estimated pose gets the time of its GT row
# usage (from the pyslam folder): python part3_tum.py RUNS_CSV OUT_DIR DATASET_DIR [DATASET_DIR ...]
#   DATASET_DIR = the folders given to --tum, e.g. $S .../room0 .../kitti06_tum (matched to runs by folder name)
import csv
import json
import os
import sys

import numpy as np
from scipy.spatial.transform import Rotation

runs_csv, out, dirs = sys.argv[1], sys.argv[2], sys.argv[3:]
os.makedirs(out, exist_ok=True)

gt = {}
for d in dirs:
    g = np.loadtxt(os.path.join(d, "groundtruth.txt"), comments="#")
    gt[os.path.basename(os.path.normpath(d))] = (g[:, 0], g[:, 1:4])

n, worst, missing = 0, 0.0, set()
for r in csv.DictReader(open(runs_csv)):
    if r["seq"] not in gt:
        missing.add(r["seq"])
        continue
    t, pos = gt[r["seq"]]
    p = os.path.join(r["folder"], r["mode"], r["seq"], f"iteration_{r['run']}", "plot", "trajectory_final.json")
    j = json.load(open(p))
    est, g = [np.array(T) for T in j["trajectory_est"]], [np.array(T) for T in j["trajectory_gt"]]
    k, rows = 0, []
    for E, G in zip(est, g):
        dist = np.linalg.norm(pos[k:] - G[:3, 3], axis=1)  # GT rows go forward in time, so search from the last match
        i = k + int(np.argmin(dist))
        worst = max(worst, float(dist[i - k]))
        k = i
        q = Rotation.from_matrix(E[:3, :3]).as_quat()  # x y z w
        rows.append(f"{t[i]:.6f} {E[0,3]:.6f} {E[1,3]:.6f} {E[2,3]:.6f} {q[0]:.6f} {q[1]:.6f} {q[2]:.6f} {q[3]:.6f}")
    with open(os.path.join(out, f"{r['config']}_{r['mode']}_{r['seq']}_{r['run']}.txt"), "w") as f:
        f.write("\n".join(rows) + "\n")
    n += 1
print(f"{n} trajectories -> {out}, worst GT match {worst:.2e} m (should be about 0)")
if missing:
    print("no dataset folder given for:", sorted(missing))
