#!/usr/bin/env python3
"""Package code/ only, verify ZIP hashes and preserve every previous archive."""
import argparse,io,json,subprocess,sys,zipfile,hashlib,tempfile
from pathlib import Path
from layout import CODE,GROUP,AUDIT,sha,save
TOP={'scripts','configs','patches','reference','inputs','protocols','tests','report_assets'}
ROOT={'README.md','README_part1.md','README_part2.md','README_part3.md','README_part4.md','requirements-analysis.txt','run-part4'}
SUFFIX={'.py','.md','.csv','.json','.yaml','.yml','.txt','.patch','.diff','.png','.sh','.toml','.lock','.html','.npz','.tex'}
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--out',type=Path,default=GROUP)
 p.add_argument('--audit',type=Path,default=AUDIT)
 p.add_argument('--code-only',action='store_true')
 a=p.parse_args()
 check=json.loads((CODE/'patches/validation.json').read_text())
 if not check.get('apply_check_passed') or check['patch_sha256']!=sha(CODE/'patches/pyslam_changes.patch'):
  raise ValueError('Final combined patch validation is missing or stale')
 if not a.code_only:
  subprocess.run([sys.executable,CODE/'scripts/submission/validate.py','--group',a.out,'--output',a.audit/'results_validation.json'],check=True)
 entries=[]
 for source in sorted(CODE.rglob('*')):
  rel=source.relative_to(CODE)
  if source.is_symlink():raise ValueError('Symlink forbidden in code package: '+str(rel))
  if not source.is_file():continue
  if any(x in {'.git','.pixi','.venv','__pycache__','.pytest_cache'} for x in rel.parts) or source.name=='.DS_Store' or source.suffix in {'.pyc','.pyo'}:continue
  if (len(rel.parts)==1 and str(rel) not in ROOT) or (len(rel.parts)>1 and rel.parts[0] not in TOP) or (source.suffix not in SUFFIX and str(rel)!='run-part4'):
   raise ValueError('Not in code allowlist: '+str(rel))
  if source.suffix=='.npz' and rel.parent!=Path('inputs/part2_depth'):raise ValueError('Only saved keypoint evidence NPZs are allowed')
  if source.stat().st_size>5_000_000:raise ValueError('Review unexpectedly large code input: '+str(rel))
  entries.append((source,'code/'+rel.as_posix()))
 data=io.BytesIO()
 with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for source,name in entries:
   info=zipfile.ZipInfo(name,date_time=(2026,11,13,0,0,0))
   info.external_attr=(source.stat().st_mode&0o777)<<16
   info.compress_type=zipfile.ZIP_DEFLATED
   z.writestr(info,source.read_bytes())
 save(a.out/'code.zip',data.getvalue(),a.audit)
 fixtures=a.audit/'zip_fixtures';fixtures.mkdir(parents=True,exist_ok=True)
 fixture=Path(tempfile.mkdtemp(prefix='code_',dir=fixtures))
 hashes={}
 with zipfile.ZipFile(a.out/'code.zip') as z:
  if z.testzip() is not None:raise ValueError('ZIP CRC failure')
  assert len(z.namelist())==len(entries)
  for source,name in entries:
   content=z.read(name)
   if hashlib.sha256(content).hexdigest()!=sha(source):raise ValueError('ZIP/source mismatch '+name)
   dest=fixture/name
   if '..' in Path(name).parts or Path(name).is_absolute():raise ValueError('Unsafe entry')
   dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(content)
   dest.chmod(source.stat().st_mode&0o777)
   hashes[name]=sha(dest)
 manifest={'code_zip_sha256':sha(a.out/'code.zip'),'files':len(entries),'bytes':(a.out/'code.zip').stat().st_size,
  'source_hashes':hashes,'extraction_fixture':str(fixture),'zip_crc_passed':True,'all_entry_hashes_match':True,
  'contents':'code/ only; raw sequences/maps/weights/environments/Git/old packages excluded',
  'report_staged':False,'final_report_mapping':'Current draft: Tables I-VII and Figures 1-3; final approval pending'}
 save(a.audit/'package_validation.json',json.dumps(manifest,indent=2)+'\n',a.audit)
 print(json.dumps({k:manifest[k] for k in ['files','bytes','code_zip_sha256','zip_crc_passed','all_entry_hashes_match']},indent=2))
if __name__=='__main__':main()
