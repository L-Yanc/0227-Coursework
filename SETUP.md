# Installation and input paths

Use the course installation instructions to build pySLAM and its native modules.
The complete upstream source and dependencies are deliberately not vendored here.
The original working machine has an existing default SLAM environment and a
separate depth environment. A complete new native installation was not rerun
during submission assembly.

## Apply the combined research changes

Start from a clean course pySLAM checkout at the tagged revision. Preserve any
existing work; the commands below are for a clean checkout.

```bash
export CW1_REPO="$(pwd)"
export PYSLAM_ROOT="/absolute/path/to/pyslam"
git -C "$PYSLAM_ROOT" rev-parse HEAD
# Expected: 302cf18bb15a7f9dd5363e1f7a75f9bb648ad72b
git -C "$PYSLAM_ROOT" apply --check "$CW1_REPO/patches/coursework_changes.patch"
git -C "$PYSLAM_ROOT" apply "$CW1_REPO/patches/coursework_changes.patch"
```

`patches/validation.json` records pristine-source application and syntax checks.
The three original machine-specific setup fixes are excluded from this research
patch. This check is not a claim that every platform's native build was tested.

`requirements-analysis.txt` covers saved-data tools. SLAM and depth inference use
the course's pixi environments and network weights, installed separately.

The Part 4 launcher uses `$PYSLAM_ROOT/.pixi/envs/default/bin/python`. Override
`CW1_PYTHON` for the parent CLI, `CW1_SLAM_ENV` / `CW1_DEPTH_ENV` for pixi environment
names, or `CW1_SLAM_PYTHON` / `CW1_DEPTH_PYTHON` for explicit worker interpreters.
This supports installations named `default-cpu` and `depth-cpu` as well.

## Inputs kept outside Git

```bash
export PART4_ROOT="$CW1_REPO"  # root for relative input/work paths
export CW1_TUM_FR3="/data/rgbd_dataset_freiburg3_long_office_household"
export CW1_REPLICA_ROOM0="/data/Replica/room0"
export CW1_KITTI06="$PYSLAM_ROOT/data/videos/kitti06"
```

- TUM needs RGB/depth, `associations.txt` and `groundtruth.txt`.
- Native Replica needs `results/frame*.jpg`, `results/depth*.png` and `traj.txt`.
  Its nominal timebase is 25 Hz. Depth encoding factor is 6553.5.
- KITTI needs the course colour video, `times.txt` and `06.txt`.
- Part 3's original runner expects the separately prepared TUM-format folders
  beneath `CW1_DATASETS`: TUM, `replica_room0_tum`, `kitti06_tum`. Conversion tools
  are supplied under `scripts/part3/` and `scripts/part2_*`.
- Part 4 expects the unedited room/calibration videos under `part4/input/`, or
  absolute paths in a copied config. They are sequences, excluded from the code ZIP.
  Their original hashes and camera/marker metadata are in `Results/part4/own/`.

COLMAP, FFmpeg and FFprobe can be on PATH. Alternatively set `CW1_RECON_BIN`, or
individual `CW1_COLMAP`, `CW1_FFMPEG`, `CW1_FFPROBE` executable paths. They are used
only for media/reference preparation, not saved-result CSV validation.

The original own-sequence run used an iPhone 15, 1920×1080 source video, 1280×720
prepared images and a target 10 fps with real PTS. The checkerboard has 8×6 inner
corners, 11.5 cm across nine squares. The marker distances are 1.005 m for scale
and 0.500 m for checking, with ±0.005 m measurement bounds. Reproduction configs
keep the original 1.5× pacing and five repetitions.

## Lightweight checks

```bash
./run-part4 doctor
./run-part4 test
python3 -m unittest discover -s scripts/submission/tests -v
```

The Part 4 suite includes source/dataset integration checks and needs the pinned
installed pySLAM and the standard input files. Synthetic test directories are
temporary and separate from saved experimental results. Full experiments require
the explicit commands in the part READMEs.
