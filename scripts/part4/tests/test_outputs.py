"""Synthetic CSV/observation fixtures, kept separate from experimental data."""
import tempfile
import unittest
from pathlib import Path
import numpy as np
from common import table,Stage,ROOT,read
from scoring import FIELDS,validate_csv,merge,aggregate
from geometry import write_tum
from analysis import bilinear

class OutputTests(unittest.TestCase):
    def test_blank_metric_and_csv_quoting_paths(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d); (base/'Results').mkdir(); (base/'trajectories_tum').mkdir()
            poses=np.repeat(np.eye(4)[None],3,0); poses[:,0,3]=[0,1,2]
            write_tum(base/'trajectories_tum/a file.tum',[0,1,2],poses)
            row=dict.fromkeys(FIELDS,''); row.update(run_id='test',sequence='own',method='mono',settings='a="x,y"',run_number=1,trajectory_file='trajectories_tum/a file.tum')
            p=base/'Results/a.csv'; table(p,[row],FIELDS)
            data=validate_csv(p,base); self.assertEqual(data[0]['map_depth_mae_m'],''); self.assertEqual(data[0]['settings'],row['settings'])
            with self.assertRaises(ValueError): merge([p,p],base/'Results/merged.csv')
            row['trajectory_file']='../../escape.tum'; table(p,[row],FIELDS)
            with self.assertRaises(ValueError): validate_csv(p,base)

    def test_failed_row_no_fabricated_pose(self):
        with tempfile.TemporaryDirectory() as d:
            row=dict.fromkeys(FIELDS,''); row.update(run_id='failure',method='mono',sequence='own')
            p=Path(d)/'failed.csv'; table(p,[row],FIELDS)
            self.assertEqual(len(validate_csv(p,d,True)),1)
            row['ate_scaled_m']=0; table(p,[row],FIELDS)
            with self.assertRaises(ValueError): validate_csv(p,d,True)

    def test_bilinear_invalid_and_edges(self):
        d=np.array([[1.,2.],[3.,4.]])
        self.assertAlmostEqual(bilinear(d,.5,.5),2.5)
        self.assertIsNone(bilinear(d,-.1,.2)); d[0,0]=0; self.assertIsNone(bilinear(d,.5,.5))

    def test_aggregates_separate_sequences(self):
        r=[{'sequence':'KITTI 06','method':'mono','ate_scaled_m':10},{'sequence':'own','method':'mono','ate_scaled_m':1}]
        a=[x for x in aggregate(r) if x['metric']=='ate_scaled_m']; self.assertEqual(len(a),2)
        self.assertEqual({x['mean'] for x in a},{1.,10.})

    def test_trust_configurations_are_not_pooled(self):
        import json
        r=[{'sequence':'own','method':'selected','settings':json.dumps({'method':'selected','run_number':1,'selected':{'parameters':{'trust':v}}}),'ate_scaled_m':a} for v,a in [(.1,1.),(1.,10.)]]
        a=[x for x in aggregate(r) if x['metric']=='ate_scaled_m']
        self.assertEqual(len(a),2); self.assertEqual({x['mean'] for x in a},{1.,10.})

    def test_failed_subprocess_is_logged_and_not_cached(self):
        import sys
        with tempfile.TemporaryDirectory(dir=ROOT/'part4',prefix='synthetic_process_test_') as d:
            stage=Stage(Path(d),'synthetic_failure',{'fixture':True}); stage.begin()
            with self.assertRaises(RuntimeError):
                stage.run([sys.executable,'-c','import sys; print("synthetic failure",file=sys.stderr); sys.exit(7)'])
            self.assertEqual(read(stage.path/'stage.json')['status'],'failed')
            self.assertEqual(read(stage.path/'command_000.json')['exit_code'],7)
            self.assertIn('synthetic failure',(stage.path/'command_000.stderr.log').read_text())
            self.assertFalse(stage.cached())

class PackagingOwnershipTests(unittest.TestCase):
    def test_previous_recording_ownership_does_not_overwrite_user_edits(self):
        from scoring import verified_previous_ownership
        from common import dump,digest
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);source=folder/'source';source.mkdir()
            p=source/'example.py';p.write_text('generated\n');manifest=folder/'prior.json'
            dump(manifest,{'example.py':digest(p)})
            self.assertEqual(verified_previous_ownership(source,[manifest]),{'example.py':digest(p)})
            p.write_text('independent user edits\n')
            self.assertEqual(verified_previous_ownership(source,[manifest]),{})
