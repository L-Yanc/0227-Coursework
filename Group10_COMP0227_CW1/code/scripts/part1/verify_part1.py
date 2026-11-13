#!/usr/bin/env python3
"""Verify submitted rows, source JSONs, and TUM trajectories."""
import csv, json, sys, zipfile, io, hashlib, argparse
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from build_master_results import align

base=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--archive',type=Path,required=True)
p.add_argument('--csv',type=Path,default=base/'inputs/part1.csv')
p.add_argument('--group',type=Path,default=base.parent)
a=p.parse_args()
rows=list(csv.DictReader(a.csv.open(newline='')))
if len(rows)!=30: raise SystemExit(f'Expected 30 selected rows, found {len(rows)}')
if len({r['run_id'] for r in rows})!=30: raise SystemExit('Duplicate run ids')
archive=zipfile.ZipFile(a.archive)
manifest=json.loads(archive.read('original_trajectory_manifest.json'))
by_path={rec['path']:rec for rec in manifest['trajectories']}
seqs={'KITTI 06':0,'fr3':0,'room0':0}
for r in rows:
    id_=r['run_id']; batch, it = id_.rsplit('_iteration_',1)
    dirs=[p for p in by_path if f'/{batch}/' in p and p.endswith(f'/iteration_{it}/plot/trajectory_final.json')]
    if len(dirs)!=1:raise SystemExit(f'{id_}: no unique source JSON')
    src=dirs[0]; raw=archive.read(src)
    if hashlib.sha256(raw).hexdigest()!=by_path[src]['sha256']:raise SystemExit(f'{id_}: source hash mismatch')
    d=json.loads(raw)
    est=np.asarray(d['trajectory_est'],dtype=float)
    gt=np.asarray(d['trajectory_gt'],dtype=float)
    scaled, _=align(est,gt,True)
    if abs(scaled-float(r['ate_scaled_m']))>1e-7:raise SystemExit(f'{id_}: recomputed ATE mismatch')
    f=a.group/'trajectories_tum/part1'/Path(r['trajectory_file']).name
    if not f.is_file():raise SystemExit(f'{id_}: trajectory missing: {f}')
    traj=np.loadtxt(f,comments='#',ndmin=2)
    ids=np.asarray(d['trajectory_id'],dtype=int)
    est=np.asarray(d['trajectory_est'],dtype=float)
    if traj.shape!=(len(ids),8):raise SystemExit(f'{id_}: invalid shape {traj.shape}')
    if np.any(np.diff(traj[:,0])<=0):raise SystemExit(f'{id_}: timestamps not increasing')
    if not np.allclose(traj[:,1:4],est[:,:3,3],atol=1e-8,rtol=0):raise SystemExit(f'{id_}: translation mismatches source')
    rot=Rotation.from_quat(traj[:,4:8]).as_matrix()
    if not np.allclose(rot,est[:,:3,:3],atol=2e-7,rtol=0):raise SystemExit(f'{id_}: rotations mismatch source')
    seqs[r['sequence']]+=1
print('PASS: 30 rows, 30 hashed original JSONs, 30 valid TUM trajectories, recomputed ATE matches; counts:',seqs)
