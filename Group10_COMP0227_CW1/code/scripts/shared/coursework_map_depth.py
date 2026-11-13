#!/usr/bin/env python3
"""Score SLAM map-point observation depths against corresponding reference camera depths.

Input CSV (one row per genuine map-point observation):
    frame_id,map_z_units,reference_depth_m

Here map_z_units is the 3D map point's Z coordinate in the observing camera frame,
in the units of the SLAM map. reference_depth_m is the reference depth at that
observation's image pixel, already decoded into metres. Use --scale equal to the
trajectory's Sim(3) fitted scale for monocular runs, or 1 for RGB-D runs.

This script only scores observations. It does NOT export map observations from pySLAM.
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
import numpy as np


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('observations_csv', help='CSV with frame_id,map_z_units,reference_depth_m')
    ap.add_argument('--scale', type=float, default=1.0, help='Apply fitted trajectory scale to SLAM map depths')
    ap.add_argument('--min-depth', type=float, default=0.1)
    ap.add_argument('--max-depth', type=float, default=5.0, help='Evaluation range (m); declare this in report')
    ap.add_argument('--output', help='Optional JSON result path')
    args = ap.parse_args()
    if args.scale <= 0 or args.min_depth <= 0 or args.max_depth <= args.min_depth:
        ap.error('Require scale > 0 and 0 < min-depth < max-depth')
    by_frame = defaultdict(list)
    total = 0
    with open(args.observations_csv, newline='') as f:
        rd = csv.DictReader(f)
        required = {'frame_id', 'map_z_units', 'reference_depth_m'}
        if not required.issubset(rd.fieldnames or []):
            ap.error('Missing CSV columns: ' + ', '.join(sorted(required - set(rd.fieldnames or []))))
        for row in rd:
            total += 1
            try:
                zmap = float(row['map_z_units']) * args.scale
                zref = float(row['reference_depth_m'])
            except (ValueError, TypeError):
                continue
            if not (np.isfinite(zmap) and np.isfinite(zref)):
                continue
            if zmap <= 0 or not (args.min_depth <= zref <= args.max_depth):
                continue
            by_frame[row['frame_id']].append((zmap, zref))
    pairs = np.asarray([p for points in by_frame.values() for p in points])
    if pairs.size == 0:
        raise SystemExit('No valid map/depth observations in selected reference depth range')
    zmap, zref = pairs.T
    dif = zmap - zref
    stats = {
        'input_observations': total,
        'valid_observations': len(dif),
        'valid_fraction': len(dif) / total if total else 0.0,
        'frames_with_valid_observations': len(by_frame),
        'min_reference_depth_m': args.min_depth,
        'max_reference_depth_m': args.max_depth,
        'applied_map_scale': args.scale,
        'mae_m': float(np.mean(np.abs(dif))),
        'rmse_m': float(np.sqrt(np.mean(dif ** 2))),
        'median_absolute_error_m': float(np.median(np.abs(dif))),
        'absrel': float(np.mean(np.abs(dif) / zref)),
        'median_frame_mae_m': float(np.median([np.mean(np.abs(np.asarray(p)[:,0] - np.asarray(p)[:,1])) for p in by_frame.values()])),
    }
    print(json.dumps(stats, indent=2))
    if args.output:
        Path(args.output).write_text(json.dumps(stats, indent=2) + '\n')


if __name__ == '__main__':
    main()
