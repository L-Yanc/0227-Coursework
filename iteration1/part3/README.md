# part 3 - network depth in SLAM

Run on skate-l. Each A run also re-ran mono and rgbd in the same batch, so compare against those.

- A_folders.txt, A_ate_and_tracked.txt - method A, 10 runs on fr3 and room0, with mono and rgbd from the same batch
- test_folders.txt, tests_ate_and_tracked.txt - one test run each of E1 and B
- A_fr3_runs.zip, A_room0_runs.zip, tests_runs.zip - map_dump.npz, trajectory and other_metrics_info.txt of those runs
- pointlogs/ - point logs of the two B test runs (columns below)
- part3.log - progress of the batch that's running now

Methods:
- A - the network depth is used as if it came from a depth camera (no code, --predicted-depth)
- E1 - the first map is scaled to the network's median depth instead of 1, so it starts in roughly metres. Used once, at the start
- B - matches pySLAM drops for too little parallax (under about 1.15 deg) get placed at the network's depth, if sigma_d is low enough. pySLAM can still move them later
- code and switches: code/README.md

A, medians of 10 (SE3 / Sim3 / s / % tracked):
- fr3 mono: 1.29 m / 0.028 m / 2.67 / 98.79
- fr3 A: 0.376 m / 0.173 m / 0.86 / 99.96
- fr3 rgbd: 0.009 m / 0.009 m / 1.00 / 99.96
- room0 mono: 0.735 m / 0.005 m / 2.87 / 99.85
- room0 A: 0.473 m / 0.012 m / 0.70 / 99.95
- room0 rgbd: 0.006 m / 0.005 m / 1.00 / 99.95
A gets the units closer to metres and starts straight away, but the shape gets worse: about 6x on fr3, 2.3x on room0

Test runs, 1 each, so just a hint:
- fr3 E1: 0.050 m / 0.025 m / 1.02 / 98.79 - metres right, shape same as mono
- room0 E1: 0.527 m / 0.007 m / 0.68 - carries the network's 30% scale error
- fr3 B80: 1.464 m / 0.025 m / 3.44 / 98.79 - 8679 points added, shape same, but the scale moves outside mono's range
- KITTI B80+E1: 77.2 m / 16.9 m / 0.64 / 99.82 - 12249 points added, half of KITTI's matches have too little parallax

Point log: one line per match. Columns: kf, kf2, t, u, v, parallax_deg, z_tri_units, m_per_unit, z_tri_m, d_hat_m (network depth), sigma_grad, trusted, tri_added, low_parallax, b_candidate, b_added. True depth = the dataset's depth image at time t, pixel (u, v).

Coming in iteration2: fr3, room0 and KITTI x mono, E1, B50, B80, B100, B80+E1 and B80 for the first 10 keyframes, 5 runs each, point logs for every config (mono too), plus A on KITTI.

For Part 4:
- triangulated vs learned depth: pointlogs/ (z_tri_m vs d_hat_m vs true depth, against parallax_deg, u, v)
- a case where depth hurts: A on fr3, and B moving the scale on fr3
- which frames need depth: iteration2 (E1 vs B80 vs B80 first 10 keyframes vs mono)
- ignore eval_2026_11_09-01_36_37 (A test) and the folder from 15:59 on 9 Nov (stopped start)
