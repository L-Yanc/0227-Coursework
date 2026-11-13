"""Produce only our core overlay, relative to the unmodified Part 3 patch."""
from pathlib import Path
import difflib
import subprocess
import tempfile
from common import SLAM,SOURCE,Blocked

def build_core_patch():
    upstream=SOURCE.parents[1]/'tests/fixtures/part3_historical.diff'
    names=[line.split()[2].removeprefix('a/') for line in upstream.read_text().splitlines() if line.startswith('diff --git ')]
    names.append('pyslam/utilities/logging.py')
    with tempfile.TemporaryDirectory(prefix='part4_patch_base_') as temp:
        base=Path(temp)
        subprocess.run(['git','init','-q',str(base)],check=True)
        for name in names:
            result=subprocess.run(['git','show',f'HEAD:{name}'],cwd=SLAM,capture_output=True)
            if result.returncode==0:
                p=base/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(result.stdout)
        subprocess.run(['git','apply',str(upstream)],cwd=base,check=True,capture_output=True)
        patch=[]
        for name in ['pyslam/slam/initializer.py','pyslam/depth_estimation/pred_depth.py','pyslam/depth_estimation/part4_policy.py','pyslam/utilities/logging.py']:
            before=(base/name).read_text() if (base/name).exists() else ''
            after=(SLAM/name).read_text()
            if before==after:continue
            patch.append(f'diff --git a/{name} b/{name}\n')
            if not before:patch.append('new file mode 100644\n')
            patch.extend(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+name if before else '/dev/null',tofile='b/'+name))
        tracking=(SLAM/'pyslam/slam/tracking.py').read_text()
        start=tracking.find('        # Part 4 sparse-depth playback:');end=tracking.find('        if f_cur_is_blurry:',start)
        if start<0 or end<start:raise Blocked('Part 4 sparse-depth guard is missing')
        unguarded=tracking[:start]+tracking[end:]
        patch.append('diff --git a/pyslam/slam/tracking.py b/pyslam/slam/tracking.py\n')
        patch.extend(difflib.unified_diff(unguarded.splitlines(True),tracking.splitlines(True),fromfile='a/pyslam/slam/tracking.py',tofile='b/pyslam/slam/tracking.py'))
        return ''.join(patch)
