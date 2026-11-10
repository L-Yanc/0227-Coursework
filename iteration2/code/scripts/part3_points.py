# summary of the point logs (pred_depth.py, CW1_LOG_POINTS), one folder per config
# usage: python part3_points.py POINTLOG_DIR OUT_DIR
#   prints per config: matches per run, % low parallax, B points added per run, depth of B points vs triangulated ones
#   points_ratio.png: net depth / triangulated depth vs triangulated depth, from the plain mono runs
import glob
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
FLAGS = ["trusted", "tri_added", "low_parallax", "b_candidate", "b_added"]


def read(p):
    d = pd.read_csv(p)
    for c in FLAGS:
        d[c] = d[c].astype(str).str.strip().isin(["1", "True", "true", "1.0"])
    return d


lines, ratio = [], {}
for cdir in sorted(glob.glob(os.path.join(src, "*"))):
    cfg = os.path.basename(cdir)
    if cfg.startswith("test") or cfg.endswith("stopped"):
        continue
    runs = [read(p) for p in sorted(glob.glob(os.path.join(cdir, "points_*.csv*")))]
    if not runs:
        continue
    per = []
    for d in runs:
        b = d[d.b_added]
        t = d[d.tri_added & ~d.low_parallax]
        per.append([len(d), 100 * d.low_parallax.mean(), d.b_candidate.sum(), len(b), len(d[d.tri_added]),
                    b.d_hat_m.median() if len(b) else np.nan, t.z_tri_m.median() if len(t) else np.nan])
    m = np.nanmedian(np.array(per, float), axis=0)
    lines.append(f"{cfg:16s} runs {len(runs)}  matches {m[0]:7.0f}  low par {m[1]:5.1f}%  B cand {m[2]:6.0f}  "
                 f"B added {m[3]:6.0f}  tri added {m[4]:6.0f}  depth B {m[5]:6.2f} m  depth tri {m[6]:6.2f} m")
    if cfg.endswith("_mono"):  # good triangulated points, net vs triangulation
        d = pd.concat(runs)
        g = d[d.tri_added & ~d.low_parallax & d.trusted & (d.z_tri_m > 0) & (d.d_hat_m > 0)]
        ratio[cfg.split("_")[0]] = (g.z_tri_m.values, (g.d_hat_m / g.z_tri_m).values)

print("\n".join(lines))
open(os.path.join(out, "points_summary.txt"), "w").write("\n".join(lines) + "\n")

if ratio:
    fig, axs = plt.subplots(1, len(ratio), figsize=(5 * len(ratio), 3.8), squeeze=False)
    for ax, (seq, (z, r)) in zip(axs[0], ratio.items()):
        edges = np.quantile(z, np.linspace(0, 1, 11))
        mid, med, lo, hi = [], [], [], []
        for a, b in zip(edges[:-1], edges[1:]):
            k = (z >= a) & (z <= b)
            if k.sum() < 20:
                continue
            mid.append(np.median(z[k]))
            med.append(np.median(r[k]))
            lo.append(np.quantile(r[k], 0.25))
            hi.append(np.quantile(r[k], 0.75))
            print(f"{seq:6s} depth {a:6.2f}-{b:6.2f} m  net/tri median {med[-1]:.3f}  (25-75%: {lo[-1]:.3f}-{hi[-1]:.3f})  n {k.sum()}")
        ax.fill_between(mid, lo, hi, color="#cde2fb", lw=0, label="25-75%")
        ax.plot(mid, med, color="#2a78d6", lw=2, marker="o", ms=4, label="median")
        ax.axhline(1, color="#6b6b6b", lw=1, ls="--")
        ax.set_title(seq, color="#222222")
        ax.set_xlabel("triangulated depth (m, after the running scale)")
        ax.grid(color="#e6e6e3", lw=0.8)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axs[0, 0].set_ylabel("net depth / triangulated depth")
    axs[0, 0].legend(frameon=False)
    fig.suptitle("Plain mono runs, good triangulated points (enough parallax, trusted)", color="#222222")
    fig.tight_layout()
    fig.savefig(os.path.join(out, "points_ratio.png"), dpi=160)
print("->", out)
