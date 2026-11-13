#!/usr/bin/env python3
"""Validate saved CSV/trajectory integrity. Does not run experiments."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[2]


def trajectory(path):
    previous=None;poses=0
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):continue
        a=[float(x) for x in line.split()]
        if len(a)!=8 or not all(math.isfinite(x) for x in a):raise ValueError('Expected eight finite TUM columns')
        if previous is not None and a[0]<=previous:raise ValueError('Timestamps not strictly increasing')
        if abs(math.sqrt(sum(x*x for x in a[4:]))-1)>1e-3:raise ValueError('Quaternion not unit length')
        previous=a[0];poses+=1
    if poses<3:raise ValueError('Fewer than three poses')
    return poses


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--allow-missing',action='store_true',help='Validate available data, retaining explicit missing-input status')
    ap.add_argument('--output',type=Path,default=REPO/'Results/submission_validation.json')
    a=ap.parse_args();errors=[];missing=[];hashes={};ids=set();counts={}
    with (REPO/'Results/coursework_results.csv').open(newline='') as f:rows=list(csv.DictReader(f))
    for r in rows:
        rid=r['run_id'];counts[r['source_part']]=counts.get(r['source_part'],0)+1
        if rid in ids:errors.append({'run_id':rid,'error':'duplicate run ID'})
        ids.add(rid)
        for key in ['ate_unscaled_m','ate_scaled_m','fitted_scale','rpe_rmse_m','fraction_tracked','fraction_lost','time_per_frame_ms','map_depth_mae_m','rpe_1m_m','source_wall_time_per_frame_ms']:
            if r[key]=='':continue
            try:
                value=float(r[key])
                if not math.isfinite(value) or value<0:raise ValueError('invalid nonnegative metric')
                if key.startswith('fraction_') and value>1:raise ValueError('fraction exceeds one')
            except ValueError as e:errors.append({'run_id':rid,'metric':key,'error':str(e)})
        p=(REPO/r['trajectory_file']).resolve()
        if not p.is_relative_to(REPO):errors.append({'run_id':rid,'error':'trajectory escapes repository'});continue
        if not p.is_file():missing.append({'run_id':rid,'trajectory_file':r['trajectory_file']});continue
        try:
            poses=trajectory(p)
            hashes[r['trajectory_file']]={'poses':poses,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
            if r['trajectory_status']!='present':errors.append({'run_id':rid,'error':'stale trajectory availability; rebuild results'})
        except ValueError as e:errors.append({'run_id':rid,'error':str(e)})
    result={'rows':len(rows),'counts':counts,'valid_trajectories':len(hashes),'missing_trajectories':missing,
            'errors':errors,'results_ready':not errors and not missing,'trajectory_inventory':hashes,
            'remaining_external_checks':['Part 3 historical timestamp provenance and hardware/model configuration require original-run confirmation.',
                                         'Final report and complete report-to-command mapping are maintained outside this repository at user request.']}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['rows','counts','valid_trajectories','results_ready']},indent=2))
    print(f'Missing trajectories: {len(missing)}; invalid records: {len(errors)}')
    return 1 if errors or (missing and not a.allow_missing) else 0


if __name__=='__main__':raise SystemExit(main())
