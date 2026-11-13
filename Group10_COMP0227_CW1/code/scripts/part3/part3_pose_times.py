# usage: python part3_pose_times.py RUNS_CSV TRAJ_DIR DATASET_DIR OUT_DIR
import csv
import glob
import json
import os
import sys

import numpy as np

runs_csv, traj_dir, ds_dir, out = sys.argv[1:5]
os.makedirs(out, exist_ok=True)
seqs = {}


def sequence(seq):
    if seq not in seqs:
        d = os.path.join(ds_dir, seq)
        f = os.path.join(d, "associations.txt")
        if not os.path.exists(f):
            f = os.path.join(d, "rgb.txt")
        t = np.array([float(l.split()[0]) for l in open(f) if l.strip() and not l.startswith("#")])
        g = np.array([[float(x) for x in l.split()[:4]] for l in open(os.path.join(d, "groundtruth.txt"))
                      if l.strip() and not l.startswith("#")])
        seqs[seq] = (t, g)
    return seqs[seq]


def gt_error(times, g, xyz):
    j = np.searchsorted(g[:, 0], times).clip(1, len(g) - 1)
    j = np.where(np.abs(g[j - 1, 0] - times) < np.abs(g[j, 0] - times), j - 1, j)
    return np.linalg.norm(g[j, 1:4] - xyz, axis=1)


summary = []
for r in csv.DictReader(open(runs_csv)):
    name = f"{r['config']}_{r['mode']}_{r['seq']}_{r['run']}"
    path = glob.glob(os.path.join(r["folder"], "**", r["mode"], r["seq"], f"iteration_{r['run']}", "**",
                                  "trajectory_final.json"), recursive=True)[0]
    d = json.load(open(path))
    ids = np.asarray(d["trajectory_id"], dtype=int)
    est, gt = d["trajectory_est"], np.asarray(d["trajectory_gt"])
    t, g = sequence(r["seq"])
    n = min(len(ids), len(gt))
    shift = {k: float(np.median(gt_error(t[(ids[:n] + k).clip(0, len(t) - 1)], g, gt[:n, :3, 3])))
             for k in range(-3, 4)}
    off = min(shift, key=shift.get)
    times = t[(ids[:n] + off).clip(0, len(t) - 1)]
    err = gt_error(times, g, gt[:n, :3, 3])

    tf = os.path.join(traj_dir, name + ".txt")
    t_tum = np.array([float(l.split()[0]) for l in open(tf)]) if os.path.exists(tf) else np.array([])
    tum_diff = float(np.max(np.abs(t_tum - times))) if len(t_tum) == n else float("nan")

    with open(os.path.join(out, name + ".csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pose_index", "frame_id", "timestamp", "gt_mismatch_m"])
        for k in range(n):
            w.writerow([k, int(ids[k]), f"{times[k]:.6f}", f"{err[k]:.5f}"])

    summary.append(dict(run=name, poses=len(est), frame_ids=len(ids), gt_poses=len(gt),
                        first_frame_id=int(ids[0]), ids_increasing=bool(np.all(np.diff(ids) > 0)),
                        frame_offset=off, gt_mismatch_mm_at_saved_id=round(shift[0] * 1000, 3),
                        gt_mismatch_mm_after_offset=round(shift[off] * 1000, 3),
                        tum_file_vs_timestamp_s=round(tum_diff, 6)))

with open(os.path.join(out, "summary.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=summary[0].keys())
    w.writeheader()
    w.writerows(summary)

bad = [s for s in summary if s["poses"] != s["frame_ids"] or s["frame_ids"] != s["gt_poses"]
       or not s["ids_increasing"] or s["gt_mismatch_mm_after_offset"] > 5]
print(len(summary), "runs, problems:", len(bad))
for s in bad:
    print(s)
offs = {}
for s in summary:
    offs[s["frame_offset"]] = offs.get(s["frame_offset"], 0) + 1
print("frame offset -> runs:", offs)
print("largest gt mismatch after offset (mm):", max(s["gt_mismatch_mm_after_offset"] for s in summary))
print("largest tum file vs timestamp (s):", np.nanmax([s["tum_file_vs_timestamp_s"] for s in summary]))
