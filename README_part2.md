# COMP0227 CW1 — Part 2: Depth from One Image and Feature Points

Every command behind the Part 2 numbers and figures, in the order they were run.
pySLAM at `302cf18` (`comp0227-2026-lab04`) with `part1_changes.patch` and `part2_changes.patch` applied.
Run from the pySLAM root. CPU environments throughout (`-e depth-cpu` for the network and analysis,
`-e default-cpu` for SLAM, C++ core: `PYSLAM_USE_CPP=true`).

```bash
S=data/tum/rgbd_dataset_freiburg3_long_office_household
R=data/replica/room0
K=data/kitti06_tum
```

## 0. Data

| Sequence | Source | Prepared with |
|---|---|---|
| TUM fr3 long office household | TUM RGB-D download | `pixi run -e depth-cpu python scripts/associate.py $S/rgb.txt $S/depth.txt > $S/associations.txt` |
| Replica room0 | NICE-SLAM `Replica.zip` (`room0/results`, `traj.txt`) | `pixi run -e depth-cpu python scripts/part2_replica_to_tum.py --seq $R` |
| KITTI 06 | bundled `data/videos/kitti06` | `pixi run -e depth-cpu python scripts/part2_kitti_to_tum.py --src data/videos/kitti06 --out $K` |

KITTI settings with a depth factor (max 256 m):
```bash
cp settings/KITTI04-12.yaml settings/KITTI04-12_depth.yaml
printf '\nDepthMapFactor: 256.0\n' >> settings/KITTI04-12_depth.yaml
```

Pose check for the Replica conversion (true depth used as the "prediction"; expect change ≈ 0):
```bash
cp $R/associations.txt $R/associations_gtcheck.txt
pixi run -e depth-cpu python scripts/part2_depth_stability.py --seq $R --name gtcheck \
  --settings settings/REPLICA.yaml --factor 6553.5 --gaps 10 --step 200 --out /tmp/replica_pose_check
rm $R/associations_gtcheck.txt
```

## 1. Network choice (Depth Anything V2 small / base / large, every 100th TUM frame)

```bash
for sz in small base large; do
  pixi run -e depth-cpu depth-prediction --method DEPTH_ANYTHING_V2 --size $sz \
    --tum $S --settings settings/TUM3.yaml --step 100 --headless 2>&1 | grep Summary
done
```

## 2. Depth maps for every frame (`--save dav2b`)

```bash
pixi run -e depth-cpu models-depth
pixi run -e depth-cpu depth-prediction --method DEPTH_ANYTHING_V2 --size base \
  --tum $S --settings settings/TUM3.yaml --save dav2b --headless                       # 2488 frames
pixi run -e depth-cpu depth-prediction --method DEPTH_ANYTHING_V2 --size base --scene indoor \
  --tum $R --settings settings/REPLICA.yaml --save dav2b --headless                    # 2000 frames
pixi run -e depth-cpu depth-prediction --method DEPTH_ANYTHING_V2 --size base --scene outdoor \
  --tum $K --settings settings/KITTI04-12_depth.yaml --save dav2b --headless           # 1101 frames
```
Each writes `<seq>/depth_dav2b/` (PNG per frame, `scores.csv`, `info.json`) and `<seq>/associations_dav2b.txt`.
The printed `Summary` line gives the whole-sequence metric and scale-removed scores.

## 3. Depth at keypoints (nearest / bilinear / median)

```bash
for k in nearest bilinear median; do
  pixi run -e depth-cpu depth-prediction --tum $S --settings settings/TUM3.yaml \
    --load dav2b --keypoints $k --step 25 --headless 2>&1 | grep Summary
done
for p in 3 9; do
  pixi run -e depth-cpu depth-prediction --tum $S --settings settings/TUM3.yaml \
    --load dav2b --keypoints median --patch $p --step 25 --headless 2>&1 | grep Summary
done
for k in nearest bilinear median; do
  pixi run -e depth-cpu depth-prediction --tum $R --settings settings/REPLICA.yaml \
    --load dav2b --keypoints $k --step 20 --headless 2>&1 | grep Summary
done
```

## 4. Where the depth fails (5a)

```bash
pixi run -e depth-cpu python scripts/part2_depth_errors.py --seq $S --name dav2b --factor 5000 \
  --step 5 --out results/part2/tum_dav2b
pixi run -e depth-cpu python scripts/part2_depth_errors.py --seq $R --name dav2b --factor 6553.5 \
  --step 5 --out results/part2/replica_dav2b
pixi run -e depth-cpu python scripts/part2_kitti_examples.py --seq $K --name dav2b --pred-factor 256 \
  --out results/part2/kitti_dav2b_examples
```

## 5. Stability of a static surface (5b)

```bash
pixi run -e depth-cpu python scripts/part2_depth_stability.py --seq $S --name dav2b \
  --settings settings/TUM3.yaml --factor 5000 --gaps 1 10 30 --out results/part2/tum_dav2b_stability
pixi run -e depth-cpu python scripts/part2_depth_stability.py --seq $R --name dav2b \
  --settings settings/REPLICA.yaml --factor 6553.5 --gaps 1 10 25 --out results/part2/replica_dav2b_stability
```
KITTI: same-point stability is reported by step 7 below.

## 6. Keypoint uncertainty (5c)

```bash
# sequence-specific 4-feature models (fit on first half, check on second)
pixi run -e depth-cpu python scripts/part2_keypoint_uncertainty.py --seq $S --name dav2b --factor 5000 \
  --step 5 --out results/part2/tum_dav2b_uncertainty
pixi run -e depth-cpu python scripts/part2_keypoint_uncertainty.py --seq $R --name dav2b --factor 6553.5 \
  --step 5 --out results/part2/replica_dav2b_uncertainty
# transfer tests
pixi run -e depth-cpu python scripts/part2_keypoint_uncertainty.py --seq $R --name dav2b --factor 6553.5 \
  --step 5 --model results/part2/tum_dav2b_uncertainty/model.json --out results/part2/replica_dav2b_uncertainty_tummodel
# the general two-feature model (spread + border), fitted on Replica — used for all sequences
pixi run -e depth-cpu python scripts/part2_keypoint_uncertainty.py --seq $R --name dav2b --factor 6553.5 \
  --step 5 --features spread,border --max-depth 100 --out results/part2/kitti_sigma_model
pixi run -e depth-cpu python scripts/part2_keypoint_uncertainty.py --seq $S --name dav2b --factor 5000 \
  --step 5 --model results/part2/kitti_sigma_model/model.json --out results/part2/tum_dav2b_uncertainty_kittimodel
```

## 7. Map scale (step 7)

Monocular runs with `map_observations.csv` (Part 1 patch). TUM and Replica: the Part 1 owner's 5 mono runs
(unpacked into `teammate_part1/`). KITTI: own runs, same command as the Part 1 baseline:
```bash
PYSLAM_USE_CPP=true pixi run -e default-cpu slam-evaluation --features ORB2 --runs 3 --jobs 1
for d in results/eval_2026_11_08-15_01_39/ORB2/video_color.mp4/iteration_*; do
  pixi run -e default-cpu python scripts/coursework_rpe.py $d/plot/trajectory_final.json \
    --timestamps data/videos/kitti06/times.txt --json-output $d/coursework_rpe.json
done
```
Scale analysis:
```bash
pixi run -e depth-cpu python scripts/part2_map_scale.py --seq $S --name dav2b --factor 5000 \
  --model results/part2/tum_dav2b_uncertainty/model.json \
  --runs teammate_part1/results/*/ORB2/rgbd_dataset_freiburg3_long_office_household/iteration_* \
  --out results/part2/tum_dav2b_scale
pixi run -e depth-cpu python scripts/part2_map_scale.py --seq $R --name dav2b --factor 6553.5 \
  --model results/part2/tum_dav2b_uncertainty/model.json \
  --runs teammate_part1/results/*/ORB2/room0/iteration_* --out results/part2/replica_dav2b_scale
pixi run -e depth-cpu python scripts/part2_map_scale.py --seq $K --name dav2b --pred-factor 256 \
  --model results/part2/kitti_sigma_model/model.json --max-depth 100 \
  --runs results/eval_2026_11_08-15_01_39/ORB2/video_color.mp4/iteration_* --out results/part2/kitti_dav2b_scale
```

## 8. Loader check: pseudo-RGB-D with the saved maps (1 run each)

```bash
PYSLAM_USE_CPP=true pixi run -e default-cpu slam-evaluation --tum $S --settings settings/TUM3.yaml \
  --associations associations_dav2b.txt --features ORB2 --runs 1 --jobs 1
PYSLAM_USE_CPP=true pixi run -e default-cpu slam-evaluation --tum $R --settings settings/REPLICA.yaml \
  --associations associations_dav2b.txt --features ORB2 --runs 1 --jobs 1
PYSLAM_USE_CPP=true pixi run -e default-cpu slam-evaluation --tum $K --settings settings/KITTI04-12_depth.yaml \
  --associations associations_dav2b.txt --features ORB2 --runs 1 --jobs 1
# Replica sensor RGB-D through the TUM layout (reproduces the native-loader baseline)
PYSLAM_USE_CPP=true pixi run -e default-cpu slam-evaluation --tum $R --settings settings/REPLICA.yaml \
  --features ORB2 --runs 1 --jobs 1
# RPE and fitted scale for each run
RUN=results/eval_<date>/ORB2/<sequence>/iteration_0
pixi run -e default-cpu python scripts/coursework_rpe.py $RUN/plot/trajectory_final.json \
  --timestamps <seq>/associations_dav2b.txt --json-output $RUN/coursework_rpe.json
```

## Results → command

| Result | Section | Output |
|---|---|---|
| Network choice (small/base/large) | 1 | printed `Summary` lines |
| Whole-sequence dense scores | 2 | `<seq>/depth_dav2b/scores.csv`, printed `Summary` |
| Keypoint reading comparison | 3 | printed `Summary` lines |
| Error by depth, edges, border; figures | 4 | `results/part2/{tum,replica}_dav2b/` |
| KITTI examples and per-frame statistics | 4 | `results/part2/kitti_dav2b_examples/` |
| Frame-to-frame stability | 5 | `results/part2/{tum,replica}_dav2b_stability/` |
| Uncertainty models and validation | 6 | `results/part2/*_uncertainty*/`, `results/part2/kitti_sigma_model/` |
| Map scale, drift, same-point stability, bias by distance | 7 | `results/part2/{tum,replica,kitti}_dav2b_scale/` |
| Pseudo-RGB-D loader check | 8 | `results/eval_2026_11_08-{20_55_31,21_02_30,21_09_49,21_15_57}/` |

## Making the patch

```bash
git add -N scripts/part2_*.py settings/KITTI04-12_depth.yaml
git diff 302cf18 -- pyslam/depth_estimation/depth_sampling.py scripts/part2_*.py \
  settings/KITTI04-12_depth.yaml > part2_changes.patch
git reset -q scripts/part2_*.py settings/KITTI04-12_depth.yaml
```
