#  Part 3: Depth in SLAM

This folder holds Part 3's code and results: the changes made to pySLAM, the scripts that make the depth maps, run every configuration and make the Part 3 table and figure, and one row per run with its trajectory.

## Contents

| File | Purpose |
|---|---|
| `part3.diff` | Our changes to pySLAM |
| `scripts/` | Depth maps, runs, scoring, results CSV, table and figure |
| `configs/KITTI06_depth.yaml` | KITTI settings with `DepthMapFactor: 256` |
| `results/part3_results.csv` | One row per run  |
| `results/trajectories/` | Estimated trajectory of every run in TUM format |
| `results/runs.csv`, `results/measures.csv` | Scores from `part3_score.py` and `part3_measures.py` |
| `results/summary.csv`, `results/batches.md` | Median, min and max per configuration; every configuration next to the mono of its own batch |
| `results/table_p3.tex`, `results/part3_traj_fr3.png` | The Part 3 table and figure of the report |
| `results/part3_folders.txt`, `results/A_folders.txt` | Which `results/eval_...` folder holds which configuration |

## Setup

From pySLAM at the tag:

```bash
git checkout comp0227-2026-lab04
git apply part3.diff
```

The diff changes five files:
- `pyslam/depth_estimation/pred_depth.py` (new): loads a keyframe's saved depth map, reads the depth at each keypoint (5x5 median) and its uncertainty (largest depth gradient), and holds methods B and E1.
- `pyslam/slam/local_mapping.py`: method B, called in `create_new_map_points` after triangulation.
- `pyslam/slam/initializer.py`: method E1 which is the first map scaled to the network's median depth.
- `pyslam/depth_estimation/depth_sampling.py`: median reading in `depth_at_keypoints()` 
- `main_slam.py`: saves the final map to `map_dump.npz` when `CW1_SAVE_MAP=1`

Nothing changes unless these are set:

| Variable | Meaning |
|---|---|
| `CW1_METHOD` | `E1`, `B` or `B+E1` |
| `CW1_SIGMA_PCT` | trust setting p: only keypoints whose depth gradient is below this percentile of their frame are used (100 means all) |
| `CW1_DEPTH_UNTIL` | 0 = always, N = only for the first N keyframes |
| `CW1_PRED_DEPTH` | the sequence's `associations_dav2.txt` |
| `CW1_DEPTH_FACTOR` | 5000 (TUM), 6553.5 (Replica), 256 (KITTI) |
| `CW1_SAVE_MAP` | 1 = save the map for the map-depth measure |

Sequences, in `$DS`: TUM fr3 long office household as downloaded, Replica room0 and KITTI 06 put in the TUM layout:

```bash
python $P/scripts/replica_to_tum.py Replica/room0 $DS/replica_room0_tum
python $P/scripts/part3_kitti_to_tum.py data/videos/kitti06 $DS/kitti06_tum
```

The run scripts start with our server's paths (`CW`, `DS`); set them to yours. All commands run from the pySLAM folder, with `P` set to this folder.

## Commands

| Step | Command | Makes |
|---|---|---|
| Depth maps, TUM and Replica (Depth Anything V2 large, indoor) | `bash $P/scripts/run_part2_depth.sh` | `depth_dav2/`, `associations_dav2.txt` in each sequence |
| Depth maps, KITTI (outdoor) | `pixi run -e depth depth-prediction --method DEPTH_ANYTHING_V2 --scene outdoor --tum $DS/kitti06_tum --settings $P/configs/KITTI06_depth.yaml --save dav2 --headless` | the same for KITTI |
| Batch 1: mono, Reference, true RGB-D on TUM and Replica, 10 runs each | `bash $P/scripts/run_part3_A.sh` | `A_folders.txt` |
| Batch 2: mono, E1, B50, B80, B100, B80u10, B80+E1 | `bash $P/scripts/run_part3.sh`, then `bash $P/scripts/run_part3_rest.sh` | `part3_folders.txt` |
| Batch 3: mono, E1 50%, E1 80%, Reference on KITTI | `bash $P/scripts/run_part3_extra.sh` | `part3_folders.txt` |
| ATE, scale, RPE over 1 m, tracked, lost, wall time | `pixi run python $P/scripts/part3_score.py OUT $P/results/A_folders.txt $P/results/part3_folders.txt` | `runs.csv` |
| TUM trajectories | `pixi run python $P/scripts/part3_tum.py $P/results/runs.csv $P/results/trajectories $DS/<each sequence>` | `trajectories/` |
| RPE over 1 s, tracking time, map depth error | `pixi run python $P/scripts/part3_measures.py $P/results/runs.csv $P/results/measures.csv $DS/<each sequence>` | `measures.csv` |
| Results CSV | `python $P/scripts/part3_results_csv.py $P/results/runs.csv $P/results/measures.csv $P/results/part3_results.csv` | `part3_results.csv` |
| **Part 3 table** | `python $P/scripts/part3_table.py $P/results/runs.csv $P/results/measures.csv $P/results` | `table_p3.tex`, `summary.csv`, `batches.md` |
| **Part 3 figure** | `pixi run python $P/scripts/part3_plots.py $P/results/runs.csv OUT` | `part3_traj_fr3.png` |

## Measures

- `ate_unscaled_m`, `ate_scaled_m`, `fitted_scale`: ATE RMSE after an SE(3) and a Sim(3) fit, and the fitted scale. 
- `rpe_rmse_m`: translational RPE over 1 s after the Sim(3) fit, pairs within 0.06 s and without tracking gaps.
- `fraction_tracked`, `fraction_lost`: from pySLAM's `other_metrics_info.txt`.
- `time_per_frame_ms`: mean of pySLAM's per-frame `Tracking: elapsed_time` in the run's logs.
- `map_depth_mae_m` (TUM and Replica): every map point in every keyframe that sees it, against the true depth at its pixel; monocular maps are multiplied by the fitted scale, RGB-D maps (the Reference and true RGB-D) are taken as they are.
- extra columns: `rpe_1m_m` (RPE over 1 m of travel) and `wall_time_per_frame_ms` (run time over frames; on KITTI it stays near the camera's frame interval)

## Batches

The runs were made in three batches: batch 1 on skate-l; batch 2 on skate-l (TUM and part of Replica) and shark-l (rest of Replica and KITTI); batch 3 on shark-l. Every batch has its own mono, and each method is compared with the mono of its batch (`batches.md`). The report's table shows batch 2's mono; the monos agree. On KITTI, runs that tracked under 95% of the frames are left out of the medians, because ATE is scored only on the frames that were tracked.


## Extra plots 

`results/plots/` has plots behind the text that did not fit in the report:

| File | What it shows | Made by |
|---|---|---|
| `part3_ate.png` | ATE without and with scale, one dot per run, line = median, per configuration | `part3_plots.py` |
| `part3_scale.png` | fitted scale s per run; dashed line at 1 = map in metres | `part3_plots.py` |
| `part3_traj_*.png` | median run of mono, E1 and B80+E1 against the ground truth, per sequence | `part3_plots.py` |
| `points_ratio.png` | network depth / triangulated depth against triangulated depth, from the plain mono runs (why B shrinks the map) |


## Report table

`table_p3.tex` has the rows of the Part 3 table. For each sequence it shows ATE after the SE(3) and Sim(3) fits, the fitted scale and the tracking time per frame (ms). TUM and Replica also show the map depth error (m); KITTI shows how many of the 5 runs tracked at least 95% of the frames instead.

## Merging with the other parts

`part3.diff` is against the tag on its own. `depth_sampling.py` has the same median reading that Part 2 added (it gives identical numbers), so when the parts' diffs are combined into one, keep Part 2's version of that file.


## The CSV files

| File | Made by | What it holds |
|---|---|---|
| `results/part3_results.csv` | `part3_results_csv.py` |  One row per run containing these columns: `run_id`, `sequence`, `method`, `settings`, `run_number`, `ate_unscaled_m`, `ate_scaled_m`, `fitted_scale`, `rpe_rmse_m`, `fraction_tracked`, `fraction_lost`, `time_per_frame_ms`, `map_depth_mae_m`, `trajectory_file`, plus `rpe_1m_m` and `wall_time_per_frame_ms` |
| `results/runs.csv` | `part3_score.py` | One row per run, from each run's `trajectory_final.json` and `other_metrics_info.txt`: configuration, mode, sequence, run, folder, ATE after the SE(3) and Sim(3) fits, scale, RPE over 1 m, % tracked and lost, frames, poses, wall time per frame |
| `results/measures.csv` | `part3_measures.py` | One row per run: RPE over 1 s and its number of pairs, tracking time per frame and its number of frames, map depth error and its number of observations |
| `results/summary.csv` | `part3_table.py` | Median, min and max of every measure per configuration |

`part3_results.csv` is `runs.csv` and `measures.csv` joined on configuration, mode and run, with each configuration's method and settings written out.
In the 20 TUM runs of batch 1 (the Reference and true RGB-D), pySLAM's frame ids are 2 behind `associations.txt`. `part3_pose_times.py` and `part3_measures.py` find each run's offset from the ground truth (shift -3..+3, best match) and use it for the timestamps, RPE over 1 s and map depth error. `results/pose_times/summary.csv` gives the offset of every run (0 for the other 200) and the ground-truth mismatch after it (at most 0.6 mm).

In the 20 TUM runs of batch 1 (the Reference and true RGB-D), the frame ids saved with the trajectory are 2 behind `associations.txt`. `part3_pose_times.py` and `part3_measures.py` find each run's offset from the ground truth and use it for the timestamps and the RPE over 1 s. `results/pose_times/summary.csv` gives the offset of every run (0 for the other 200) and the ground-truth mismatch after it (at most 0.6 mm). The map's keyframe ids need no offset: for these runs the map depth error is lowest at offset 0 (true RGB-D: 0.049 m at 0, 0.068 m at +2).
