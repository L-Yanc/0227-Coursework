# code

pyslam.diff has all my changes to pySLAM. Apply it on a clean pySLAM at commit 302cf18:

    cd pyslam
    git apply pyslam.diff

What it changes:
- main_slam.py - saves the map at the end of a run to map_dump.npz (CW1_SAVE_MAP=1)
- pyslam/depth_estimation/depth_sampling.py - added bilinear and median to depth_at_keypoints
- pyslam/depth_estimation/pred_depth.py (new) - loads the network depth in mono mode, sigma_d, B, the point log
- pyslam/slam/initializer.py - E1: the first map starts in the network's metres
- pyslam/slam/local_mapping.py - B: network depth for the matches that have too little parallax

Switches (all off unless set):
- CW1_METHOD=E1, B or B+E1
- CW1_PRED_DEPTH=<seq>/associations_dav2.txt and CW1_DEPTH_FACTOR (fr3 5000, room0 6553.5, KITTI 256)
- CW1_SIGMA_PCT=50, 80 or 100 - B only trusts keypoints under this percentile of sigma_d
- CW1_DEPTH_UNTIL=N - only use the network depth for the first N keyframes
- CW1_LOG_POINTS=<folder> - writes the point log
- CW1_SAVE_MAP=1 - writes map_dump.npz

Example, B on your own sequence:

    CW1_METHOD=B CW1_SIGMA_PCT=80 CW1_PRED_DEPTH=<seq>/associations_dav2.txt CW1_DEPTH_FACTOR=5000 \
    CW1_LOG_POINTS=<folder> CW1_SAVE_MAP=1 \
    pixi run slam-evaluation --features ORB2 --tum <seq> --settings <settings.yaml> --sensor mono --runs 5

Network depth for a sequence (same output every time):

    pixi run -e depth depth-prediction --method DEPTH_ANYTHING_V2 --tum <seq> --settings <settings.yaml> --save dav2 --headless

add --scene outdoor for KITTI.

scripts/
- replica_to_tum.py, part3_kitti_to_tum.py - turn Replica room0 and KITTI 06 into TUM layout
- run_part1_simple.sh, run_part2_depth.sh, run_part3_A.sh, run_part3.sh - the batches I ran
- part2_stability.py, part2_sigma.py - Part 2 analysis
- patch_init.py, patch_mapping.py - how E1 and B were added (already in pyslam.diff)

configs/KITTI06_depth.yaml - KITTI settings with DepthMapFactor 256 (street depths don't fit with 5000)
