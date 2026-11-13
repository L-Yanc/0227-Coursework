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
    from layout import CODE, GROUP, AUDIT, save
    from build_results import FIELDS, build
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--group',type=Path,default=GROUP)
    ap.add_argument('--inputs',type=Path,default=CODE/'inputs')
    ap.add_argument('--output',type=Path,default=AUDIT/'results_validation.json')
    ap.add_argument('--allow-missing',action='store_true')
    a=ap.parse_args();errors=[];hashes={};counts={};ids=set();paths=set()
    with (a.group/'results.csv').open(newline='') as f:
        reader=csv.DictReader(f);records=list(reader)
        if reader.fieldnames[:14]!=FIELDS:errors.append('First 14 columns differ from required schema')
    expected={r['run_id']:r for r in build(a.inputs,a.group)}
    for r in records:
        rid=r['run_id'];counts[r['source_part']]=counts.get(r['source_part'],0)+1
        if rid in ids or r['trajectory_file'] in paths:errors.append('Duplicate run/path: '+rid)
        ids.add(rid);paths.add(r['trajectory_file'])
        if r!=expected.get(rid):errors.append('Source score/identity/protocol mismatch: '+rid)
        rel=Path(r['trajectory_file']);p=(a.group/rel).resolve()
        if rel.is_absolute() or '..' in rel.parts or not p.is_relative_to(a.group.resolve()):
            errors.append('Escaping trajectory: '+rid);continue
        try:
            poses=trajectory(p)
            hashes[str(rel)]={'poses':poses,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
            for key in FIELDS[5:13]+['rpe_1m_m','source_wall_time_per_frame_ms']:
                if r[key]=='':continue
                v=float(r[key])
                if not math.isfinite(v) or v<0 or (key.startswith('fraction_') and v>1):raise ValueError('invalid metric '+key)
        except (ValueError,FileNotFoundError) as e:errors.append(rid+': '+str(e))
    if set(expected)!=ids:errors.append('Reported run set differs from verified source exports')
    result={'rows':len(records),'counts':counts,'valid_trajectories':len(hashes),
            'trajectory_inventory':hashes,'errors':errors,'results_ready':not errors,
            'source_identity_and_metrics_match':not errors,
            'remaining_external_checks':['Approved final report and actual report-to-command mapping are deferred.',
                '160 original Part 3 raw folders and exact checkpoint binary hashes are not bundled; full independent rescoring is not claimed.']}
    save(a.output,json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['rows','counts','valid_trajectories','results_ready']},indent=2))
    return bool(errors)
if __name__=='__main__':raise SystemExit(main())
