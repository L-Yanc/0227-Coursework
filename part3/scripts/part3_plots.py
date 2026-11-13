# part 3 plots from runs.csv 
import copy
import csv
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
from evo.core.trajectory import PosePath3D

runs_csv, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)

SEQS = [("fr3", "fr3"), ("room0", "room0 (Replica)"), ("kitti", "KITTI 06")]
ORDER = ["mono", "mono_rest", "mono_x", "E1", "E1s50", "E1s80", "B50", "B80", "B100", "B80u10", "B80E1", "A"]
LABEL = {"mono": "mono", "mono_rest": "mono\n(shark-l)", "mono_x": "mono\n(extra)", "E1": "E1",
         "E1s50": "E1\n50%", "E1s80": "E1\n80%", "B50": "B\n50%", "B80": "B\n80%", "B100": "B\n100%",
         "B80u10": "B 80%\n10 KFs", "B80E1": "B 80%\n+ E1", "A": "A"}
BLUE, ORANGE, AQUA, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#1baf7a", "#222222", "#6b6b6b", "#e6e6e3"

plt.rcParams.update({"font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False})

rows = list(csv.DictReader(open(runs_csv)))
for r in rows:
    for k in ("ate_se3_m", "ate_sim3_m", "scale"):
        r[k] = float(r[k])
    r["seqkey"], r["method"] = r["config"].split("_", 1)
# A's folders also hold its own mono and rgbd runs, keep only the pseudo rgbd ones
rows = [r for r in rows if r["method"] != "A" or r["mode"] == "pseudo-rgbd" or
        all(x["mode"] == r["mode"] for x in rows if x["config"] == r["config"])]


def methods(seq):
    have = {r["method"] for r in rows if r["seqkey"] == seq}
    return [m for m in ORDER if m in have] + sorted(have - set(ORDER))


def dots(ax, seq, key, log=True, one=False):
    ms = methods(seq)
    for i, m in enumerate(ms):
        v = np.array([r[key] for r in rows if r["seqkey"] == seq and r["method"] == m])
        if m.startswith("mono"):
            ax.axvspan(i - 0.45, i + 0.45, color=GRID, zorder=0, lw=0)
        jit = np.linspace(-0.12, 0.12, len(v)) if len(v) > 1 else [0]
        ax.scatter(i + np.asarray(jit), v, s=22, color=BLUE, edgecolor="white", linewidth=0.8, zorder=3)
        ax.plot([i - 0.3, i + 0.3], [np.median(v)] * 2, color=INK, lw=2, zorder=4, solid_capstyle="round")
    if one:
        ax.axhline(1, color=MUTED, lw=1, ls="--", zorder=1)
    if log:
        ax.set_yscale("log")
        fmt = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}")
        ax.yaxis.set_major_formatter(fmt)
        lo, hi = ax.get_ylim()
        ax.yaxis.set_minor_formatter(fmt if hi / lo < 12 else matplotlib.ticker.NullFormatter())
    ax.set_xticks(range(len(ms)))
    ax.set_xticklabels([LABEL.get(m, m) for m in ms])
    ax.set_xlim(-0.6, len(ms) - 0.4)
    ax.grid(axis="y", color=GRID, lw=0.8, which="both")
    ax.set_axisbelow(True)


# ATE
W = {"width_ratios": [max(3, len(methods(s))) for s, _ in SEQS]}
fig, axs = plt.subplots(2, 3, figsize=(18, 7.5), gridspec_kw=W)
for j, (seq, name) in enumerate(SEQS):
    dots(axs[0, j], seq, "ate_se3_m")
    dots(axs[1, j], seq, "ate_sim3_m")
    axs[0, j].set_title(name, color=INK, fontsize=11)
axs[0, 0].set_ylabel("ATE, SE(3) fit (m, log)")
axs[1, 0].set_ylabel("ATE, Sim(3) fit (m, log)")
fig.suptitle("Part 3: one dot per run, line = median, grey = plain mono", color=INK)
fig.tight_layout()
fig.savefig(os.path.join(out, "part3_ate.png"), dpi=160)
plt.close(fig)

# scale
fig, axs = plt.subplots(1, 3, figsize=(18, 3.8), gridspec_kw=W)
for j, (seq, name) in enumerate(SEQS):
    dots(axs[j], seq, "scale", one=True)
    axs[j].set_title(name, color=INK, fontsize=11)
axs[0].set_ylabel("fitted scale s (log)")
fig.suptitle("Scale s from the Sim(3) fit, 1 = map in metres", color=INK)
fig.tight_layout()
fig.savefig(os.path.join(out, "part3_scale.png"), dpi=160)
plt.close(fig)


# trajectories
def load(r):
    p = os.path.join(r["folder"], r["mode"], r["seq"], f"iteration_{r['run']}", "plot", "trajectory_final.json")
    if not os.path.exists(p):
        return None
    j = json.load(open(p))
    est = PosePath3D(poses_se3=[np.array(T) for T in j["trajectory_est"]])
    gt = PosePath3D(poses_se3=[np.array(T) for T in j["trajectory_gt"]])
    return gt, est


def median_run(config):
    rs = sorted([r for r in rows if r["config"] == config], key=lambda r: r["ate_se3_m"])
    return rs[len(rs) // 2] if rs else None


for seq, name in SEQS:
    pick = [(m, c) for m, c in (("mono", BLUE), ("E1", ORANGE), ("B80E1", AQUA)) if median_run(f"{seq}_{m}")]
    if not pick:
        continue
    fig, axs = plt.subplots(1, 2, figsize=(12, 5.5))
    plane = None
    for m, c in pick:
        got = load(median_run(f"{seq}_{m}"))
        if got is None:
            continue
        gt, est = got
        if plane is None:  # the two GT axes that move the most = top view
            plane = sorted(np.argsort(np.ptp(gt.positions_xyz, axis=0))[-2:])
            for ax in axs:
                ax.plot(*gt.positions_xyz[:, plane].T, color=INK, lw=2, label="GT")
        for ax, with_scale in zip(axs, (False, True)):
            e = copy.deepcopy(est)
            e.align(gt, correct_scale=with_scale)
            ax.plot(*e.positions_xyz[:, plane].T, color=c, lw=1.5, label=LABEL[m].replace("\n", " "))
    for ax, t in zip(axs, ("SE(3) fit: no scale correction", "Sim(3) fit: scale corrected")):
        ax.set_title(t, color=INK)
        ax.set_aspect("equal", adjustable="datalim")
        ax.set_xlabel("m")
        ax.grid(color=GRID, lw=0.8)
        ax.legend(frameon=False)
    fig.suptitle(f"{name}: median run of each method, top view", color=INK)
    fig.tight_layout()
    fig.savefig(os.path.join(out, f"part3_traj_{seq}.png"), dpi=160)
    plt.close(fig)
print("plots ->", out)
