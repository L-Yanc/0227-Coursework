import importlib.util
from pathlib import Path
import sys
import unittest

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'scripts/shared'))
from coursework_export_map import associated_frame_ids


class SubmissionTests(unittest.TestCase):
    def test_gt_association_removing_initial_and_interior_poses_retains_correct_ids(self):
        self.assertEqual(associated_frame_ids([10.,11.,12.,13.,14.],[2,3,4,7,8],[12.,14.]),[4,8])

    def test_unknown_timestamp_does_not_get_a_nearby_frames_id(self):
        with self.assertRaises(ValueError):associated_frame_ids([10.,11.],[2,3],[10.5])

    def test_invalid_source_order_is_rejected(self):
        with self.assertRaises(ValueError):associated_frame_ids([11.,10.],[2,3],[10.])

    def test_part3_method_trust_controls(self):
        path=REPO/'scripts/part3/run_configurations.py'
        spec=importlib.util.spec_from_file_location('part3_plan',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual(module.parameters('B80E1'),('B+E1',80,0))
        self.assertEqual(module.parameters('B80u10'),('B',80,10))
        self.assertEqual(module.parameters('E1s50'),('E1',50,0))
        with self.assertRaises(ValueError):module.parameters('unknown')


if __name__=='__main__':unittest.main()
