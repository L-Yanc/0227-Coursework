"""Shared arguments for the four report-rendering entry points."""
import argparse,os,subprocess,sys
from pathlib import Path
CODE=Path(__file__).resolve().parents[2]
def arguments(description):
 p=argparse.ArgumentParser(description=description)
 p.add_argument('--out',type=Path,required=True)
 p.add_argument('--group',type=Path,default=CODE.parent)
 a=p.parse_args();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=True)
 os.environ.setdefault('MPLCONFIGDIR',str(a.out/'_plot_cache'))
 return a
def run(script,*args):
 subprocess.run([sys.executable,str(CODE/script),*[str(x) for x in args]],cwd=CODE,check=True)
