"""Run submission and Part 4 checks from one consistent test root."""
import argparse,os,subprocess,sys
from pathlib import Path
CODE=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--suite',choices=['all','submission','part4'],default='all')
a=p.parse_args()
for name in (['submission','part4'] if a.suite=='all' else [a.suite]):
 env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
 env['PYTHONPATH']=os.pathsep.join([str(CODE/'scripts/part4'),str(CODE/'scripts/shared'),env.get('PYTHONPATH','')])
 subprocess.run([sys.executable,'-m','unittest','discover','-s',str(CODE/'tests'/name),'-v'],cwd=CODE/'scripts/part4',env=env,check=True)
