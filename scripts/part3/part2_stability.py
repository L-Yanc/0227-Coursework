# Part 2: how much the network's scale wobbles from frame to frame (from depth_<name>/scores.csv)
# usage: python part2_stability.py out.png fr3=path/to/scores.csv room0=path/to/scores.csv
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

out = sys.argv[1]
fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 6))
print(f"{'seq':8} {'frames':>6} {'scale med':>9} {'min':>6} {'max':>6} {'sd %':>6} {'jump med %':>10} {'jump p95 %':>10}")
for arg in sys.argv[2:]:
    name, path = arg.split("=", 1)
    r = np.genfromtxt(path, delimiter=",", names=True, dtype=None, encoding=None)
    s = r["median_scale"].astype(float)
    jump = np.abs(s[1:] / s[:-1] - 1) * 100  # % change in scale between consecutive frames
    print(f"{name:8} {len(s):6d} {np.median(s):9.3f} {s.min():6.3f} {s.max():6.3f} {s.std() / s.mean() * 100:6.1f}"
          f" {np.median(jump):10.2f} {np.percentile(jump, 95):10.2f}")
    a1.plot(r["frame"], s, lw=0.8, label=name)
    a2.plot(r["frame"], r["absrel_shape"], lw=0.8, label=name)
a1.set_ylabel("median scale (true / pred)")
a2.set_ylabel("AbsRel, shape only")
a2.set_xlabel("frame")
a1.legend()
fig.tight_layout()
fig.savefig(out, dpi=120)
print("saved", out)
