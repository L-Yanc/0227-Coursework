# part 1 - baseline

Plain pySLAM (ORB2, C++ core), 10 runs per config, on shark-l. Made with code/scripts/run_part1_simple.sh.

- part1_folders.txt - which results folder is which config
- ate_and_tracked.txt - every run: ATE without scale (SE3), with scale (Sim3), fitted scale s, % tracked
- part1.log - when each config ran
- runs.zip - map_dump.npz, trajectory and other_metrics_info.txt of every run

map_dump.npz has kf_img_id, kf_timestamp, kf_Tcw (world to camera, 4x4), points (map units) and observations (keyframe index, point index).

Medians (SE3 / Sim3 / s / % tracked):
- room0 rgbd: 6 mm / 4 mm / 1.00 / 99.95
- room0 mono: 0.73 m / 4.5 mm / 2.85 / 99.85
- fr3 rgbd: 9.5 mm / 9 mm / 1.00 / 99.96
- fr3 mono: 1.28 m / 4.2 cm / 2.65 / 98.79 (the first 30 frames are initialisation)
- KITTI mono: 131.7 m / 13.0 m / 23.0 / 99.82, except runs 2 and 7 which lost track (94.8 and 72.1)
- room0 mono on the Python core, 3 runs: same accuracy, about 10x slower

Notes:
- runs aren't identical, but indoor ones are very close. KITTI has 2 bad runs out of 10
- KITTI run 7 has the smallest SE3 error only because it was scored on 72% of the frames
- for Part 4: the mono runs' map_dump.npz plus the network depth maps give you triangulated vs learned depth and keyframe consistency
- ignore eval_2026_11_08-14_51_58, it was a test run
