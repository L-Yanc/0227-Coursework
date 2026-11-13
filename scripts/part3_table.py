# Part 3 report table
import csv
import os
import statistics as st
import sys
from collections import defaultdict

runs_csv, measures_csv, out = sys.argv[1], sys.argv[2], sys.argv[3]
FULL = 95.0
SEQ = {"rgbd_dataset_freiburg3_long_office_household": "fr3", "replica_room0_tum": "room0", "kitti06_tum": "kitti"}
COLS = ["ate_se3_m", "ate_sim3_m", "scale", "rpe_1s_m", "pct_tracked", "track_ms", "map_depth_mae_m",
        "rpe_1m_m", "wall_s_per_frame"]

# config name 
NAMES = {"mono": ("mono", 2), "mono_rest": ("mono", 2), "mono_x": ("mono", 3), "E1": ("E1", 2),
         "E1s50": ("E1 50%", 3), "E1s80": ("E1 80%", 3), "B50": ("B50", 2), "B80": ("B80", 2),
         "B100": ("B100", 2), "B80u10": ("B80u10", 2), "B80E1": ("B80+E1", 2), "A": ("Reference", 3)}
A_MODES = {"mono": "mono", "pseudo-rgbd": "Reference", "rgbd": "true RGB-D"}
# which mono each config is compared with 
OWN_MONO = {("room0", "B80u10"): "mono_rest", ("room0", "B80E1"): "mono_rest"}

extra = {(m["config"], m["mode"], m["run"]): m for m in csv.DictReader(open(measures_csv))}
groups = defaultdict(list)
for r in csv.DictReader(open(runs_csv)):
    r.update({c: extra[(r["config"], r["mode"], r["run"])][c] for c in ("rpe_1s_m", "track_ms", "map_depth_mae_m")})
    seq = SEQ[r["seq"]]
    cfg = r["config"].split("_", 1)[1]
    key = (seq, f"A/{r['mode']}") if cfg == "A" and r["mode"] in A_MODES and seq != "kitti" else (seq, cfg)
    groups[key].append(r)


def kept(rows, seq):
    return [r for r in rows if seq != "kitti" or float(r["pct_tracked"]) >= FULL]


def stats(rows, seq):
    k = kept(rows, seq)
    s = {}
    for c in COLS:
        v = [float(r[c]) for r in k if r[c] not in ("", "nan")]
        s[c] = (st.median(v), min(v), max(v)) if v else (float("nan"),) * 3
    s["n"], s["N"] = len(k), len(rows)
    return s


def mono_of(seq, cfg):
    if cfg.startswith("A/"):
        return "A/mono"
    if (seq, cfg) in OWN_MONO:
        return OWN_MONO[(seq, cfg)]
    if cfg == "A":
        return "mono_x"
    return "mono" if NAMES.get(cfg, ("", 2))[1] == 2 else "mono_x"


S = {k: stats(v, k[0]) for k, v in groups.items()}

# summary.csv
with open(os.path.join(out, "summary.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["seq", "config", "runs", "runs_used"] + [f"{c}_{x}" for c in COLS for x in ("median", "min", "max")])
    for (seq, cfg), s in sorted(S.items()):
        w.writerow([seq, cfg, s["N"], s["n"]] + [f"{v:.6g}" for c in COLS for v in s[c]])


def fmt(x, c, seq):
    if c == "track_ms":
        return f"{x:.0f}"
    if c == "map_depth_mae_m":
        return f"{x:.3f}"
    if c == "scale":
        return f"{x:.1f}" if x >= 10 else f"{x:.2f}"
    if seq == "kitti":
        return f"{x:.1f}"
    if seq == "room0" and c == "ate_sim3_m":
        return f"{x:.4f}"
    return f"{x:.3f}"


# batches.md
with open(os.path.join(out, "batches.md"), "w") as f:
    for seq in ("fr3", "room0", "kitti"):
        f.write(f"\n### {seq}\n\n| config | own mono | ATE SE(3) | ATE Sim(3) | s | RPE 1 s | map MAE | tracking ms | runs used |\n|---|---|---|---|---|---|---|---|---|\n")
        for (sq, cfg), s in sorted(S.items()):
            if sq != seq:
                continue
            m = mono_of(seq, cfg)
            cell = lambda c: f"{s[c][0]:.4g} ({s[c][1]:.4g}-{s[c][2]:.4g})"
            f.write(f"| {cfg} | {m if cfg != m else '-'} | {cell('ate_se3_m')} | {cell('ate_sim3_m')} | {cell('scale')} | {cell('rpe_1s_m')} | {cell('map_depth_mae_m')} | {cell('track_ms')} | {s['n']}/{s['N']} |\n")

# table_p3.tex
order = [("mono", "mono"), ("Reference", "A/pseudo-rgbd"), ("true RGB-D", "A/rgbd"), None, ("E1", "E1"),
         ("E1 50\\%", "E1s50"), ("E1 80\\%", "E1s80"), None, ("B50", "B50"), ("B80", "B80"), ("B100", "B100"),
         ("B80u10", "B80u10"), ("B80+E1", "B80E1")]
with open(os.path.join(out, "table_p3.tex"), "w") as f:
    for item in order:
        if item is None:
            f.write("\\midrule\n")
            continue
        name, cfg = item
        cells = []
        for seq in ("fr3", "room0", "kitti"):
            key = (seq, "A" if seq == "kitti" and cfg == "A/pseudo-rgbd" else cfg)
            s = S.get(key)
            if s is None:
                cells += ["--"] * 5
                continue
            col4 = f"{s['n']}/{s['N']}" if seq == "kitti" else fmt(s["map_depth_mae_m"][0], "map_depth_mae_m", seq)
            cells += [fmt(s["ate_se3_m"][0], "ate_se3_m", seq), fmt(s["ate_sim3_m"][0], "ate_sim3_m", seq),
                      fmt(s["scale"][0], "scale", seq), col4, fmt(s["track_ms"][0], "track_ms", seq)]
        f.write(" & ".join([name] + cells) + " \\\\\n")
print("wrote summary.csv, batches.md and table_p3.tex to", out)
