#!/usr/bin/env python3
"""Fixed-time translational RPE on pySLAM trajectory_final.json.

Examples:
  python scripts/coursework_rpe.py path/to/plot/trajectory_final.json --timestamps data/videos/kitti06/times.txt
  python scripts/coursework_rpe.py path/to/plot/trajectory_final.json --timestamps data/tum/SEQUENCE/associations.txt

For TUM, each association row begins with the timestamp of the RGB frame.
For KITTI, times.txt contains one timestamp per frame.
"""
import argparse
import bisect
import copy
import json
from pathlib import Path
import numpy as np
from evo.core.trajectory import PosePath3D


def load_timestamps(path):
    timestamps = []
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        timestamps.append(float(line.split()[0]))
    if not timestamps:
        raise ValueError(f'No timestamps in {path}')
    if any(b <= a for a, b in zip(timestamps, timestamps[1:])):
        raise ValueError('Timestamps must be strictly increasing and in frame order')
    return np.array(timestamps, dtype=float)


def evaluate(json_path, timestamps_path, delta_s, tolerance_s, scale_align, require_contiguous):
    data = json.loads(Path(json_path).read_text())
    ids = np.asarray(data['trajectory_id'], dtype=int)
    if len(set(ids.tolist())) != len(ids):
        raise ValueError('Duplicate frame IDs in trajectory JSON')
    if len(ids) < 3:
        raise ValueError('Too few matched poses')
    frame_times = load_timestamps(timestamps_path)
    if ids.min() < 0 or ids.max() >= len(frame_times):
        raise ValueError(f'Frame ID range {ids.min()}..{ids.max()} exceeds timestamps (n={len(frame_times)}); check sequence ordering')
    if not np.all(np.diff(ids) > 0):
        raise ValueError('Frame IDs must be in increasing order')

    gt = PosePath3D(poses_se3=[np.asarray(T, dtype=float) for T in data['trajectory_gt']])
    est = PosePath3D(poses_se3=[np.asarray(T, dtype=float) for T in data['trajectory_est']])
    if len(ids) != len(gt.poses_se3) or len(ids) != len(est.poses_se3):
        raise ValueError('Pose count mismatch')
    est = copy.deepcopy(est)
    _, _, fitted_scale = est.align(gt, correct_scale=scale_align)

    # Pair by genuine camera timestamps, not by adjacent *saved* poses.
    times = frame_times[ids]
    index_by_id = {int(fid): idx for idx, fid in enumerate(ids)}
    errors = []
    actual_deltas = []
    skipped_gap = skipped_tolerance = 0
    for idx, i in enumerate(ids):
        target = times[idx] + delta_s
        loc = bisect.bisect_left(times, target, lo=idx + 1)
        candidates = [k for k in (loc - 1, loc) if idx < k < len(ids)]
        if not candidates:
            continue
        jdx = min(candidates, key=lambda k: abs(times[k] - target))
        dt = float(times[jdx] - times[idx])
        if abs(dt - delta_s) > tolerance_s:
            skipped_tolerance += 1
            continue
        j = int(ids[jdx])
        if require_contiguous and j - int(i) != jdx - idx:
            skipped_gap += 1
            continue
        # T_i^-1 T_j gives motion relative to camera i.
        rel_gt = np.linalg.inv(gt.poses_se3[idx]) @ gt.poses_se3[jdx]
        rel_est = np.linalg.inv(est.poses_se3[idx]) @ est.poses_se3[jdx]
        err_T = np.linalg.inv(rel_gt) @ rel_est
        errors.append(float(np.linalg.norm(err_T[:3, 3])))
        actual_deltas.append(dt)
    if not errors:
        raise ValueError('No valid RPE pairs; check timestamps, delta and tolerance')
    err = np.asarray(errors)
    return dict(
        rpe_rmse_m=float(np.sqrt(np.mean(err**2))),
        rpe_median_m=float(np.median(err)),
        rpe_mean_m=float(np.mean(err)),
        valid_pairs=len(errors),
        skipped_due_to_tracking_gaps=skipped_gap,
        skipped_due_to_time_tolerance=skipped_tolerance,
        delta_target_s=delta_s,
        delta_actual_median_s=float(np.median(actual_deltas)),
        delta_actual_min_s=float(np.min(actual_deltas)),
        delta_actual_max_s=float(np.max(actual_deltas)),
        scale_alignment='similarity' if scale_align else 'rigid',
        fitted_scale=float(fitted_scale),
        matched_pose_count=len(ids),
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('trajectory_json')
    ap.add_argument('--timestamps', required=True, help='KITTI times.txt or TUM associations.txt; one row per input frame')
    ap.add_argument('--delta-seconds', type=float, default=1.0)
    ap.add_argument('--tolerance-seconds', type=float, default=0.06, help='Maximum difference from target interval')
    ap.add_argument('--no-scale-align', action='store_true', help='Use rigid SE(3) alignment instead of scale-correcting Sim(3)')
    ap.add_argument('--allow-gaps', action='store_true', help='Include endpoints even when intermediate frame poses are missing')
    ap.add_argument('--json-output', help='Optional summary JSON output path')
    args = ap.parse_args()
    if args.delta_seconds <= 0 or args.tolerance_seconds < 0:
        ap.error('delta-seconds must be > 0 and tolerance-seconds must be >= 0')
    result = evaluate(args.trajectory_json, args.timestamps, args.delta_seconds,
                      args.tolerance_seconds, not args.no_scale_align, not args.allow_gaps)
    print(json.dumps(result, indent=2))
    if args.json_output:
        Path(args.json_output).write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
