#!/usr/bin/env python3
"""Reproduce the configurations recorded in Part 3. Dry-run unless --execute.

Historical scores were obtained on the teammate's machines. This command records
new runs under new output folders; it never replaces the historical CSV.
"""
import argparse
from collections import Counter
import csv
import json
import os
from pathlib import Path
import shlex
import subprocess

REPO=Path(__file__).resolve().parents[2]


def parameters(tag):
    if tag.startswith('mono') or tag=='A':return '',100,0
    if tag=='E1':return 'E1',100,0
    if tag in ['E1s50','E1s80']:return 'E1',int(tag[3:]),0
    if tag=='B80E1':return 'B+E1',80,0
    if tag=='B80u10':return 'B',80,10
    if tag in ['B50','B80','B100']:return 'B',int(tag[1:]),0
    raise ValueError('Unknown historical configuration '+tag)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pyslam',type=Path,default=Path(os.environ.get('PYSLAM_ROOT',REPO.parent.parent/'_work/external/pyslam')))
    p.add_argument('--datasets',type=Path,default=Path(os.environ.get('CW1_DATASETS',REPO.parent.parent/'_work/datasets')),
                   help='TUM-format folders: rgbd_dataset_freiburg3_long_office_household, replica_room0_tum, kitti06_tum')
    p.add_argument('--config',action='append',help='Limit to named configurations, e.g. fr3_B80E1; repeatable')
    p.add_argument('--runs',type=int,help='Override historical repetition counts for a new experiment')
    p.add_argument('--depth-name',default='dav2',help='Historical association suffix; Part 2 owner used dav2b separately')
    p.add_argument('--pixi',default=os.environ.get('CW1_PIXI','pixi'))
    p.add_argument('--environment',default=os.environ.get('CW1_SLAM_ENV','default'))
    p.add_argument('--out',type=Path,default=REPO.parent.parent/'_work/part3')
    p.add_argument('--execute',action='store_true')
    a=p.parse_args()
    with (REPO/'inputs/part3/runs.csv').open() as f:counts=Counter((r['config'],r['mode'],r['seq']) for r in csv.DictReader(f))
    plan=[]
    for (config,mode,sequence),count in sorted(counts.items()):
        if a.config and config not in a.config:continue
        short,tag=config.split('_',1);method,sigma,until=parameters(tag)
        factor={'fr3':5000,'room0':6553.5,'kitti':256}[short]
        settings=(a.pyslam/'settings'/('TUM3.yaml' if short=='fr3' else 'REPLICA.yaml')
                  if short!='kitti' else REPO/'configs/part3/KITTI06_depth.yaml')
        dataset=a.datasets/sequence
        associations=f'associations_{a.depth_name}.txt'
        sensor='mono';extra=[]
        if tag=='A':
            sensor='rgbd' if mode in ['rgbd','pseudo-rgbd','ORB2'] else 'mono'
            if mode in ['pseudo-rgbd','ORB2']:extra=['--associations',associations]
        argv=[a.pixi,'run','-e',a.environment,'slam-evaluation','--tum',str(dataset),
              '--settings',str(settings),'--sensor',sensor,'--features','ORB2','--runs',str(a.runs or count),'--jobs','1',*extra]
        env={'CW1_METHOD':method,'CW1_SIGMA_PCT':str(sigma),'CW1_DEPTH_UNTIL':str(until),
             'CW1_DEPTH_FACTOR':str(factor),'CW1_PRED_DEPTH':str(dataset/associations) if method else '',
             'CW1_LOG_POINTS':str(a.out/'pointlogs'/config),'CW1_SAVE_MAP':'1','PYSLAM_USE_CPP':'true'}
        item={'config':config,'mode':mode,'runs':a.runs or count,'argv':argv,'env':env};plan.append(item)
        if not a.execute:continue
        if not dataset.is_dir() or not settings.is_file():raise SystemExit('Missing dataset/settings for '+config)
        if (method or extra) and not (dataset/associations).is_file():raise SystemExit('Missing saved predicted-depth associations for '+config)
        a.out.mkdir(parents=True,exist_ok=True);(a.out/'logs').mkdir(exist_ok=True)
        before=set((a.pyslam/'results').glob('eval_*'));childenv=dict(os.environ);childenv.update(env)
        with (a.out/'logs'/f'{config}_{mode}.log').open('w') as log:
            subprocess.run(argv,cwd=a.pyslam,env=childenv,stdout=log,stderr=subprocess.STDOUT,check=True)
        created=set((a.pyslam/'results').glob('eval_*'))-before
        if len(created)!=1:raise RuntimeError('Expected one new evaluation folder; inspect logs')
        with (a.out/'part3_folders.txt').open('a') as f:f.write(config+' '+shlex.quote(str(created.pop()))+'\n')
    if not plan:raise SystemExit('No matching configurations')
    print(json.dumps({'execute':a.execute,'attempts':sum(x['runs'] for x in plan),'configurations':plan},indent=2))


if __name__=='__main__':main()
