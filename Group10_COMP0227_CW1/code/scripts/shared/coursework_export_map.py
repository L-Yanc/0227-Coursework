
import csv
import numpy as np


def associated_frame_ids(timestamps, frame_ids, retained_timestamps):
    """Keep frame IDs aligned when ground-truth matching removes poses."""
    timestamps=np.asarray(timestamps,float)
    retained=np.asarray(retained_timestamps,float)
    if len(timestamps)!=len(frame_ids) or np.any(np.diff(timestamps)<=0):
        raise ValueError('Source trajectory IDs/timestamps are inconsistent')
    indices=np.searchsorted(timestamps,retained)
    if np.any(indices>=len(timestamps)) or not np.array_equal(timestamps[indices],retained):
        raise ValueError('Retained timestamp is absent from the source trajectory')
    return np.asarray(frame_ids)[indices].tolist()


def export_map_observations(slam, output_path):
    """Export map-point depths at their observed keyframe pixels."""

    rows = []

    for point in slam.map.get_points():
        world_point = np.asarray(point.pt()).reshape(3)
        point_id = int(point.id)

        for keyframe, idx in point.observations():
            if keyframe is None or keyframe.kps is None:
                continue

            idx = int(idx)
            if idx < 0 or idx >= len(keyframe.kps):
                continue

            # World coordinates -> camera coordinates
            Tcw = np.asarray(keyframe.pose())
            camera_point = (
                Tcw[:3, :3] @ world_point + Tcw[:3, 3]
            )

            z = float(camera_point[2])
            if not np.isfinite(z) or z <= 0:
                continue

            u, v = keyframe.kps[idx][:2]

            rows.append([
                int(keyframe.img_id),
                point_id,
                float(u),
                float(v),
                z,
            ])

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "frame_id", "point_id", "u", "v", "map_depth"
        ])
        writer.writerows(rows)

    print(
        f"Map observations exported: {len(rows)} "
        f"to {output_path}"
    )
