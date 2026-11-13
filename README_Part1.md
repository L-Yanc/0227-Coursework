# COMP0227 Coursework 1 — Part 1 Baseline Handover

**Status:** Part 1 baseline data collected; evaluation scripts and map-depth associations need the validation checks below before final reporting.  
**Starting pySLAM revision:** `302cf18bb15a7f9dd5363e1f7a75f9bb648ad72b` (`comp0227-2026-lab04`).  
**Team repository:** https://github.com/L-Yanc/0227-Coursework (private; access required).

## 1. What is shared

`patches/part1_changes.patch` is a **Git patch**, not a ZIP and not an executable program. Applied to a clean checkout of the tagged coursework pySLAM, it edits `main_slam.py` and creates these files:

| File | Role |
|---|---|
| `scripts/coursework_export_map.py` | Exports observed map points and their camera-frame depths |
| `scripts/coursework_map_depth.py` | Scores map depths against reference depth |
| `scripts/coursework_replica_reference.py` | Matches Replica observations to rendered depth images |
| `scripts/coursework_tum_reference.py` | Matches TUM observations to measured depth images |
| `scripts/coursework_rpe.py` | Computes timestamp-based translational RPE |
| `pyslam/evaluation/configs/coursework_replica_mono.json` | Replica monocular evaluation |
| `pyslam/evaluation/configs/coursework_replica_rgbd.json` | Replica RGB-D evaluation |

The tagged pySLAM already contains `main_slam_evaluation.py` and `scripts/trajectory_errors.py`; those unchanged files are not included in this Part 1 patch. The patch includes **eight affected files total** (one modified and seven new). It was verified with `git apply --check` against a clean worktree at `302cf18`; a full clean-environment runtime reproduction has not yet been demonstrated.

## 2. How to apply the patch

Start with the lecturer's course repository and initialise the pySLAM submodule at the tagged commit. From the **pySLAM submodule root**:

```bash
git rev-parse --short HEAD   # should show 302cf18 before applying
git status --short          # should be clean
git apply --check /path/to/0227-team/patches/part1_changes.patch
git apply /path/to/0227-team/patches/part1_changes.patch
git status --short
```

Replace `/path/to/0227-team` with the actual clone location of the team's repository. **Do not apply the patch a second time**; it will fail because the files already exist. Do not run `git reset --hard` or `git clean -fd` on a working checkout containing your own changes. Collaborators who already changed pySLAM should coordinate before applying the patch.

The patch **does not include** datasets, model weights, the full pySLAM source, or experimental results.

## 3. Dependencies and data

Run pySLAM in the coursework's documented pixi environment. The Part 1 experiments used the CPU environment, `pixi run -e default-cpu`, and ORB2 features. The repository/dataset setup must be completed separately.

| Sequence | Required material | Camera settings |
|---|---|---|
| KITTI 06 | Supplied colour video, timestamps and trajectory ground truth | `settings/KITTI04-12.yaml` |
| TUM fr3 long office household | RGB/depth frames, `associations.txt`, trajectory ground truth | `settings/TUM3.yaml` |
| Replica room0 | RGB/depth frames, `traj.txt`, and nominal `times.txt` (25 fps) | `settings/REPLICA.yaml` |

The TUM `associations.txt` in the original run contained 2,488 matched RGB/depth pairs. Replica was configured with 2,000 frames. Do not commit the datasets to the team repository or final code ZIP.

## 4. Reproduce the main Part 1 baseline runs

Commands below are run from the **pySLAM root**. Each configuration was repeated five times using one evaluation job at a time.

```bash
# KITTI 06 (default course evaluation configuration)
PYSLAM_USE_CPP=true  pixi run -e default-cpu slam-evaluation --features ORB2 --runs 5 --jobs 1
PYSLAM_USE_CPP=false pixi run -e default-cpu slam-evaluation --features ORB2 --runs 5 --jobs 1

# TUM fr3
S=data/tum/rgbd_dataset_freiburg3_long_office_household
PYSLAM_USE_CPP=true pixi run -e default-cpu slam-evaluation --tum "$S" --sensor mono --settings settings/TUM3.yaml --features ORB2 --runs 5 --jobs 1
PYSLAM_USE_CPP=true pixi run -e default-cpu slam-evaluation --tum "$S" --sensor rgbd --settings settings/TUM3.yaml --features ORB2 --runs 5 --jobs 1

# Replica room0
PYSLAM_USE_CPP=true pixi run -e default-cpu slam-evaluation --config-file pyslam/evaluation/configs/coursework_replica_mono.json --features ORB2 --runs 5 --jobs 1
PYSLAM_USE_CPP=true pixi run -e default-cpu slam-evaluation --config-file pyslam/evaluation/configs/coursework_replica_rgbd.json --features ORB2 --runs 5 --jobs 1
```

These commands are historical reproduction instructions, **not** a request to rerun everything now. Use existing saved runs unless a specific validity problem demands a rerun. Their success assumes the dataset directories, ground-truth files, and pySLAM environment are configured correctly.

## 5. Evaluation and outputs

- `main_slam.py` records `mean_tracking_ms`, `median_tracking_ms`, `std_tracking_ms`, processed/tracked/lost frame counts, and exports `map_observations.csv` when ground truth is available.
- `scripts/trajectory_errors.py` evaluates ATE with and without fitted scale and reports the similarity scale.
- `scripts/coursework_rpe.py` computes approximate 1-second translational RPE using input timestamps. By default it uses fitted-scale alignment; pass `--no-scale-align` for a rigid-alignment diagnostic.
- `scripts/coursework_replica_reference.py` and `scripts/coursework_tum_reference.py` associate exported observations with reference depth images.
- `scripts/coursework_map_depth.py` scores depth agreement for valid 0.1–5.0 m reference depths, applying a fitted scale for monocular map diagnostics.

Example post-processing commands (adjust paths/run numbers):

```bash
RUN=results/eval_YYYY_MM_DD-HH_MM_SS/ORB2/room0/iteration_0
pixi run -e default-cpu python scripts/coursework_rpe.py "$RUN/plot/trajectory_final.json" --timestamps data/replica/room0/times.txt --delta-seconds 1.0 --json-output "$RUN/coursework_rpe.json"
pixi run -e default-cpu python scripts/coursework_replica_reference.py "$RUN/map_observations.csv" --output "$RUN/map_depth_reference.csv"
pixi run -e default-cpu python scripts/coursework_map_depth.py "$RUN/map_depth_reference.csv" --scale 1 --output "$RUN/map_depth_scores.json"
```

For **monocular** map-depth scoring, replace `--scale 1` with that run's fitted trajectory scale. Using ground truth to fit scale is valid for *diagnostic scoring*, not evidence that monocular SLAM recovered metres itself.

## 6. Existing experiment results (not stored in this patch)

The following folders were recorded on the original machine:

| Configuration | Original local results folder | Runs |
|---|---|---:|
| KITTI C++ mono | `results/eval_2026_10_30-15_42_06` | 5 |
| KITTI Python mono | `results/eval_2026_10_30-15_57_04` | 5 |
| TUM C++ mono | `results/eval_2026_10_31-18_39_58` | 5 |
| TUM C++ RGB-D | `results/eval_2026_10_31-19_17_20` | 5 |
| Replica C++ mono | `results/eval_2026_11_02-17_00_25` | 5 |
| Replica C++ RGB-D | `results/eval_2026_11_02-17_26_25` | 5 |

Additional **single-run** TUM map exports: `eval_2026_11_02-18_35_51` (mono) and `eval_2026_11_02-18_38_13` (RGB-D). Keep these separate from the original five-run batches when reporting variability.

Selected five-run findings for orientation (see original result files before final publication): KITTI C++ tracking-call latency ~37.73 ms versus Python ~203.55 ms; TUM one-second translational RPE ~0.01458 m (mono) versus ~0.009408 m (RGB-D); Replica one-second RPE ~0.004400 m (mono) versus ~0.003566 m (RGB-D).

## 7. How Parts 2–4 build on this work

- **Part 2:** Run one learned-depth network on each image; save depth maps; evaluate depth on TUM and Replica; estimate feature-point depth, uncertainty and scale. Reuse frame ordering/calibration and the dataset depth references. Agree on the depth-map encoding and per-keypoint format with the Part 3 teammate.
- **Part 3:** Take the learned-depth outputs of Part 2 into SLAM. First run *pseudo RGB-D*, then implement at least two new integration methods and vary depth-trust parameters. Compare against Part 1 baselines with the same evaluation protocol. `slam-evaluation --predicted-depth` supports a three-way mono/RGB-D/pseudo-RGB-D comparison for TUM-format sequences.
- **Part 4:** Use map observations, triangulated point depths, predicted depths and keyframe associations to analyse disagreement, parallax, temporal consistency and selective depth use. The current Part 1 map-depth scripts are a starting point, not a complete Part 4 implementation.

## 8. Outstanding checks / limitations

1. Verify that exported `keyframe.id` maps to the correct image/association row for Replica and TUM.
2. Verify the coordinate convention of `keyframe.pose()` and that the exported map Z is camera-frame optical depth.
3. Confirm the mapping backend is quiescent when final map observations are exported.
4. Check the correct depth encoding/conversion is applied exactly once (Replica factor 6553.5; TUM factor 5000).
5. Preserve both scale-fitted and metric/rigid trajectory evaluations and describe them accurately. Current one-second RPE defaults to scale alignment.
6. `mean_tracking_ms` measures the synchronous `slam.track()` call, not full pipeline latency. Depth-prediction inference costs must be measured separately or included in an explicitly defined end-to-end timer.
7. Current final trajectories/experiment configurations may use KITTI format; the coursework submission specifically requires estimated trajectories for **every run in TUM format**.
8. Results CSV needs one row **per run**, not only group means, with all required metrics and method settings. The present patch does not create that final consolidated CSV.

## 9. Coursework submission (not the same as GitHub)

The team's **final** submission requires (a) an IEEE-style report, (b) a code ZIP containing the final combined Git diff against the tagged commit, depth/experiment/table/figure scripts, and a README identifying commands that regenerate each table, and (c) a per-run results CSV with TUM-format trajectories. The Part 1 patch is only the initial contribution to that final combined diff; it is **not the complete submission**. Do not include pySLAM itself, datasets, or network weights in the code ZIP. Keep the group repository private until the deadline, in line with the coursework restrictions.

## 10. Team workflow reminder

The patch is convenient for an initial handover. It is **not automatically updated** when someone changes their pySLAM checkout. For ongoing teamwork, coordinate changes in the private repository, maintain a shared source-of-truth/branching approach, and regenerate a **single final combined patch** against `302cf18` when preparing the final code ZIP. Avoid independently editing the same SLAM-core sections without coordinating merges.
