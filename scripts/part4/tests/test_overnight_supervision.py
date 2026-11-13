import sys
import tempfile
from pathlib import Path
import unittest
import numpy as np
from common import ROOT,Stage,dump,table,read
from supervision import run_supervised,completed_payload
from geometry import write_tum
from master_results import historical_row,clean_number,canonical_sequence

class SupervisionTests(unittest.TestCase):
    def fixture(self,p):
        prep=p/'prep';prep.mkdir();table(prep/'frames.csv',[{'frame_id':i,'timestamp':float(i)} for i in range(3)])
        dump(p/'spec.json',{'prepare':str(prep.relative_to(ROOT)),'selected':None})
        table(p/'frame_status.csv',[{'frame_id':i,'timestamp':float(i),'state':'OK'} for i in range(3)])
        table(p/'map_observations.csv',[],['frame_id','point_id','map_depth'])
        poses=np.repeat(np.eye(4)[None],3,axis=0);poses[:,0,3]=[0,1,2];write_tum(p/'trajectory.tum',[0,1,2],poses)
        return {'status':'complete','backend_quiescent':True,'frames':3,'trajectory_poses':3,'map_observations':0}

    def test_exported_payload_exit_hang_is_recovered_without_rerunning(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'part4',prefix='synthetic_supervisor_') as d:
            stage=Stage(Path(d),'synthetic_worker',{});stage.begin();info=self.fixture(stage.path)
            code='import json,time;from pathlib import Path;Path("run.json").write_text(json.dumps('+repr(info)+'));time.sleep(10)'
            run_supervised(stage,[sys.executable,'-c',code],cwd=stage.path,poll_s=.01,exit_grace_s=.03,timeout_s=2.)
            self.assertTrue(read(stage.path/'run.json')['shutdown_recovered'])
            rec=read(stage.path/'command_000.json')
            self.assertTrue(rec['successful_payload_recovered']);self.assertLess(rec['exit_code'],0)
            self.assertTrue((stage.path/'supervision_recovery/run_before_recovery.json').exists())

    def test_hung_incomplete_worker_times_out_and_is_not_scored(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'part4',prefix='synthetic_timeout_') as d:
            stage=Stage(Path(d),'synthetic_worker',{});stage.begin()
            code='from pathlib import Path;import time;Path("run.json").write_text("{}");time.sleep(10)'
            with self.assertRaises(RuntimeError):
                run_supervised(stage,[sys.executable,'-c',code],cwd=stage.path,poll_s=.01,exit_grace_s=.02,timeout_s=.1)
            self.assertEqual(read(stage.path/'stage.json')['status'],'failed')
            self.assertFalse((stage.path/'run.json').exists())
            self.assertTrue((stage.path/'incomplete_payloads/run_000.json').exists())

    def test_zero_exit_with_missing_outputs_is_not_success(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'part4',prefix='synthetic_no_payload_') as d:
            stage=Stage(Path(d),'synthetic_worker',{});stage.begin()
            with self.assertRaises(RuntimeError):run_supervised(stage,[sys.executable,'-c','pass'],cwd=stage.path,poll_s=.01)

class HistoricalExportTests(unittest.TestCase):
    def test_legacy_metrics_stay_in_distinct_columns(self):
        raw={'config':'fr3_B80E1','mode':'mono','seq':'rgbd_dataset_freiburg3_long_office_household','run':'0','ate_se3_m':'.1','ate_sim3_m':'.02','scale':'1.2','pct_tracked':'98.5','pct_lost':'1.5','rpe_1m_m':'.03','wall_s_per_frame':'.05'}
        row=historical_row(raw,'trajectories_tum/test.tum')
        self.assertEqual(row['rpe_rmse_m'],'');self.assertEqual(row['time_per_frame_ms'],'')
        self.assertEqual(row['rpe_1m_m'],.03);self.assertEqual(row['source_wall_time_per_frame_ms'],50.)
        self.assertAlmostEqual(row['fraction_tracked'],.985);self.assertEqual(row['run_number'],1)
        self.assertEqual(row['sequence'],'TUM fr3')
        self.assertEqual(clean_number('nan'),'');self.assertEqual(clean_number(None),'')

class ReadinessGuardTests(unittest.TestCase):
    def test_missing_or_changed_readiness_is_rejected(self):
        from overnight import require_ready,signature
        from part4 import example
        from common import Blocked
        with tempfile.TemporaryDirectory() as d:
            work=Path(d);c=example()
            with self.assertRaises(Blocked):require_ready(c,work)
            dump(work/'overnight_preflight.json',{'complete':False,'signature':signature(c)})
            with self.assertRaises(Blocked):require_ready(c,work)
            dump(work/'overnight_preflight.json',{'complete':True,'signature':signature(c)})
            require_ready(c,work)
            c['methods']['playback_speed']=2.
            with self.assertRaises(Blocked):require_ready(c,work)

class MasterPipelineTests(unittest.TestCase):
    def test_master_export_links_sources_and_preserves_independent_edits(self):
        from unittest.mock import patch
        from common import Blocked,rows
        import master_results
        from scoring import FIELDS
        with tempfile.TemporaryDirectory(dir=ROOT/'part4',prefix='synthetic_master_') as d:
            root=Path(d);team=root/'team';(team/'Results').mkdir(parents=True)
            work=root/'work';legacy=work/'legacy';ev=work/'evaluation'
            raw={'config':'fr3_B80E1','mode':'mono','seq':'tum','run':'0','ate_se3_m':'.1','ate_sim3_m':'.02','scale':'1.2','pct_tracked':'98.5','pct_lost':'1.5','rpe_1m_m':'.03','wall_s_per_frame':'.05'}
            table(legacy/'runs.csv',[raw])
            text='0 0 0 0 0 0 0 1\n1 1 0 0 0 0 0 1\n2 2 0 0 0 0 0 1\n'
            p=legacy/'trajectories/fr3_B80E1_mono_tum_0.txt';p.parent.mkdir(parents=True);p.write_text(text)
            own=dict.fromkeys(FIELDS,'');own.update(run_id='SYNTHETIC_OWN',sequence='own',method='mono',settings='{}',run_number=1,ate_scaled_m=.1,trajectory_file='trajectories_tum/part4/synthetic_own.tum')
            table(ev/'part4_submission_results.csv',[own],FIELDS)
            p=ev/'trajectories_tum/synthetic_own.tum';p.parent.mkdir();p.write_text(text)
            std={**own,'run_id':'SYNTHETIC_STANDARD','sequence':'kitti06','trajectory_file':'trajectories_tum/part4/synthetic_std.tum'}
            p=team/std['trajectory_file'];p.parent.mkdir(parents=True);p.write_text(text)
            table(work/'standard_reruns/part4_standard_results.csv',[std],FIELDS)
            dump(work/'standard_reruns/status.json',{'full_standard_part4_completed':True})
            def locate(w,name):return legacy if name=='part3_import' else ev
            with patch.object(master_results,'ROOT',root),patch.object(master_results,'TEAM',team),patch.object(master_results,'artifact',side_effect=locate):
                output=master_results.export_master({'experiment_id':'SYNTHETIC_ONLY'},work)
                data=rows(output);self.assertEqual(len(data),3)
                self.assertEqual({r['source_part'] for r in data},{'part3','part4_own','part4_standard'})
                self.assertTrue(all((team/r['trajectory_file']).exists() for r in data))
                self.assertEqual(data[0]['rpe_rmse_m'],'');self.assertEqual(float(data[0]['rpe_1m_m']),.03)
                alias=team/'Results/part3_part4_combined_results.csv';alias.write_text('independent user edits\n')
                with self.assertRaises(Blocked):master_results.export_master({'experiment_id':'SYNTHETIC_ONLY'},work)
                self.assertEqual(alias.read_text(),'independent user edits\n')
