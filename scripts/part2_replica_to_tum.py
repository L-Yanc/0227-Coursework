#!/usr/bin/env python3
"""COMP0227 CW1 Part 2: write the TUM-layout lists for Replica room0 (NICE-SLAM version), so that
depth-prediction --tum (--save, --load, --keypoints) and the part2_*.py scripts can read it.

Writes ONLY small text files into the sequence folder; the images are not copied or changed:
  rgb.txt, depth.txt     `timestamp results/frame000000.jpg` / `timestamp results/depth000000.png`
  associations.txt       `timestamp rgb timestamp depth` (frame i <-> depth i, same index)
  groundtruth.txt        `timestamp tx ty tz qx qy qz qw`, from traj.txt
Timestamps are i / fps (default 25 Hz, the same as the team's Replica times.txt), so frame i here is
img_id i of the baseline. traj.txt holds one camera-to-world 4x4 matrix per line (16 numbers, row
by row), in the OpenCV camera convention (x right, y down, z forward), the same as TUM's ground truth.

Example:
  pixi run -e depth-cpu python scripts/part2_replica_to_tum.py --seq data/replica/room0
"""
import argparse
import glob
import os
import sys

import numpy as np


def rot_to_quat(R):
    """Rotation matrix -> (qx, qy, qz, qw), unit length, qw >= 0."""
    t = np.trace(R)
    if t > 0:
        s = 2.0 * np.sqrt(t + 1.0)
        q = [(R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s, 0.25 * s]
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
        q = [0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s, (R[2, 1] - R[1, 2]) / s]
    elif R[1, 1] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
        q = [(R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s, (R[0, 2] - R[2, 0]) / s]
    else:
        s = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
        q = [(R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s, (R[1, 0] - R[0, 1]) / s]
    q = np.array(q)
    q /= np.linalg.norm(q)
    return q if q[3] >= 0 else -q


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seq", required=True, help="the room0 folder (results/ and traj.txt)")
    ap.add_argument("--fps", type=float, default=25.0)
    ap.add_argument("--force", action="store_true", help="overwrite existing lists")
    a = ap.parse_args()

    rgb = sorted(glob.glob(os.path.join(a.seq, "results", "frame*.jpg")))
    dep = sorted(glob.glob(os.path.join(a.seq, "results", "depth*.png")))
    traj = np.loadtxt(os.path.join(a.seq, "traj.txt"))
    if traj.ndim == 1:
        traj = traj[None]
    n = len(rgb)
    if not n or len(dep) != n or len(traj) != n or traj.shape[1] != 16:
        sys.exit(f"mismatch: {n} rgb, {len(dep)} depth, {len(traj)} poses with {traj.shape[1]} numbers each")
    for i, (r, d) in enumerate(zip(rgb, dep)):  # frame i must pair with depth i
        if os.path.basename(r)[5:11] != f"{i:06d}" or os.path.basename(d)[5:11] != f"{i:06d}":
            sys.exit(f"unexpected file names at index {i}: {r}, {d}")

    out = {k: os.path.join(a.seq, k) for k in ("rgb.txt", "depth.txt", "associations.txt", "groundtruth.txt")}
    existing = [p for p in out.values() if os.path.exists(p)]
    if existing and not a.force:
        sys.exit(f"already there (use --force to overwrite): {', '.join(existing)}")

    worst = 0.0
    lines = {k: [] for k in out}
    for i in range(n):
        t = f"{i / a.fps:.6f}"
        rr, dd = os.path.relpath(rgb[i], a.seq), os.path.relpath(dep[i], a.seq)
        T = traj[i].reshape(4, 4)
        R = T[:3, :3]
        worst = max(worst, float(np.abs(R @ R.T - np.eye(3)).max()))
        q = rot_to_quat(R)
        lines["rgb.txt"].append(f"{t} {rr}")
        lines["depth.txt"].append(f"{t} {dd}")
        lines["associations.txt"].append(f"{t} {rr} {t} {dd}")
        lines["groundtruth.txt"].append(f"{t} " + " ".join(f"{x:.9f}" for x in (*T[:3, 3], *q)))
    if worst > 1e-4:
        sys.exit(f"traj.txt rotations are not orthonormal (error {worst:.1e}): not camera-to-world 4x4 rows?")

    heads = {"rgb.txt": "# timestamp filename", "depth.txt": "# timestamp filename",
             "associations.txt": "", "groundtruth.txt": "# timestamp tx ty tz qx qy qz qw (camera-to-world)"}
    for k, p in out.items():
        with open(p, "w") as f:
            if heads[k]:
                f.write(heads[k] + "\n")
            f.write("\n".join(lines[k]) + "\n")
    print(f"{n} frames at {a.fps:g} Hz ({n / a.fps:.1f} s): wrote " + ", ".join(out))
    print("first:", lines["associations.txt"][0])
    print("pose: ", lines["groundtruth.txt"][0])


if __name__ == "__main__":
    main()
