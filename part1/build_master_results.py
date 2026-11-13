#!/usr/bin/env python3
"""Build reproducible per-run COMP0227 SLAM results from pySLAM evaluations.

Examples:
  python build_master_results.py --zip scene_part1_results.zip --output master_results.csv
  python build_master_results.py --results-root /home/ad/scene/COMP0227_26-27/pyslam/results --output master_results.csv --timestamps-root /home/ad/scene/COMP0227_26-27/pyslam

Requires numpy. Missing metrics remain empty, NEVER inferred from aggregates.
For each run, ATE uses the matched estimated/GT poses in plot/trajectory_final.json.
RPE uses the supplied saved JSON when available; otherwise is computed only when
real frame timestamps can be found (same 1 s, 0.06 s tolerance, contiguous pairs).
TUM trajectories exported from JSON contain the GT-matched estimated poses;
check against the full saved trajectory before final submission.
"""
import argparse
import bisect
import csv
import io
import json
import re
from pathlib import Path
from zipfile import ZipFile
import numpy as np

BATCHES = {
 'eval_2026_10_30-15_42_06': ('KITTI 06','monocular','cpp','baseline'),
 'eval_2026_10_30-15_57_04': ('KITTI 06','monocular','python','baseline'),
 'eval_2026_10_31-18_39_58': ('fr3','monocular','cpp','baseline'),
 'eval_2026_10_31-19_17_20': ('fr3','rgbd','cpp','baseline'),
 'eval_2026_11_02-17_00_25': ('room0','monocular','cpp','baseline'),
 'eval_2026_11_02-17_26_25': ('room0','rgbd','cpp','baseline'),
 'eval_2026_11_02-18_35_51': ('fr3','monocular','cpp','map-depth'),
 'eval_2026_11_02-18_38_13': ('fr3','rgbd','cpp','map-depth'),
 'eval_2026_11_04-19_08_08': ('fr3','monocular','cpp','map-depth'),
 'eval_2026_11_04-19_36_33': ('fr3','rgbd','cpp','map-depth'),
}
HEADERS = ['run_id','sequence','method','backend','feature','experiment_group','batch','run_number',
           'settings','ate_unscaled_m','ate_scale_aligned_m','fitted_scale','rpe_rmse_m',
           'rpe_alignment','rpe_delta_s','rpe_valid_pairs','fraction_tracked','fraction_lost',
           'tracking_time_mean_ms','tracking_time_median_ms','map_depth_mae_m',
           'map_depth_rmse_m','map_depth_absrel','source_run','trajectory_tum_file', 'warnings']

class Source:
 def __init__(self, root=None, zipfile=None):
  self.z=ZipFile(zipfile) if zipfile else None
  self.root=Path(root) if root else None
  self.names=sorted(self.z.namelist() if self.z else [p.relative_to(self.root).as_posix() for p in self.root.rglob('*') if p.is_file()])
 def read(self,name):
  try: return self.z.read(name).decode('utf-8') if self.z else (self.root/name).read_text()
  except (KeyError,FileNotFoundError):return None
 def json(self,name):
  s=self.read(name);return json.loads(s) if s is not None else None

def align(est,gt,scale):
 """World-position least-squares Umeyama alignment of estimated camera centres to GT."""
 a,b=est[:,:3,3],gt[:,:3,3]
 ac,bc=a.mean(axis=0),b.mean(axis=0)
 A=a-ac; B=b-bc
 U,S,Vt=np.linalg.svd((B.T@A)/len(a))
 D=np.eye(3); D[-1,-1]=np.sign(np.linalg.det(U@Vt))
 R=U@D@Vt
 s=float(np.trace(np.diag(S)@D)/(np.sum(A*A)/len(a))) if scale else 1.
 fitted=b.mean(axis=0) - s*R@ac
 diff=(s*(R@a.T)).T+fitted-b
 return float(np.sqrt(np.mean(np.sum(diff**2,axis=1)))),s

def timestamps_path(seq,root):
 if not root:return None
 p=Path(root)
 files={'KITTI 06':'data/videos/kitti06/times.txt','fr3':'data/tum/rgbd_dataset_freiburg3_long_office_household/associations.txt','room0':'data/replica/room0/times.txt'}
 f=p/files[seq];return f if f.exists() else None

def timestamp_values(path):
 arr=[]
 for line in path.read_text().splitlines():
  line=line.strip()
  if line and not line.startswith('#'):arr.append(float(line.split()[0]))
 if not arr or any(y<=x for x,y in zip(arr,arr[1:])):raise ValueError('bad/unsorted timestamps in '+str(path))
 return np.array(arr)

def rpe_metric(est,gt,ids,times,scale):
 """Matches coursework_rpe.py: 1-s translational RPE and no gaps."""
 s=align(est,gt,scale)[1]
 ts=times[ids]
 errors=[]
 for idx,i in enumerate(ids):
  loc=bisect.bisect_left(ts,ts[idx]+1.,lo=idx+1)
  candidates=[k for k in (loc-1,loc) if idx<k<len(ids)]
  if not candidates:continue
  jdx=min(candidates,key=lambda k:abs(ts[k]-(ts[idx]+1.)))
  if abs(ts[jdx]-ts[idx]-1.)>0.06:continue
  if ids[jdx]-i != jdx-idx:continue
  # Relative translations in each starting camera's coordinate system.
  a=gt[idx,:3,:3].T@(gt[jdx,:3,3]-gt[idx,:3,3])
  b=s*est[idx,:3,:3].T@(est[jdx,:3,3]-est[idx,:3,3])
  errors.append(float(np.linalg.norm(b-a)))
 return (float(np.sqrt(np.mean(np.square(errors)))),len(errors)) if errors else (None,0)

def rotation_quaternion(R):
 """Numerically stable matrix-> quaternion, output qx qy qz qw."""
 q=np.empty(4);t=np.trace(R)
 if t>0:
  s=np.sqrt(t+1.)*2;q[3]=s/4;q[0]=(R[2,1]-R[1,2])/s;q[1]=(R[0,2]-R[2,0])/s;q[2]=(R[1,0]-R[0,1])/s
 else:
  k=int(np.argmax(np.diag(R)));j=(k+1)%3;l=(k+2)%3
  s=np.sqrt(max(0,1+R[k,k]-R[j,j]-R[l,l]))*2
  q[k]=s/4;q[3]=(R[l,j]-R[j,l])/s;q[j]=(R[j,k]+R[k,j])/s;q[l]=(R[l,k]+R[k,l])/s
 return q/np.linalg.norm(q)

def floatstr(x):return '' if x is None else f'{x:.10g}'

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 src=ap.add_mutually_exclusive_group(required=True)
 src.add_argument('--zip',help='ZIP of results/eval_... folders')
 src.add_argument('--results-root',help='pySLAM results/ directory')
 ap.add_argument('--timestamps-root',help='pySLAM root containing data/videos/, data/tum/, data/replica/')
 ap.add_argument('--output',default='master_results.csv')
 ap.add_argument('--trajectories-dir',default=None,help='Export GT-matched trajectories as timestamped TUM files when timestamps available')
 args=ap.parse_args()
 source=Source(root=args.results_root,zipfile=args.zip)
 groups={}
 for f in source.names:
  if not f.endswith('/plot/trajectory_final.json'):continue
  parts=f.split('/')
  try: bi=next(i for i,p in enumerate(parts) if p.startswith('eval_'))
  except StopIteration:continue
  batch=parts[bi]
  if batch not in BATCHES:continue
  groups[(batch,parts[bi+3])]=('/'.join(parts[:bi+4]),parts[bi+1],parts[bi+2])
 rows=[]
 for (batch,it),(run,preset,dataset) in sorted(groups.items()):
  if not re.fullmatch(r'iteration_\d+',it):continue
  seq,method,backend,group=BATCHES[batch]
  run_id=f'{batch}_{it}'
  d=source.json(run+'/plot/trajectory_final.json')
  if not d:continue
  est=np.asarray(d['trajectory_est'],dtype=float);gt=np.asarray(d['trajectory_gt'],dtype=float)
  ids=np.asarray(d['trajectory_id'],dtype=int)
  issues=[]
  if est.shape!=gt.shape or len(ids)!=len(est) or est.shape[1:]!=(4,4):raise ValueError('Pose shape mismatch: '+run)
  unscaled,_=align(est,gt,False);scaled,s=align(est,gt,True)
  info={}
  for line in (source.read(run+'/other_metrics_info.txt') or '').splitlines():
   if ':' in line:
    a,b=line.split(':',1);info[a.strip()]=b.strip()
  rpe=source.json(run+'/coursework_rpe.json')
  ts_path=timestamps_path(seq,args.timestamps_root)
  ts=None
  if ts_path:
   ts=timestamp_values(ts_path)
   if min(ids)<0 or max(ids)>=len(ts):issues.append('timestamps index mismatch');ts=None
  if not rpe and ts is not None:
   val,n=rpe_metric(est,gt,ids,ts,True)
   if val is not None:rpe={'rpe_rmse_m':val,'valid_pairs':n,'scale_alignment':'similarity','delta_target_s':1.}
  if not rpe:issues.append('RPE missing: supply original frame timestamps')
  depth=source.json(run+'/map_depth_scores.json') or {}
  if not depth:issues.append('map-depth unavailable') if seq!='KITTI 06' else None
  if seq=='KITTI 06':issues.append('KITTI has no reference depth')
  if abs((rpe or {}).get('fitted_scale',s)-s)>0.01:issues.append('RPE/Ate scale disagreement')
  tumfile=''
  if args.trajectories_dir and ts is not None:
   out=Path(args.trajectories_dir);out.mkdir(parents=True,exist_ok=True)
   p=out/(run_id+'.tum');tumfile=str(p)
   with p.open('w') as f:
    f.write('# timestamp tx ty tz qx qy qz qw; GT-associated estimate subset\n')
    for fid,pose in zip(ids,est):
     q=rotation_quaternion(pose[:3,:3]);vals=[ts[fid],*pose[:3,3],*q]
     f.write(' '.join(f'{x:.12g}' for x in vals)+'\n')
  elif args.trajectories_dir:issues.append('trajectory export unavailable: timestamps missing')
  r={
   'run_id':run_id,'sequence':seq,'method':method,'backend':backend,'feature':preset,
   'experiment_group':group,'batch':batch,'run_number':int(it.split('_')[-1])+1,
   'settings':f'ORB2; {backend}; {method}; batch={group}',
   'ate_unscaled_m':floatstr(unscaled),'ate_scale_aligned_m':floatstr(scaled),
   'fitted_scale':floatstr(s),'rpe_rmse_m':floatstr((rpe or {}).get('rpe_rmse_m')),
   'rpe_alignment':(rpe or {}).get('scale_alignment',''),
   'rpe_delta_s':floatstr((rpe or {}).get('delta_target_s')),
   'rpe_valid_pairs':(rpe or {}).get('valid_pairs',''),
   'fraction_tracked':floatstr(float(info['num_tracked_frames'])/float(info['num_total_frames'])) if 'num_tracked_frames' in info and 'num_total_frames' in info else '',
   'fraction_lost':floatstr(float(info['num_lost_frames'])/float(info['num_total_frames'])) if 'num_lost_frames' in info and 'num_total_frames' in info else '',
   'tracking_time_mean_ms':info.get('mean_tracking_ms',''),
   'tracking_time_median_ms':info.get('median_tracking_ms',''),
   'map_depth_mae_m':floatstr(depth.get('mae_m')),'map_depth_rmse_m':floatstr(depth.get('rmse_m')),
   'map_depth_absrel':floatstr(depth.get('absrel')),'source_run':run,
   'trajectory_tum_file':tumfile,'warnings':'; '.join(issues)}
  rows.append(r)
 out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=HEADERS);w.writeheader();w.writerows(rows)
 print('Generated',out,'with',len(rows),'run rows')
 from collections import Counter
 print('Coverage:',dict(Counter((r['sequence'],r['method'],r['backend'],r['experiment_group']) for r in rows)))
 for key in ['ate_unscaled_m','ate_scale_aligned_m','fitted_scale','rpe_rmse_m','fraction_tracked','fraction_lost','tracking_time_mean_ms','trajectory_tum_file']:
  print(f'{key}: {sum(bool(r[key]) for r in rows)}/{len(rows)}')
 missing=[b for b in BATCHES if not any(r['batch']==b for r in rows)]
 if missing:print('Batches not present in inputs:', ', '.join(missing))
 if source.z:source.z.close()

if __name__=='__main__':main()
