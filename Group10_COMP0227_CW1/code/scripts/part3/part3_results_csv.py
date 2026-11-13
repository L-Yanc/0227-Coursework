# Part 3 results CSV in the group's columns
import csv
import sys

runs_csv, measures_csv, out = sys.argv[1], sys.argv[2], sys.argv[3]

HEADER = ["run_id", "sequence", "method", "settings", "run_number", "ate_unscaled_m", "ate_scaled_m", "fitted_scale",
          "rpe_rmse_m", "fraction_tracked", "fraction_lost", "time_per_frame_ms", "map_depth_mae_m",
          "trajectory_file", "rpe_1m_m", "wall_time_per_frame_ms"]
SEQ = {"rgbd_dataset_freiburg3_long_office_household": "fr3", "replica_room0_tum": "room0", "kitti06_tum": "KITTI 06"}
# config 
CFG = {"mono": ("monocular", "", 0, 2), "mono_rest": ("monocular", "", 0, 2), "mono_x": ("monocular", "", 0, 3),
       "E1": ("E1 metric start", 100, 0, 2), "E1s50": ("E1 metric start", 50, 0, 3),
       "E1s80": ("E1 metric start", 80, 0, 3), "B50": ("B fill low parallax", 50, 0, 2),
       "B80": ("B fill low parallax", 80, 0, 2), "B100": ("B fill low parallax", 100, 0, 2),
       "B80u10": ("B fill low parallax", 80, 10, 2), "B80E1": ("B + E1", 80, 0, 2),
       "A": ("pseudo-RGB-D (Reference)", "", 0, 3)}
A_MODE = {"mono": "monocular", "pseudo-rgbd": "pseudo-RGB-D (Reference)", "rgbd": "RGB-D (true depth)"}


def num(x):
    try:
        v = float(x)
        return "" if v != v else f"{v:.6g}"
    except (TypeError, ValueError):
        return ""


extra = {(m["config"], m["mode"], m["run"]): m for m in csv.DictReader(open(measures_csv))}
rows = []
for r in csv.DictReader(open(runs_csv)):
    seq = SEQ[r["seq"]]
    cfg = r["config"].split("_", 1)[1]
    method, p, until, batch = CFG[cfg]
    sensor = "rgbd" if cfg == "A" else "monocular"
    if cfg == "A" and seq != "KITTI 06":
        method, batch = A_MODE[r["mode"]], 1
        sensor = "monocular" if r["mode"] == "mono" else "rgbd"
    machine = "skate-l" if batch == 1 or (batch == 2 and seq == "fr3") or (
        batch == 2 and seq == "room0" and cfg in ("mono", "E1", "B50", "B80", "B100")) else "shark-l"
    settings = ["backend=C++", "features=ORB2", f"sensor={sensor}"]
    if method not in ("monocular", "RGB-D (true depth)"):
        settings.append("depth=Depth Anything V2 large")
    if p != "":
        settings.append(f"trust p={p} (sigma_d percentile)")
    if until:
        settings.append(f"depth for first {until} keyframes only")
    if method.startswith("pseudo"):
        settings.append("ThDepth from settings file")
    settings += [f"batch={batch}", f"machine={machine}"]
    m = extra.get((r["config"], r["mode"], r["run"]), {})
    folder = r["folder"].rstrip("/").split("/")[-1]
    rows.append({
        "run_id": f"part3_{r['config']}_{r['mode']}_{folder}_iteration_{r['run']}",
        "sequence": seq, "method": method, "settings": "; ".join(settings), "run_number": int(r["run"]) + 1,
        "ate_unscaled_m": num(r["ate_se3_m"]), "ate_scaled_m": num(r["ate_sim3_m"]), "fitted_scale": num(r["scale"]),
        "rpe_rmse_m": num(m.get("rpe_1s_m")), "fraction_tracked": num(float(r["pct_tracked"]) / 100),
        "fraction_lost": num(float(r["pct_lost"]) / 100), "time_per_frame_ms": num(m.get("track_ms")),
        "map_depth_mae_m": num(m.get("map_depth_mae_m")) if seq != "KITTI 06" else "",
        "trajectory_file": f"trajectories/{r['config']}_{r['mode']}_{r['seq']}_{r['run']}.txt",
        "rpe_1m_m": num(r["rpe_1m_m"]), "wall_time_per_frame_ms": num(float(r["wall_s_per_frame"]) * 1000),
    })

with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=HEADER)
    w.writeheader()
    w.writerows(rows)
print(f"{len(rows)} runs -> {out}")