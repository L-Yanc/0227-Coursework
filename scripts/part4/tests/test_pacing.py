import unittest
from pacing import playback_delay

class PacingTests(unittest.TestCase):
    def test_processing_counts_toward_interval(self):
        self.assertAlmostEqual(playback_delay(10.,1.,1.1,1.,10.04),.06)
        self.assertAlmostEqual(playback_delay(10.,1.,1.1,1.5,10.04),.1/1.5-.04)
    def test_slow_processing_does_not_add_wait_or_build_catchup_backlog(self):
        self.assertEqual(playback_delay(10.,1.,1.1,1.5,10.2),0.)
        self.assertAlmostEqual(playback_delay(10.2,1.1,1.2,1.5,10.24),.1/1.5-.04)
    def test_first_frame_unpaced_and_invalid_inputs(self):
        self.assertEqual(playback_delay(None,None,0.,1.5,10.),0.)
        self.assertEqual(playback_delay(10.,1.,1.1,0.,10.04),0.)
        for speed in [-1.,float('nan'),float('inf')]:
            with self.assertRaises(ValueError): playback_delay(None,None,0.,speed,10.)
        with self.assertRaises(ValueError):playback_delay(10.,1.,1.,1.,10.04)
