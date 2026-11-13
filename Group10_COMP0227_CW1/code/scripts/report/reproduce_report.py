"""Render all report items through the same four per-part interfaces."""
import argparse,subprocess,sys,hashlib,json
from pathlib import Path
CODE=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--out',type=Path,default=CODE.parent.parent/'_assembly/report_assets/current_draft')
p.add_argument('--group',type=Path,default=CODE.parent)
a=p.parse_args();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=True)
for n in [1,2,3,4]:
 subprocess.run([sys.executable,CODE/f'scripts/report/part{n}.py','--out',a.out,'--group',a.group],check=True)
outputs={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in a.out.iterdir() if f.suffix in {'.png','.tex'}}
(a.out/'reproduction.json').write_text(json.dumps({'tables':7,'figures':3,'outputs':outputs,'no_new_experiments':True},indent=2)+'\n')
print('Rendered all seven tables and three figures.')
