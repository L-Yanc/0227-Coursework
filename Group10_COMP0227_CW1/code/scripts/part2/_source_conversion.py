#!/usr/bin/env python3
"""Convert the seven saved Part 2 SLAM runs and score their original poses.

No SLAM or network inference is run. Requires the original sequence timestamps.
The full KITTI-format poses are preserved in the source ZIP. Upstream eval_ate
zips full frame IDs with GT-associated poses; those IDs must be remapped if GT
association dropped initial poses. Every scored pose must match a unique full
pose. A trailing full-ID suffix is recoverable only when all remaining input
frames have a saved pose.
"""
import argparse
import os
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import numpy as np
from scipy.spatial import cKDTree

CODE = Path(__file__).resolve().parents[2]
REPO = Path(os.environ['CW1_IMPORT_ROOT']).resolve()
sys.path.insert(0, str(CODE/'scripts/part4'))
sys.path.insert(0, str(CODE/'scripts/shared'))
from geometry import align, write_tum, read_tum
from coursework_rpe import evaluate as rpe, load_timestamps
from scoring import FIELDS


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    stamps=REPO/'Results/part2/timestamps'
    parser.add_argument('--kitti-times',type=Path,default=stamps/'kitti06.txt')
    parser.add_argument('--tum-associations',type=Path,default=stamps/'tum_fr3.txt')
    parser.add_argument('--replica-times',type=Path,default=stamps/'replica_room0.txt')
    args=parser.parse_args()
    timepaths={'KITTI 06':args.kitti_times,'TUM fr3':args.tum_associations,
               'Replica room0':args.replica_times}
    times={name:load_timestamps(p) for name,p in timepaths.items()}
    source=REPO/'Part 2 Results/part2_results.zip'
    out=REPO/'Results/part2';out.mkdir(parents=True,exist_ok=True)
    records=[];provenance=[]
    with zipfile.ZipFile(source) as z:
        for name in sorted(n for n in z.namelist() if n.endswith('/plot/trajectory_final.json')):
            parts=Path(name).parts
            folder='/'.join(parts[:-2]);batch=parts[1];iteration=parts[-3]
            seq=('TUM fr3' if 'freiburg' in name else 'Replica room0' if 'room0' in name else 'KITTI 06')
            method=('monocular' if batch.endswith('15_01_39') else 'rgbd' if batch.endswith('21_09_49') else 'pseudo_rgbd')
            j=json.loads(z.read(name));ids=np.asarray(j['trajectory_id'],int)
            matched=np.asarray(j['trajectory_est'],float)
            raw=np.loadtxt(io.StringIO(z.read(folder+'/trajectory_final.txt').decode())).reshape(-1,3,4)
            full=np.repeat(np.eye(4)[None],len(raw),axis=0);full[:,:3,:]=raw
            if len(ids)!=len(matched) or not len(ids) or np.any(np.diff(ids)<=0):
                raise ValueError('Invalid saved frame IDs: '+name)
            if len(full)<len(matched):raise ValueError('Too many matched poses: '+name)
            distances,indices=cKDTree(full[:,:3,:].reshape(len(full),12)).query(matched[:,:3,:].reshape(len(matched),12),k=2)
            matched_indices=indices[:,0]
            if np.any(distances[:,0]>1e-8) or np.any(distances[:,1]<=1e-8) or np.any(np.diff(matched_indices)<=0):
                raise ValueError('Scored poses do not map uniquely and in order to full poses: '+name)
            suffix=np.arange(ids[-1]+1,len(times[seq]))
            if len(suffix)!=len(full)-len(ids):
                raise ValueError('Cannot certify trailing frame timestamps: '+name)
            fullids=np.r_[ids,suffix]
            if fullids.min()<0 or fullids.max()>=len(times[seq]):raise ValueError('Frame IDs outside sequence')
            rid=f'{batch}_{iteration}'
            rel=f'trajectories_tum/part2/{rid}.tum';traj=REPO/rel
            traj.parent.mkdir(parents=True,exist_ok=True)
            write_tum(traj,times[seq][fullids],full);read_tum(traj)
            metadata={}
            for line in z.read(folder+'/other_metrics_info.txt').decode().splitlines():
                if ':' in line:
                    key,value=line.split(':',1)
                    try:metadata[key.strip()]=float(value)
                    except ValueError:pass
            scoring=out/'source'/rid;scoring.mkdir(parents=True,exist_ok=True)
            original=scoring/'trajectory_final_original.json';original.write_bytes(z.read(name))
            corrected=dict(j);corrected['trajectory_id']=fullids[matched_indices].tolist()
            jsonpath=scoring/'trajectory_final.json';jsonpath.write_text(json.dumps(corrected)+'\n')
            gt=np.asarray(j['trajectory_gt'],float)
            x=matched[:,:3,3];y=gt[:,:3,3]
            scale,rotation,translation=align(x,y,True)
            _,rigid_r,rigid_t=align(x,y,False)
            rmse=lambda a:float(np.sqrt(np.mean(np.sum(a*a,axis=1))))
            rpe_result=rpe(jsonpath,timepaths[seq],1.,.12,True,True)
            total=metadata['num_total_frames']
            row=dict.fromkeys(FIELDS,'')
            row.update(run_id=rid,sequence=seq,method=method,
                       settings=json.dumps({'source_part':'part2','backend':'cpp','feature':'ORB2','sensor':'mono' if method=='monocular' else 'rgbd','saved_depth':'dav2b' if method=='pseudo_rgbd' else None,'scoring':'original JSON pose/GT associations; scored frame IDs mapped to identical full poses; full trajectory exported separately'},sort_keys=True),
                       run_number=int(iteration.rsplit('_',1)[1])+1,
                       ate_unscaled_m=rmse((rigid_r@x.T).T+rigid_t-y),
                       ate_scaled_m=rmse((scale*(rotation@x.T)).T+translation-y),fitted_scale=scale,
                       rpe_rmse_m=rpe_result['rpe_rmse_m'],
                       fraction_tracked=metadata['num_tracked_frames']/total,
                       fraction_lost=metadata['num_lost_frames']/total,
                       time_per_frame_ms=metadata.get('mean_tracking_ms',''),trajectory_file=rel)
            records.append(row)
            detail={'run_id':rid,'zip_member':name,'json_sha256':digest(jsonpath),
                    'full_poses':len(full),'scored_poses':len(ids),'source_frame_ids':fullids.tolist(),
                    'suffix_verification':'remaining input-frame count equals remaining full-pose count; full frame-ID prefix saved by upstream eval_ate',
                    'scored_pose_indices_in_full_trajectory':matched_indices.tolist(),
                    'scoring_frame_ids_remapped':not np.array_equal(ids,fullids[matched_indices]),
                    'frame_id_note':'Upstream eval_ate receives full frame IDs but GT-associated poses. Match poses to full output before applying input timestamps; TUM association removed two initial poses.',
                    'timestamps_sha256':digest(timepaths[seq]),'trajectory_sha256':digest(traj),
                    'metrics':metadata,'rpe':rpe_result,
                    'map_depth_mae_note':'Not recomputed here. No sensor depth exists for KITTI.'}
            (scoring/'provenance.json').write_text(json.dumps(detail,indent=2)+'\n')
            provenance.append(detail)
    if len(records)!=7:raise ValueError(f'Expected seven archived SLAM runs, got {len(records)}')
    with (out/'slam_results.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();writer.writerows(records)
    (out/'conversion_manifest.json').write_text(json.dumps({'source_zip_sha256':digest(source),'runs':provenance},indent=2)+'\n')
    print('Converted and scored all seven saved Part 2 SLAM runs. No experiments rerun.')


if __name__=='__main__':main()
