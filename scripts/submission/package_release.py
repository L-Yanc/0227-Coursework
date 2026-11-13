#!/usr/bin/env python3
"""Build reviewable Moodle archives from the saved submission tree; no experiments."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

REPO=Path(__file__).resolve().parents[2]


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def archive(path,entries):
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
        for source,name in sorted(entries,key=lambda x:x[1]):
            info=zipfile.ZipInfo(name,date_time=(2026,11,13,0,0,0))
            info.external_attr=(source.stat().st_mode&0o777)<<16
            info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,source.read_bytes(),compresslevel=1)
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:raise ValueError('ZIP integrity check failed')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--report-tools',type=Path,help='Optional report scripts kept outside GitHub at the user request')
    p.add_argument('--code-only',action='store_true')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    checked=json.loads((REPO/'patches/validation.json').read_text())
    patch=REPO/'patches/coursework_changes.patch'
    if not checked.get('apply_check_passed') or checked['patch_sha256']!=sha(patch):raise ValueError('Combined patch validation missing or stale')
    sources=[]
    for name in ['README.md','README_Part1.md','README_part2.md','README_part4.md','requirements-analysis.txt','run-part4','SETUP.md','MISSING_INPUTS.md','.gitignore']:
        source=REPO/name
        if source.is_file():sources.append((source,name))
    for dirname in ['scripts','configs','patches']:
        for source in (REPO/dirname).rglob('*'):
            if source.is_file() and source.name!='.DS_Store' and '__pycache__' not in source.parts and source.suffix not in ['.pyc','.zip']:
                sources.append((source,str(source.relative_to(REPO))))
    if a.report_tools:
        for source in a.report_tools.rglob('*'):
            if source.is_file() and '__pycache__' not in source.parts and 'generated' not in source.parts:
                sources.append((source,'report_tools/'+str(source.relative_to(a.report_tools))))
    code=a.out/'code_draft.zip';archive(code,sources)
    summary={'code_archive':code.name,'code_sha256':sha(code),'code_files':len(sources),
             'combined_patch_checked':True,'report_scripts_included':bool(a.report_tools),
             'complete_submission':False,'reason':'Final report/reproduction mapping is external; results still require the checks recorded in MISSING_INPUTS.md.'}
    if not a.code_only:
        subprocess.run([sys.executable,str(REPO/'scripts/submission/validate.py'),'--allow-missing'],check=True)
        status=json.loads((REPO/'Results/submission_validation.json').read_text())
        result=a.out/('results.zip' if status['results_ready'] else 'results_partial.zip')
        entries=[]
        for dirname in ['Results','trajectories_tum','Part 2 Results']:
            entries.extend((source,str(source.relative_to(REPO))) for source in (REPO/dirname).rglob('*') if source.is_file() and source.name!='.DS_Store')
        archive(result,entries)
        summary.update(results_archive=result.name,results_sha256=sha(result),results_rows=status['rows'],
                       valid_trajectories=status['valid_trajectories'],missing_trajectories=len(status['missing_trajectories']))
    (a.out/'manifest.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
