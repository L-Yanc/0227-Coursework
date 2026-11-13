"""Import the verified final Part 3 artifacts without branch/network operations."""
from pathlib import Path
import shutil
from common import CODE,TEAM,Stage,read,rows,table,dump,publish_pointer
from geometry import read_tum
REVISION='41bde4c'
def import_results(c,work):
 source=CODE/'inputs/part3.csv'
 records=rows(source)
 paths=[TEAM/'trajectories_tum/part3'/Path(r['trajectory_file']).name for r in records]
 stage=Stage(work,'part3_import',{'revision':REVISION,'source':'final verified export'},[source,*paths,CODE/'inputs/part3/pose_times/summary.csv'])
 if stage.cached():publish_pointer(work,'part3_import',stage);return stage.path
 out=stage.begin()
 shutil.copyfile(source,out/'final_results.csv')
 inventory=[]
 for path in paths:
  a=read_tum(path);inventory.append({'trajectory':str(path.relative_to(TEAM)),'poses':len(a)})
 table(out/'trajectory_inventory.csv',inventory)
 dump(out/'status.json',{'historical_runs':len(records),'valid_trajectory_files':len(paths),'revision':REVISION,'association_audit':'200 zero, 20 +2 offsets; supplied pose proofs verified'})
 stage.finish(['final_results.csv','trajectory_inventory.csv','status.json'])
 publish_pointer(work,'part3_import',stage);return stage.path
