#!/usr/bin/env python3
"""Apply the combined diff to pristine tagged files in a disposable directory."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from layout import CODE, AUDIT, save

REPO=Path(__file__).resolve().parents[2]
BASE='302cf18bb15a7f9dd5363e1f7a75f9bb648ad72b'


def verify(pyslam):
    patch=REPO/'patches/pyslam_changes.patch'
    names=[line.split()[2][2:] for line in patch.read_text().splitlines() if line.startswith('diff --git ')]
    if len(set(names))!=len(names):raise ValueError('Duplicate paths in combined diff')
    forbidden={'bash_utils.sh','scripts/install_extra.sh','scripts/native_bundle.py'}
    if forbidden.intersection(names):raise ValueError('Machine-specific installation changes leaked into research diff')
    if True:
        fixtures=AUDIT/'patch_fixtures';fixtures.mkdir(parents=True,exist_ok=True)
        target=Path(tempfile.mkdtemp(prefix='apply_',dir=fixtures))
        subprocess.run(['git','init','-q',str(target)],check=True)
        for name in names:
            if Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('Invalid patch path')
            blob=subprocess.run(['git','show',f'{BASE}:{name}'],cwd=pyslam,capture_output=True)
            if blob.returncode==0:
                p=target/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(blob.stdout)
                mode=subprocess.check_output(['git','ls-tree',BASE,'--',name],cwd=pyslam,text=True).split()[0]
                p.chmod(0o755 if mode=='100755' else 0o644)
        subprocess.run(['git','apply','--check','--whitespace=error-all',str(patch)],cwd=target,check=True,capture_output=True)
        subprocess.run(['git','apply',str(patch)],cwd=target,check=True,capture_output=True)
        hashes={};installed_comparison={}
        for name in names:
            p=target/name
            if p.suffix=='.py':ast.parse(p.read_text(),filename=name)
            elif p.suffix=='.json':json.loads(p.read_text())
            hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
            installed=pyslam/name
            installed_comparison[name]='matches' if installed.is_file() and hashlib.sha256(installed.read_bytes()).hexdigest()==hashes[name] else 'different' if installed.is_file() else 'not installed'
            if name in ['pyslam/slam/initializer.py','pyslam/slam/local_mapping.py','pyslam/slam/tracking.py','pyslam/utilities/logging.py','pyslam/depth_estimation/pred_depth.py','pyslam/depth_estimation/part4_policy.py'] and installed_comparison[name]!='matches':
                raise ValueError('Part 3/4 core differs from installed working implementation: '+name)
    return {'base_revision':BASE,'patch_sha256':hashlib.sha256(patch.read_bytes()).hexdigest(),
            'apply_check_passed':True,'syntax_check_passed':True,'files':hashes,
            'fixture_location':'external audit patch_fixtures directory','installed_comparison':installed_comparison,
            'runtime_note':'This checks pristine tagged source application and Python syntax. Full clean-install SLAM execution is not claimed.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pyslam',type=Path,required=True)
    p.add_argument('--out',type=Path,default=REPO/'patches/validation.json');a=p.parse_args()
    result=verify(a.pyslam);save(a.out,json.dumps(result,indent=2)+'\n')
    print(f'Combined diff applies to {BASE[:7]}; {len(result["files"])} files passed syntax/JSON checks.')


if __name__=='__main__':main()
