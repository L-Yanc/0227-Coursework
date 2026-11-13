"""A full diagnostic pipe must not hold completed SLAM results hostage at exit."""
import subprocess
import tempfile
from pathlib import Path
import unittest
from common import SLAM,env_python

class LoggingShutdownTests(unittest.TestCase):
    def test_stopped_consumer_and_full_pipe_exit_within_timeout(self):
        with tempfile.TemporaryDirectory(prefix='part4_log_exit_') as d:
            code='''import sys,logging
import pyslam
from pyslam.utilities.logging import LoggerQueue
q=LoggerQueue(sys.argv[1])
q.listener.stop()
q.listener=None
for i in range(32):
    q.log_queue.put(logging.LogRecord('shutdown_test',20,'',0,'x'*65536,(),None))
q.stop_listener()
print('bounded shutdown returned',flush=True)
'''
            python,env=env_python()
            result=subprocess.run([str(python),'-c',code,str(Path(d)/'test.log')],cwd=SLAM,env=env,capture_output=True,text=True,timeout=12)
            self.assertEqual(result.returncode,0,result.stderr[-1500:])
            self.assertIn('bounded shutdown returned',result.stdout)
