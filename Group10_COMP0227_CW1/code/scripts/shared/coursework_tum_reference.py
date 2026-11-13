import argparse
import csv
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("observations_csv", type=Path)
parser.add_argument("--tum", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()

associations = []
with (args.tum / "associations.txt").open() as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 4:
            raise ValueError(f"Unexpected association: {line}")
        associations.append(parts[3])

grouped = defaultdict(list)
with args.observations_csv.open(newline="") as f:
    for row in csv.DictReader(f):
        grouped[int(row["frame_id"])].append(row)

if not grouped:
    raise ValueError("No map observations found")

if min(grouped) < 0 or max(grouped) >= len(associations):
    raise ValueError("Frame IDs outside association index range")

args.output.parent.mkdir(parents=True, exist_ok=True)
valid = skipped = 0

with args.output.open("w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["frame_id", "map_z_units", "reference_depth_m"])

    for frame_id, rows in sorted(grouped.items()):
        depth_path = args.tum / associations[frame_id]
        depth = cv2.imread(str(depth_path), cv2.IMREAD_UNCHANGED)

        if depth is None or depth.ndim != 2 or depth.dtype != np.uint16:
            raise ValueError(f"Invalid depth image: {depth_path}")

        height, width = depth.shape

        for row in rows:
            u = float(row["u"])
            v = float(row["v"])
            z = float(row["map_depth"])

            if not np.isfinite([u, v, z]).all() or z <= 0:
                skipped += 1
                continue

            x, y = round(u), round(v)
            if not (0 <= x < width and 0 <= y < height):
                skipped += 1
                continue

            raw_depth = int(depth[y, x])
            if raw_depth == 0:
                skipped += 1
                continue

            writer.writerow([frame_id, z, raw_depth / 5000.0])
            valid += 1

print(f"Reference comparisons: {valid}")
print(f"Skipped observations: {skipped}")
print(f"Saved: {args.output}")
