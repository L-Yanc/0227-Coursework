"""Synthetic camera motion must not be interpreted as depth flicker."""
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from analysis import analyse_run
from common import ROOT,table,dump
from part4 import example

class AnalysisTests(unittest.TestCase):
    def test_threshold_has_no_heldout_learned_centre_leakage(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'part4',prefix='synthetic_threshold_') as d:
            root=Path(d); prep=root/'prep'; run=root/'run'; pred=root/'depth'
            for p in [prep,run,pred/'raw_m']: p.mkdir(parents=True)
            k=np.array([[20.,0,20],[0,20,15],[0,0,1.]])
            dump(prep/'camera.json',{'K':k.tolist(),'width':40,'height':30})
            records=[]; frames=[]
            for i in range(6):
                pose=np.eye(4); pose[0,3]=i*.1; pc=np.array([0.,0.,4.])-pose[:3,3]; uv=k@pc; uv=uv[:2]/uv[2]
                frames.append({'frame_id':i,'timestamp':i,'image':f'rgb/{i:06d}.png'})
                records.append({'frame_id':i,'timestamp':i,'point_id':123,'u':uv[0],'v':uv[1],
                                'map_depth':4.,'world_x':0.,'world_y':0.,'world_z':4.,'Twc':json.dumps(pose.tolist())})
                np.save(pred/'raw_m'/f'{i:06d}.npy',np.full((30,40),4. if i<3 else 4.5))
            table(prep/'frames.csv',frames); table(run/'map_observations.csv',records)
            summary=analyse_run(run,prep,pred,root/'out',example())
            self.assertAlmostEqual(summary['diagnostic_threshold_m'],0,places=8)
            self.assertEqual(summary['heldout_rejection_fraction'],1.)
            self.assertEqual(summary['threshold_heldout_points'],1)

    def test_world_consistency_and_source_ids(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); prep=root/'prep'; run=root/'run'; pred=root/'depth'
            for p in [prep,run,pred/'raw_m']: p.mkdir(parents=True)
            k=np.array([[20.,0,20],[0,20,15],[0,0,1.]])
            dump(prep/'camera.json',{'K':k.tolist(),'width':40,'height':30})
            records=[]; frames=[]; world=np.array([0.,0.,4.])
            for fid,x,z in [(0,-1,0),(10,0,.5),(20,1,1)]:
                pose=np.eye(4); pose[:3,3]=[x,0,z]; pc=world-pose[:3,3]; uv=k@pc; uv=uv[:2]/uv[2]
                frames.append({'frame_id':fid,'timestamp':fid/10,'image':f'rgb/{fid:06d}.png'})
                records.append({'frame_id':fid,'timestamp':fid/10,'point_id':123,'u':uv[0],'v':uv[1],
                                'map_depth':pc[2],'world_x':0,'world_y':0,'world_z':4,'Twc':json.dumps(pose.tolist())})
                np.save(pred/'raw_m'/f'{fid:06d}.npy',np.full((30,40),pc[2]))
            table(prep/'frames.csv',frames); table(run/'map_observations.csv',records)
            summary=analyse_run(run,prep,pred,root/'out',example())
            self.assertAlmostEqual(summary['temporal_world_discrepancy']['median'],0)
            self.assertFalse(summary['reference_depth_available'])
            records[-1]['frame_id']=999; table(run/'map_observations.csv',records)
            with self.assertRaises(ValueError): analyse_run(run,prep,pred,root/'bad',example())
