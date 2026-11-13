#!/usr/bin/env python3
"""Plan the six five-run Part 1 baselines. Runs only with --execute."""
import argparse
import json
import os
from pathlib import Path
import subprocess

REPO=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pyslam',type=Path,default=Path(os.environ.get('PYSLAM_ROOT',REPO/'external/pyslam')))
    p.add_argument('--tum',type=Path,default=Path(os.environ.get('CW1_TUM_FR3',REPO/'datasets/rgbd_dataset_freiburg3_long_office_household')))
    p.add_argument('--replica',type=Path,default=Path(os.environ.get('CW1_REPLICA_ROOM0',REPO/'datasets/Replica/room0')))
    p.add_argument('--pixi',default=os.environ.get('CW1_PIXI','pixi'))
    p.add_argument('--environment',default=os.environ.get('CW1_SLAM_ENV','default'))
    p.add_argument('--runs',type=int,default=5)
    p.add_argument('--out',type=Path,default=REPO/'work/part1')
    p.add_argument('--execute',action='store_true')
    a=p.parse_args();plan=[]
    for name,cpp,sensor in [('kitti_cpp',True,'mono'),('kitti_python',False,'mono'),('tum_mono',True,'mono'),('tum_rgbd',True,'rgbd'),('replica_mono',True,'mono'),('replica_rgbd',True,'rgbd')]:
        extra=[];config=None
        if name.startswith('tum'):
            extra=['--tum',str(a.tum),'--settings',str(a.pyslam/'settings/TUM3.yaml'),'--sensor',sensor]
        elif name.startswith('replica'):
            config=json.loads((REPO/f'configs/part1/coursework_replica_{sensor}.json').read_text())
            config['dataset_base_path']=str(a.replica.parent)
            config['datasets'][0]['name']=a.replica.name
            extra=['--config-file',str(a.out/f'{name}.json')]
        argv=[a.pixi,'run','-e',a.environment,'slam-evaluation','--features','ORB2','--runs',str(a.runs),'--jobs','1',*extra]
        plan.append({'name':name,'cpp':cpp,'argv':argv,'config':config})
        if a.execute:
            a.out.mkdir(parents=True,exist_ok=True)
            if config:(a.out/f'{name}.json').write_text(json.dumps(config,indent=2)+'\n')
            env=dict(os.environ);env['PYSLAM_USE_CPP']='true' if cpp else 'false'
            for key in ['CW1_METHOD','CW1_PRED_DEPTH','CW1_LOG_POINTS']:env.pop(key,None)
            with (a.out/f'{name}.log').open('w') as f:subprocess.run(argv,cwd=a.pyslam,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    print(json.dumps({'execute':a.execute,'attempts':6*a.runs,'plan':plan},indent=2))


if __name__=='__main__':main()
