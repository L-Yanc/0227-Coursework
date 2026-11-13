#!/usr/bin/env python3
"""COMP0227 CW1 Part 2: put the bundled KITTI 06 video in the TUM layout (monocular), so that
depth-prediction --tum (--save) can run on it.

Writes a NEW folder (default data/kitti06_tum); the video and its files are not changed:
  rgb/000000.png ...   every frame of the video, decoded in order with OpenCV (as pySLAM's video
                       reader does) and saved losslessly, so frame i is img_id i of the baseline
  rgb.txt              `timestamp rgb/000000.png`, timestamps from times.txt
  groundtruth.txt      `timestamp tx ty tz qx qy qz qw`: the first 8 columns of the video's
                       groundtruth.txt (its 9th column, a scale, is dropped)
There is no depth.txt: KITTI 06 has no reference depth in this coursework.

Example:
  pixi run -e depth-cpu python scripts/part2/part2_kitti_to_tum.py --src data/videos/kitti06 --out data/kitti06_tum
"""
import argparse
import os
import sys

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default="data/videos/kitti06", help="folder with video_color.mp4, times.txt, groundtruth.txt")
    ap.add_argument("--video", default="video_color.mp4", help="the video the baseline used")
    ap.add_argument("--out", default="data/kitti06_tum")
    ap.add_argument("--force", action="store_true", help="write into an existing folder")
    a = ap.parse_args()

    times = [float(l.split()[0]) for l in open(os.path.join(a.src, "times.txt")) if l.strip() and not l.startswith("#")]
    gt = [l.split() for l in open(os.path.join(a.src, "groundtruth.txt")) if l.strip() and not l.startswith("#")]
    if len(gt) != len(times):
        sys.exit(f"{len(times)} timestamps but {len(gt)} ground-truth poses")
    worst = max(abs(float(g[0]) - t) for g, t in zip(gt, times))
    if worst > 1e-4:
        sys.exit(f"ground-truth timestamps differ from times.txt by up to {worst:.2e} s")
    if os.path.exists(a.out) and not a.force:
        sys.exit(f"{a.out} already exists (use --force to write into it)")
    os.makedirs(os.path.join(a.out, "rgb"), exist_ok=True)

    cap = cv2.VideoCapture(os.path.join(a.src, a.video))
    if not cap.isOpened():
        sys.exit(f"cannot open {os.path.join(a.src, a.video)}")
    n, shape = 0, None
    while True:
        ok, img = cap.read()
        if not ok:
            break
        if shape is None:
            shape = img.shape
        if n >= len(times):
            sys.exit(f"the video has more frames than the {len(times)} timestamps")
        if not cv2.imwrite(os.path.join(a.out, "rgb", f"{n:06d}.png"), img):
            sys.exit(f"could not write frame {n} (disk full?)")
        n += 1
        if n % 200 == 0:
            print(f"  {n}/{len(times)} frames")
    cap.release()
    if n != len(times):
        sys.exit(f"the video has {n} frames but times.txt has {len(times)}")

    with open(os.path.join(a.out, "rgb.txt"), "w") as f:
        f.write("# timestamp filename\n")
        f.writelines(f"{times[i]:.9f} rgb/{i:06d}.png\n" for i in range(n))
    with open(os.path.join(a.out, "groundtruth.txt"), "w") as f:
        f.write("# timestamp tx ty tz qx qy qz qw\n")
        f.writelines(" ".join(g[:8]) + "\n" for g in gt)
    print(f"{n} frames ({shape[1]}x{shape[0]}), {times[-1] - times[0]:.1f} s: wrote {a.out}/rgb/, rgb.txt, groundtruth.txt")


if __name__ == "__main__":
    main()
