
import os
import sys

import cv2
import numpy as np

src, out = sys.argv[1], sys.argv[2]
os.makedirs(os.path.join(out, "rgb"), exist_ok=True)

times = np.loadtxt(os.path.join(src, "times.txt")).reshape(-1)
gt = np.loadtxt(os.path.join(src, "groundtruth.txt"))
assert len(gt) == len(times), f"{len(gt)} poses but {len(times)} times"
assert np.allclose(gt[:, 0], times, atol=1e-6), "groundtruth timestamps don't match times.txt"

cap = cv2.VideoCapture(os.path.join(src, "video_color.mp4"))
names = []
while True:
    ok, img = cap.read()
    if not ok:
        break
    name = f"rgb/{len(names):06d}.png"  # png so nothing is lost again
    cv2.imwrite(os.path.join(out, name), img)
    names.append(name)
assert len(names) == len(times), f"{len(names)} frames in the video but {len(times)} times"

with open(os.path.join(out, "rgb.txt"), "w") as f:
    f.write("# timestamp filename\n")
    for t, n in zip(times, names):
        f.write(f"{t:.6f} {n}\n")
with open(os.path.join(out, "groundtruth.txt"), "w") as f:
    f.write("# timestamp tx ty tz qx qy qz qw\n")
    for r in gt:
        f.write(f"{r[0]:.6f} " + " ".join(f"{x:.9f}" for x in r[1:8]) + "\n")  # drop the 9th column
print(f"{len(names)} frames written to {out}")
