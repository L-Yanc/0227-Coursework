import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from online_policy import ConsistencyGate,Runtime
from common import ROOT,SLAM,dump
from part3_adapter import configure

class IntegrationTests(unittest.TestCase):
    def test_frozen_threshold_ignores_future_outliers(self):
        g=ConsistencyGate(10,min_samples=3,min_relative_threshold=.05)
        self.assertTrue(g.decide(5,[.01,.02,.03]).all())
        self.assertEqual(g.decide(11,[.01,2.,float('nan')]).tolist(),[True,False,True])
        threshold=g.threshold
        g.decide(12,[1000.]*100)
        self.assertEqual(g.threshold,threshold)
        self.assertEqual(len(g.samples),3)
        # A delayed old pair cannot refit a frozen threshold.
        g.decide(8,[1000.]);self.assertEqual(len(g.samples),3)

    def test_insufficient_development_is_not_claimed_intervention(self):
        g=ConsistencyGate(1,min_samples=5);g.decide(0,[.1])
        self.assertTrue(g.decide(2,[20.])[0]);self.assertIsNone(g.report()['relative_threshold'])

    def test_stride_policy_keeps_initialisation_and_every_rgb_frame(self):
        frames=[{'timestamp':i/10} for i in range(12)]
        r=Runtime({},frames,'stride5','.',{'enabled':False})
        for i in range(12): r.before_frame(i,i/10,i<2)
        self.assertEqual([i for i in range(12) if r.permits(i/10)],[0,1,5,10])
        self.assertFalse(r.permits(9.))

    def test_same_world_point_at_different_camera_depths(self):
        class KF:
            kps=np.array([[0.,0.]]);kpsn=kps;img_id=0
            def __init__(self,z,t): self.z=z;self.timestamp=t
            def pose(self):
                a=np.eye(4);a[2,3]=-self.z;return a
        class Pred:
            ts_of=staticmethod(lambda f:f.timestamp)
            depth=staticmethod(lambda t:np.ones((3,3)))
            trusted=staticmethod(lambda d,uv:(np.array([5.]),np.array([True])))
        r=Runtime({},[{'timestamp':0},{'timestamp':20}],'keyframes','.',{'enabled':True,'min_samples':1})
        cur,other=KF(1.,2.),KF(0.,1.)
        keep=r.filter_candidates(Pred,cur,other,[0],[0],np.array([4.]),1.,np.array([True]))
        self.assertTrue(keep[0]);self.assertAlmostEqual(r.gate.samples[0],0.)
        cur.timestamp=12.
        keep=r.filter_candidates(Pred,cur,other,[0],[0],np.array([10.]),1.,np.array([True]))
        self.assertFalse(keep[0])

    def test_manifest_supports_spaces_and_environment_isolation(self):
        with tempfile.TemporaryDirectory(prefix='Part 3 space ') as d:
            dep=Path(d);(dep/'png').mkdir();(dep/'raw_m').mkdir();out=dep/'run';out.mkdir()
            (dep/'png/000000.png').write_bytes(b'placeholder')
            dump(dep/'raw_m/000000.json',{'timestamp':1.234})
            selected={'parameters':{'method':'B+E1','sigma_pct':80}}
            with patch.dict(os.environ,{'CW1_UNRELATED':'stale'},clear=False):
                configure(selected,dep,out,'every',5000)
                self.assertNotIn('CW1_UNRELATED',os.environ)
                manifest=json.loads(Path(os.environ['CW1_PRED_DEPTH']).read_text())
                # macOS may expose the same temporary directory as /var or /private/var.
                self.assertEqual(Path(manifest[0]['path']).resolve(),(dep/'png/000000.png').resolve())
                self.assertEqual(os.environ['CW1_DEPTH_FACTOR'],'5000')
                configure(None,None,out,'every',5000)
                self.assertFalse(any(k.startswith('CW1_') for k in os.environ))

    def test_core_overlay_applies_after_teammate_patch(self):
        import subprocess
        from core_patch import build_core_patch
        from common import SOURCE
        upstream=SOURCE/'part3_source/pyslam.diff'
        names=[line.split()[2].removeprefix('a/') for line in upstream.read_text().splitlines() if line.startswith('diff --git ')]
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)
            for name in [*names,'pyslam/slam/tracking.py','pyslam/utilities/logging.py']:
                result=subprocess.run(['git','show','HEAD:'+name],cwd=SLAM,capture_output=True)
                if result.returncode==0:
                    path=base/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(result.stdout)
            subprocess.run(['git','apply',str(upstream)],cwd=base,check=True,capture_output=True)
            overlay=base/'overlay.patch';overlay.write_text(build_core_patch())
            subprocess.run(['git','apply','--check',str(overlay)],cwd=base,check=True,capture_output=True)
            subprocess.run(['git','apply',str(overlay)],cwd=base,check=True,capture_output=True)
            for name in ['pyslam/slam/initializer.py','pyslam/depth_estimation/pred_depth.py','pyslam/depth_estimation/part4_policy.py','pyslam/slam/tracking.py','pyslam/utilities/logging.py']:
                self.assertEqual((base/name).read_bytes(),(SLAM/name).read_bytes())

    def test_standard_source_ids_and_groundtruth_counts(self):
        from standard_sequences import source_records
        for name in ['tum_fr3','replica_room0','kitti06']:
            records,gt=source_records(name)
            times=np.array([r['timestamp'] for r in records])
            self.assertTrue((np.diff(times)>0).all())
            self.assertGreater(len(records),100)
            self.assertTrue((np.diff(gt[:,0])>0).all())
            self.assertLess(float(np.max(abs(np.linalg.norm(gt[:,4:],axis=1)-1.))),1e-3)

    def test_completion_does_not_claim_missing_batches(self):
        from completion import completion_report
        from part4 import example
        with tempfile.TemporaryDirectory() as d:
            c=example();c['methods']['runs']=1
            records=[]
            for method,policy in [('mono','every'),('pseudo_rgbd','every'),('pseudo_rgbd','stride5')]:
                records.append({'settings':json.dumps({'method':method,'policy':policy,'run_number':1}),'ate_scaled_m':''})
            report=completion_report(c,Path(d),records)
            self.assertTrue(report['own_attempts_completed'])
            self.assertFalse(report['full_experiment_completed'])
            self.assertTrue(all(r['scored_runs']==0 for r in report['own_configurations']))
            dump(Path(d)/'standard_reruns/status.json',{'full_standard_part4_completed':True})
            self.assertTrue(completion_report(c,Path(d),records)['full_experiment_completed'])
            self.assertFalse(completion_report(c,Path(d),records[:-1])['full_experiment_completed'])
