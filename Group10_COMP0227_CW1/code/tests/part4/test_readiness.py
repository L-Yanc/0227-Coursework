"""Synthetic readiness checks must stop expensive work on invalid metric geometry."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from common import ROOT,Stage,Blocked,dump,publish_pointer
from part4 import example
from readiness import marker_report
from repair_reference import parse_camera
from reference import reconstruction_settings

def fixture(work,check_distance):
    c=example(); k=np.array([[500.,0,320],[0,500,240],[0,0,1.]])
    prep=Stage(work,'synthetic_camera',{'fixture':True}); prep.begin()
    dump(prep.path/'camera.json',{'K':k.tolist(),'width':640,'height':480})
    prep.finish(['camera.json']); publish_pointer(work,'prepare',prep)
    poses=np.repeat(np.eye(4)[None],5,axis=0); poses[:,0,3]=np.linspace(-.7,.7,5)
    registered={f'{i:06d}.png':{'Twc':p.tolist()} for i,p in enumerate(poses)}
    ref=Stage(work,'synthetic_reference',{'fixture':True}); ref.begin()
    dump(ref.path/'registered.json',registered)
    dump(ref.path/'reference_quality.json',{'registered_fraction':1.,'max_gap_s':.1})
    ref.finish(['registered.json','reference_quality.json']); publish_pointer(work,'reference',ref)
    selections=[]
    for m,y,length in [('wall_100',0.,1.005),('wall_50',.4,check_distance)]:
        for e,x in [('a',-.4),('b',-.4+length)]:
            point=np.array([x,y,5.]); pc=point-poses[:,:3,3]; uv=(k@pc.T).T; uv=uv[:,:2]/uv[:,2:]
            for i,u in enumerate(uv): selections.append({'marker':m,'endpoint':e,'image':f'{i:06d}.png','u':float(u[0]),'v':float(u[1])})
    dump(work/'annotations.json',{'reference_key':ref.key,'selections':selections})
    return c

class ReadinessTests(unittest.TestCase):
    def test_independent_check_distance_pass_and_fail(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'part4',prefix='synthetic_readiness_') as d:
            work=Path(d); c=fixture(work,.5); good=marker_report(c,work,write=False)
            self.assertTrue(good['metric_reference_ready']); self.assertAlmostEqual(good['markers']['wall_50']['estimated_distance_m'],.5)
            c=fixture(work,.9); bad=marker_report(c,work,write=False)
            self.assertTrue(bad['selections_sufficient']); self.assertFalse(bad['metric_reference_ready'])
            self.assertTrue(any('held-out' in reason for reason in bad['blockers']))

    def test_failed_reference_stops_before_calibration_or_batch(self):
        from experiments import run
        with tempfile.TemporaryDirectory(dir=ROOT/'part4',prefix='synthetic_gate_') as d:
            work=Path(d); c=fixture(work,.9)
            with patch('media.calibrate') as calibrate,patch('experiments.depth') as depth,patch('experiments.slam_run') as slam:
                with contextlib.redirect_stdout(io.StringIO()),self.assertRaises(Blocked): run(c,work)
                calibrate.assert_not_called(); depth.assert_not_called(); slam.assert_not_called()

    def test_camera_parser_and_scoring_settings_separation(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'cameras.txt'; p.write_text('# fixture\n1 PINHOLE 640 480 500 501 320 240\n')
            self.assertEqual(parse_camera(p)['K'][1][1],501)
        a=example()['reference']; b={**a,'max_check_error_m':.05,'marker_border_margin_px':12}
        self.assertEqual(reconstruction_settings(a),reconstruction_settings(b))
