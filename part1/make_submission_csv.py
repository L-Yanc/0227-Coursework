"""Create a concise per-run submission CSV from the detailed master results.

Usage: python make_submission_csv.py detailed_master.csv submission_results.csv
Rebuild after additional rows are added to the detailed master file.
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

FIELDS = [
    'run_id', 'sequence', 'method', 'settings', 'run_number',
    'ate_unscaled_m', 'ate_scaled_m', 'fitted_scale', 'rpe_rmse_m',
    'fraction_tracked', 'fraction_lost', 'time_per_frame_ms',
    'map_depth_mae_m', 'trajectory_file'
]


def build(source, destination):
    with open(source, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    # Each distinct configuration has its own sequence of run numbers.
    counters = defaultdict(int)
    output = []
    seen = set()
    for r in rows:
        uid = r['run_id']
        if uid in seen:
            raise ValueError(f'Duplicate run ID: {uid}')
        seen.add(uid)
        key = (r['sequence'], r['method'], r['backend'], r['feature'])
        counters[key] += 1
        src = r['trajectory_tum_file']
        # Keep portable relative paths, not paths in someone's home folder.
        trajectory = 'trajectories_tum/' + Path(src).name if src else ''
        output.append({
            'run_id': uid,
            'sequence': r['sequence'],
            'method': r['method'],
            'settings': f"backend={r['backend']}; feature={r['feature']}; sensor={r['method']}",
            'run_number': counters[key],
            'ate_unscaled_m': r['ate_unscaled_m'],
            'ate_scaled_m': r['ate_scale_aligned_m'],
            'fitted_scale': r['fitted_scale'],
            'rpe_rmse_m': r['rpe_rmse_m'],
            'fraction_tracked': r['fraction_tracked'],
            'fraction_lost': r['fraction_lost'],
            'time_per_frame_ms': r['tracking_time_mean_ms'],
            'map_depth_mae_m': r['map_depth_mae_m'],
            'trajectory_file': trajectory,
        })
    with open(destination, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(output)
    print(f'Wrote {len(output)} runs to {destination}')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: python make_submission_csv.py INPUT.csv OUTPUT.csv')
    build(sys.argv[1], sys.argv[2])
