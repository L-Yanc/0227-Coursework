"""Console reporting must distinguish cache hits, live progress and exit waits."""
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from common import ROOT,dump,table
from part4 import example
from progress import Reporter,Heartbeat,planned_attempts,worker_progress


def config():
    c=example();c['methods'].update(selected={'method':'test'},selected_policies=['every','stride5','keyframes'],temporal_consistency={'enabled':True})
    return c

class ProgressTests(unittest.TestCase):
    def test_counts_match_room_standard_and_combined_batches(self):
        c=config()
        self.assertEqual(planned_attempts(c,'run'),35)
        self.assertEqual(planned_attempts(c,'run-standard'),105)
        self.assertEqual(planned_attempts(c,'run-all'),140)
        self.assertEqual(planned_attempts(c,'run',smoke=True),0)
        c['methods']['runs']=3
        self.assertEqual(planned_attempts(c,'run-all'),84)

    def test_cached_and_fresh_attempts_get_number_runtime_and_status(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);dump(p/'stage.json',{'status':'complete'});dump(p/'run.json',{'status':'complete','elapsed_s':62.})
            output=[];r=Reporter(config(),'run',emit=output.append)
            def fake(*args,**kwargs):
                r.current_cached=args[4]==1
                return p
            wrapped=r.wrap_attempt(fake)
            wrapped(config(),p,'mono','every',1)
            wrapped(config(),p,'mono','every',2)
            self.assertTrue(any('Attempt 1/35' in x and 'CACHED' in x and '00:01:02' in x for x in output))
            self.assertTrue(any('Attempt 2/35' in x and 'DONE' in x and 'runtime' in x for x in output))
            wrapped(config(),p,'mono','every',1,smoke=True)
            self.assertEqual(r.index,2)
            self.assertIsNone(r.current)

    def test_errors_are_reported_and_reraised(self):
        output=[];r=Reporter(config(),'run',emit=output.append)
        def failing(*args,**kwargs):raise RuntimeError('synthetic failure')
        with self.assertRaisesRegex(RuntimeError,'synthetic failure'):
            r.wrap_attempt(failing)(config(),Path('.'),'mono','every',1)
        self.assertIn('ERROR',output[-1]);self.assertIsNone(r.current)

    def test_heartbeat_stops_after_scope_exits(self):
        calls=[];seen=threading.Event()
        def callback():calls.append(1);seen.set()
        with Heartbeat(callback,.01):self.assertTrue(seen.wait(1.))
        count=len(calls);time.sleep(.03)
        self.assertEqual(len(calls),count)

    def test_frame_progress_and_export_wait_are_visible(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'part4',prefix='synthetic_progress_') as d:
            p=Path(d);prep=p/'prepared';prep.mkdir()
            table(prep/'frames.csv',[{'frame_id':i} for i in range(3)])
            dump(p/'spec.json',{'prepare':str(prep.relative_to(ROOT)),'max_frames':None})
            table(p/'frame_status.csv',[{'frame_id':0,'state':'OK'},{'frame_id':1,'state':'LOST'}])
            text=worker_progress(p,time.time()-10)
            self.assertIn('frames 2/3',text);self.assertIn('state LOST',text)
            self.assertIn('no frame update',worker_progress(p,time.time()+10))
            dump(p/'run.json',{'backend_quiescent':True})
            self.assertIn('results exported; waiting for worker exit',worker_progress(p,time.time()-10))

    def test_worker_wait_prints_heartbeat_without_changing_worker(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'part4',prefix='synthetic_heartbeat_') as d:
            p=Path(d);output=[];r=Reporter(config(),'run',emit=output.append,heartbeat_interval=.01)
            r.current='Attempt 7/35';stage=SimpleNamespace(path=p,meta={'stage':'slam'})
            def fake_worker(stage):
                dump(p/'run.json',{'backend_quiescent':True});time.sleep(.055)
                return 'worker return'
            self.assertEqual(r.wrap_stage_run(fake_worker)(stage),'worker return')
            self.assertTrue(any('Attempt 7/35 | HEARTBEAT' in x and 'waiting for worker exit' in x for x in output))

class BatchLockTests(unittest.TestCase):
    def test_duplicate_batch_is_rejected_and_lock_releases(self):
        from progress import acquire_batch_lock
        from common import Blocked
        with tempfile.TemporaryDirectory(dir=ROOT/'part4',prefix='synthetic_lock_') as d:
            first=acquire_batch_lock(d)
            try:
                with self.assertRaises(Blocked):acquire_batch_lock(d)
            finally:first.close()
            second=acquire_batch_lock(d);second.close()
