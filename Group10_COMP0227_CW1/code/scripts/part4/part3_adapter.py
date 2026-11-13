"""Environment contract for the real Part 3 patch (revision 94c47e1)."""
import os
import json
from common import ROOT,SLAM,Blocked,rows,dump

def configure(selected,depth_path,out,policy,factor):
    for key in list(os.environ):
        if key.startswith('CW1_'): del os.environ[key]
    if not selected: return
    p=selected['parameters']
    if p['method'] not in ('E1','B','B+E1') or not 0<p['sigma_pct']<=100:
        raise ValueError('Unsupported Part 3 configuration')
    for path in ['pyslam/depth_estimation/pred_depth.py','pyslam/depth_estimation/part4_policy.py']:
        if not (SLAM/path).exists(): raise Blocked('Apply patches/pyslam_changes.patch before running')
    manifest=out/'predicted_depth_manifest.json'
    entries=[]
    for path in sorted((depth_path/'png').glob('*.png')):
        meta=json.loads((depth_path/'raw_m'/(path.stem+'.json')).read_text())
        entries.append({'timestamp':meta['timestamp'],'path':str(path.resolve())})
    if not entries: raise Blocked('No predicted depth frames for Part 3')
    dump(manifest,entries)
    os.environ.update(CW1_METHOD=p['method'],CW1_SIGMA_PCT=str(p['sigma_pct']),
                      CW1_DEPTH_UNTIL=str(p.get('depth_until',0)),
                      CW1_PRED_DEPTH=str(manifest),
                      CW1_DEPTH_FACTOR=str(factor),CW1_LOG_POINTS=str(out/'point_logs'))
