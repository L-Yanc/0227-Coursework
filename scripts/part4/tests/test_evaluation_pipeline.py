"""End-to-end SYNTHETIC scoring fixture, never submitted as a real experiment."""
import tempfile
import unittest
from pathlib import Path
import numpy as np
from common import ROOT, Stage, dump, table, publish_pointer, rows, read
from geometry import write_tum
from scoring import evaluate
from part4 import example

class EvaluationPipelineTests(unittest.TestCase):
    def test_actual_csv_and_sidecars_from_synthetic_transformed_poses(self):
        with tempfile.TemporaryDirectory(prefix='synthetic_test_',dir=ROOT/'part4') as temp:
            work=Path(temp); c=example(); c['experiment_id']='SYNTHETIC_UNIT_TEST_ONLY'
            t=np.arange(30)/10; xyz=np.c_[np.sin(t),np.cos(t),t*.1]
            poses=np.repeat(np.eye(4)[None],30,axis=0); poses[:,:3,3]=xyz
            refposes=poses.copy(); refposes[:,:3,3]=2.5*xyz+[3,4,5]
            prep=Stage(work,'synthetic_prepare',{'fixture':True}); prep.begin()
            table(prep.path/'frames.csv',[{'frame_id':i,'timestamp':float(ti),'image':f'rgb/{i:06d}.png','source_frame_index':i} for i,ti in enumerate(t)])
            dump(prep.path/'camera.json',{'K':[[20,0,20],[0,20,15],[0,0,1]],'width':40,'height':30})
            (prep.path/'camera.yaml').write_text('fixture: true\n')
            prep.finish(['frames.csv','camera.json','camera.yaml']); publish_pointer(work,'prepare',prep)
            ref=Stage(work,'synthetic_reference',{'fixture':True}); ref.begin()
            dump(ref.path/'reference_quality.json',{'passes_registered_fraction':True,'registered_fraction':1.,'max_gap_s':.1})
            ref.finish(['reference_quality.json']); publish_pointer(work,'reference',ref)
            scale=Stage(work,'synthetic_marker_scale',{'fixture':True}); scale.begin()
            write_tum(scale.path/'reference_tum.txt',t,refposes); scale.finish(['reference_tum.txt']); publish_pointer(work,'marker_scale',scale)
            dep=Stage(work,'synthetic_depth',{'fixture':True}); dep.begin()
            table(dep.path/'timing.csv',[],['frame_id','inference_ms']); dep.finish(['timing.csv']); publish_pointer(work,'depth',dep)
            run=work/'slam/SYNTHETIC_UNIT_TEST'; run.mkdir(parents=True)
            dump(run/'spec.json',{'fixture':'SYNTHETIC_UNIT_TEST_ONLY','prepare':str(prep.path.relative_to(ROOT)),
                                  'method':'mono','policy':'every','run_number':1,'max_frames':None})
            dump(run/'run.json',{'status':'complete','mean_tracking_ms':1.,'subprocess_wall_s':.1})
            write_tum(run/'trajectory.tum',t,poses)
            table(run/'frame_status.csv',[{'frame_id':i,'timestamp':ti,'state':'OK','depth_used':False} for i,ti in enumerate(t)])
            table(run/'map_observations.csv',[],['frame_id','point_id','u','v','map_depth'])
            out=evaluate(c,work); csv=rows(out/'part4_submission_results.csv')
            self.assertEqual(len(csv),1); self.assertEqual(csv[0]['map_depth_mae_m'],'')
            self.assertAlmostEqual(float(csv[0]['fitted_scale']),2.5,places=7)
            self.assertLess(float(csv[0]['ate_scaled_m']),1e-8)
            self.assertTrue(csv[0]['trajectory_file'].startswith('trajectories_tum/part4/'))
            self.assertEqual(len(rows(out/'common_subset_metrics.csv')),1)
            self.assertEqual(read(out/'failure_trace.json')['status'],'unavailable')
            # A repeat uses the same output directory and one CSV row.
            self.assertEqual(evaluate(c,work),out)
            self.assertEqual(len(rows(out/'part4_submission_results.csv')),1)
