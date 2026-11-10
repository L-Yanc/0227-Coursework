# iteration2: Part 3 final

All Part 3 results (9-10 Nov, 220 runs). Raw run folders stay on the server, listed in part3/part3_folders.txt. Ask if you need one.

## part3/
- runs.csv: one row per run. config, mode, seq, run, ATE SE3 and Sim3, scale s, RPE over 1 m, % tracked and lost
- summary.csv: median, min, max per config (report Tables 7 and 8)
- trajectories_tum.zip: every run's estimated trajectory in TUM format, not aligned. Timestamps come from each sequence's groundtruth.txt
- plots/: part3_ate.png (Fig 3), part3_scale.png (Fig 4), part3_traj_*.png (Fig 5), points_ratio.png (Fig 6), points_summary.txt (low parallax share, B points added, depths)
- pointlogs/<config>/points_*.csv.gz: one line per match B looked at. All runs for mono, run 0 for the rest.
  columns: kf, kf2, t, u, v, parallax_deg, z_tri_units, m_per_unit, z_tri_m, d_hat_m, sigma_grad, trusted, tri_added, low_parallax, b_candidate, b_added
- part3_folders.txt, A_folders.txt: config -> results folder on the server
- part3.log, part3_extra_nohup.out: batch logs (which machine, when)

## Configs
- mono: plain monocular
- A: pseudo RGB-D (net depth as the depth image). fr3 and room0 in its own batch, KITTI in batch 3
- E1: first map scaled to the net's median depth. E1s50 / E1s80: only keypoints under the 50th / 80th sigma_d percentile
- B50 / B80 / B100: net depth for matches with too little parallax, sigma_d percentile 50 / 80 / 100
- B80E1: both. B80u10: B only for the first 10 keyframes
- mono_rest, mono_x: mono again on shark-l, for B80E1/B80u10 (batch 2) and batch 3

## Commands -> report
| Runs | Script | Report |
|---|---|---|
| A batch (skate-l) | code/scripts/run_part3_A.sh | Table 8, A rows |
| batch 2 (skate-l, then shark-l) | run_part3.sh, run_part3_rest.sh | Tables 7 and 8 |
| batch 3 (shark-l) | run_part3_extra.sh | Table 8, E1 50/80 %, KITTI A |
| scores | part3_score.py OUT part3_folders.txt | runs.csv, summary.csv |
| TUM trajectories | part3_tum.py runs.csv OUT <the three dataset folders> | trajectories_tum.zip |
| figures | part3_plots.py runs.csv OUT | Figs 3-5 |
| point logs | part3_points.py pointlogs OUT | Fig 6, points_summary.txt |
| local mapping time | part3_lm_time.py part3_folders.txt | LM column, Table 8 |

Run all of them from the pyslam folder with pixi run python.

## code/
- pyslam.diff: git diff against 302cf18, 5 files (pred_depth.py new, depth_sampling.py, initializer.py, local_mapping.py, main_slam.py)
- switches, all off by default: CW1_METHOD (E1, B, B+E1), CW1_SIGMA_PCT, CW1_DEPTH_UNTIL, CW1_PRED_DEPTH, CW1_DEPTH_FACTOR, CW1_LOG_POINTS
- configs/KITTI06_depth.yaml: KITTI settings with DepthMapFactor 256, for A on KITTI
