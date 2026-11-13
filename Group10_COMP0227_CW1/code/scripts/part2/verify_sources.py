"""Recover the original seven Part 2 trajectories in a fresh external fixture."""
import argparse,os,subprocess,sys,zipfile
from pathlib import Path
CODE=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--archive',type=Path,required=True)
p.add_argument('--timestamps',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=False)
import shutil
(a.out/'Part 2 Results').mkdir()
shutil.copy2(a.archive,a.out/'Part 2 Results/part2_results.zip')
shutil.copytree(a.timestamps,a.out/'Results/part2/timestamps')
env=dict(os.environ,CW1_IMPORT_ROOT=str(a.out.resolve()))
subprocess.run([sys.executable,CODE/'scripts/part2/_source_conversion.py'],env=env,check=True)
