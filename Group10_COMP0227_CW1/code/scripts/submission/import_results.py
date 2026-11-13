"""Validate/import any of the four source CSVs using a common interface."""
import argparse
from pathlib import Path
from build_results import build,encode,FIELDS,EXTRA
from layout import CODE,GROUP,AUDIT,save
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--part',type=int,choices=[1,2,3,4],required=True)
p.add_argument('--inputs',type=Path,default=CODE/'inputs')
p.add_argument('--group',type=Path,default=GROUP)
p.add_argument('--out',type=Path,help='Optional derived per-part CSV; original sources remain unchanged')
a=p.parse_args()
selected=[r for r in build(a.inputs,a.group) if r['source_part'].startswith('part'+str(a.part))]
if a.out:save(a.out,encode(selected,FIELDS+EXTRA))
print('Verified part',a.part,':',len(selected),'source rows; original IDs retained in source_run_id.')
