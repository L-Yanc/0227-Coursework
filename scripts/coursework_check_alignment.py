import csv
from pathlib import Path

import cv2
import numpy as np

DATASETS = [
    {
        "name": "TUM RGB-D",
        "run": Path("results/eval_2026_11_02-18_38_13/ORB2/rgbd_dataset_freiburg3_long_office_household/iteration_0"),
        "dataset": Path("data/tum/rgbd_dataset_freiburg3_long_office_household"),
        "factor": 5000.0,
        "scale": 1.0,
        "tum": True,
    },
    {
        "name": "Replica RGB-D",
        "run": Path("results/eval_2026_11_02-17_26_25/ORB2/room0/iteration_0"),
        "dataset": Path("data/replica/room0"),
        "factor": 6553.5,
        "scale": 1.0,
        "tum": False,
    },
]

for cfg in DATASETS:
    observations = {}
    with (cfg["run"] / "map_observations.csv").open(newline="") as f:
        for row in csv.DictReader(f):
            frame_id = int(row["frame_id"])
            observations.setdefault(frame_id, []).append(row)

    if cfg["tum"]:
        with (cfg["dataset"] / "associations.txt").open() as f:
            depth_files = [
                cfg["dataset"] / parts[3]
                for line in f
                if (parts := line.split()) and not line.startswith("#")
            ]
    else:
        depth_files = sorted((cfg["dataset"] / "results").glob("depth*.png"))

    print(f"\n===== {cfg['name']} =====")

    for offset in (-1, 0, 1):
        errors = []

        for frame_id, rows in observations.items():
            index = frame_id + offset
            if index < 0 or index >= len(depth_files):
                continue

            depth = cv2.imread(str(depth_files[index]), cv2.IMREAD_UNCHANGED)
            if depth is None:
                raise RuntimeError(f"Missing depth: {depth_files[index]}")

            height, width = depth.shape

            for row in rows:
                u = float(row["u"])
                v = float(row["v"])
                map_z = float(row["map_depth"]) * cfg["scale"]

                if not np.isfinite([u, v, map_z]).all():
                    continue

                x, y = round(u), round(v)

                if not (0 <= x < width and 0 <= y < height):
                    continue

                reference = float(depth[y, x]) / cfg["factor"]

                if 0.1 <= reference <= 5.0 and map_z > 0:
                    errors.append(abs(map_z - reference))

        print(
            f"Offset {offset:+d}: "
            f"MAE={np.mean(errors):.5f} m, "
            f"median={np.median(errors):.5f} m, "
            f"N={len(errors)}"
        )
