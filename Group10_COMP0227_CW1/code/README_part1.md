# Part 1 — baseline and measurement

## Inputs and configurations

inputs/part1.csv contains the original 30 selected rows: five runs each of KITTI
monocular C++/Python, TUM monocular/RGBD and Replica monocular/RGBD.
configs/part1 contains the Replica sensor configurations; TUM/KITTI use the
pinned course settings. The C++/Python backend is an explicit run setting.

## Commands

From code/, preview the baseline plan:

    python3 scripts/part1/run_baselines.py --pyslam /path/to/pyslam --tum /data/tum --replica /data/Replica/room0

The planner is dry-run unless --execute is supplied. Original-source verification:

    python3 scripts/part1/verify_sources.py --archive /external/source_inputs.zip

This checks the original 30 JSON hashes, pose identity and recomputed ATE.
build_master_results.py and make_submission_csv.py in scripts/part1 retain the
original raw-result scoring route. Shared geometry/RPE/map tools are under
scripts/shared; the combined patch installs its upstream helpers at their required
pySLAM paths.

## Report and results

    python3 scripts/report/part1.py --out /external/report_assets
    python3 scripts/submission/import_results.py --part 1

Tables I-II show means and sample SD across five runs, with original tracking-call
timing and valid/lost frame definitions. RPE is approximately one second, tolerance
0.06 s, after fitted similarity scale and excluding tracking gaps. Source poses
are GT-associated subsets; no claim that every source image has a pose is made.
The rendered room0 RGBD Sim3 mean rounds to 0.00408 m from the CSV, versus 0.00409 m
in the draft; no source metric was altered.

Hardware: Intel i5-1240P, 16 logical CPUs, 3.8 GiB RAM reported by Linux.
Submitted IDs are normalised; original IDs and trajectory filenames remain intact.
See README.md for setup, common build/validation and submission packaging.
