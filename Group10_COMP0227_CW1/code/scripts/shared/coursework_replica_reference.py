
"""Convert Replica map observations to the map-depth scorer's input format."""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

DEPTH_FACTOR = 6553.5


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("observations_csv", type=Path)
    parser.add_argument("--replica", type=Path, default=Path("data/replica/room0"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    grouped = defaultdict(list)
    with args.observations_csv.open(newline="") as f:
        reader = csv.DictReader(f)
        required = {"frame_id", "point_id", "u", "v", "map_depth"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing columns: {required - set(reader.fieldnames or [])}")

        for row in reader:
            grouped[int(row["frame_id"])].append(row)

    image_files = sorted((args.replica / "results").glob("frame*.jpg"))
    depth_files = sorted((args.replica / "results").glob("depth*.png"))
    if not image_files or len(image_files) != len(depth_files):
        raise ValueError("RGB/depth image count mismatch or missing images")

    frame_ids = sorted(grouped)
    print("Observed frame ID range:", frame_ids[0], "to", frame_ids[-1])
    print("Available image indices: 0 to", len(depth_files) - 1)

    # The exporter uses pySLAM frame IDs. We require these to match
    # Replica's zero-based image indices rather than silently shifting them.
    if frame_ids[0] < 0 or frame_ids[-1] >= len(depth_files):
        raise ValueError(
            "Frame IDs do not match zero-based Replica image indices. "
            "Verify frame-to-image mapping before scoring."
        )

    written = 0
    skipped = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["frame_id", "map_z_units", "reference_depth_m"])

        for frame_id in frame_ids:
            depth_path = args.replica / "results" / f"depth{frame_id:06d}.png"
            depth = cv2.imread(str(depth_path), cv2.IMREAD_UNCHANGED)

            if depth is None or depth.ndim != 2:
                raise ValueError(f"Cannot read depth image: {depth_path}")
            if depth.dtype != np.uint16:
                raise ValueError(f"Unexpected depth dtype: {depth.dtype}")

            height, width = depth.shape

            for row in grouped[frame_id]:
                u = float(row["u"])
                v = float(row["v"])
                z = float(row["map_depth"])

                if not np.isfinite([u, v, z]).all() or z <= 0:
                    skipped += 1
                    continue

                x, y = int(round(u)), int(round(v))
                if not (0 <= x < width and 0 <= y < height):
                    skipped += 1
                    continue

                raw = int(depth[y, x])
                if raw == 0:
                    skipped += 1
                    continue

                reference_depth_m = raw / DEPTH_FACTOR
                writer.writerow([frame_id, z, reference_depth_m])
                written += 1

    print(f"Valid comparisons: {written}")
    print(f"Skipped observations: {skipped}")
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
