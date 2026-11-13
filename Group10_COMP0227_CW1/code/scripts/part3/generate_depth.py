"""Plan historical DAV2-large depth generation. Execute only when requested."""
import argparse,json,os,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--pyslam',type=Path,required=True)
p.add_argument('--datasets',type=Path,required=True)
p.add_argument('--environment',default='depth')
p.add_argument('--pixi',default='pixi')
p.add_argument('--execute',action='store_true')
a=p.parse_args();plan=[]
code=Path(__file__).resolve().parents[2]
for seq,settings,scene in [('rgbd_dataset_freiburg3_long_office_household',a.pyslam/'settings/TUM3.yaml','indoor'),('replica_room0_tum',a.pyslam/'settings/REPLICA.yaml','indoor'),('kitti06_tum',code/'configs/part3/KITTI06_depth.yaml','outdoor')]:
 command=[a.pixi,'run','-e',a.environment,'depth-prediction','--method','DEPTH_ANYTHING_V2','--scene',scene,'--tum',str(a.datasets/seq),'--settings',str(settings),'--save','dav2','--headless']
 plan.append(command)
 if a.execute:subprocess.run(command,cwd=a.pyslam,check=True)
print(json.dumps({'execute':a.execute,'model':'upstream DepthEstimatorDepthAnythingV2 defaults to vitl (large); indoor/outdoor metric checkpoints','commands':plan},indent=2))
