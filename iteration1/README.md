# iteration 1 

Everything from parts 1 to 3 so far. Each folder has its own README.

- code/ - my pySLAM changes (pyslam.diff), scripts, settings, and how to switch the methods on
- part1/ - baseline: plain pySLAM on fr3, room0 and KITTI, 10 runs each
- part2/ - the network's depth on its own: scores, stability, sigma_d, keypoint files
- part3/ - depth in SLAM: method A (10 runs), test runs of E1 and B, point logs

The zips have the run files (map_dump.npz, trajectory, metrics). The depth maps aren't included (too big), code/README.md has the command to make them.

iteration2 will have the full Part 3 batch (every config, 5 runs each).

For Part 4, start with:
- triangulated vs learned depth: part3/pointlogs, or part1/runs.zip plus the depth maps
- consistency across keyframes: map_dump.npz in the zips plus the depth maps
- a case where depth hurts: part3 (A on fr3) and part2 (fr3 frames 1007 and 2022)
- which frames need depth: iteration2
- your own sequence: code/README.md
