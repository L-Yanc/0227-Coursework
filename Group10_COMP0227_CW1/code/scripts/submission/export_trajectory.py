#!/usr/bin/env python3
"""Export TUM from a new run's original trajectory_source.json, without GT fitting."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'part4'))
from geometry import write_tum,read_tum


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    j=json.loads(a.source.read_text());times=j['timestamps'];poses=np.asarray(j['trajectory_est'])
    if len(times)!=len(poses) or len(j['trajectory_id'])!=len(times):raise ValueError('Source trajectory fields have different lengths')
    if a.output.exists():raise ValueError('Output already exists; preserve the original')
    a.output.parent.mkdir(parents=True,exist_ok=True);write_tum(a.output,times,poses);read_tum(a.output)
    print(f'Exported {len(times)} poses using original source timestamps.')


if __name__=='__main__':main()
