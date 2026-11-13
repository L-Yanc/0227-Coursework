"""Verify the original Part 1 source package against supplied final trajectories."""
import argparse,subprocess,sys
from pathlib import Path
CODE=Path(__file__).resolve().parents[2]
GROUP=CODE.parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--archive',type=Path,required=True)
p.add_argument('--group',type=Path,default=GROUP)
a=p.parse_args()
subprocess.run([sys.executable,CODE/'scripts/part1/verify_part1.py','--archive',a.archive,'--group',a.group],check=True)
