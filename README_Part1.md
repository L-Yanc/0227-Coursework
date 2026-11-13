# Part 1 baseline

The original 30-row score table is `Results/part1_submission_results_30.csv`.
Its matching trajectories are still missing. See `MISSING_INPUTS.md` for the eight
source batches. The November 8 archive on main2 contains different runs and cannot
supply trajectories for these scores. Existing measurements are preserved.

`patches/coursework_changes.patch` combines the Part 1 tracking-call timer/map
exporter and scoring helpers with later research changes. It adds full original
pose/timestamp export in `trajectory_source.json` and keeps exported frame IDs
aligned when GT association drops initial or interior poses.

## Reproduction

After `SETUP.md`, preview the six five-run configurations:

    python3 scripts/part1/run_baselines.py

They are KITTI C++/Python monocular, TUM C++ monocular/RGB-D, and native Replica C++
monocular/RGB-D. Pass --tum, --replica and --pyslam, or use the documented environment
variables. --execute explicitly starts 30 new attempts. It does not reconstruct the
missing originals or replace their scores.

The combined patch installs scripts/coursework_rpe.py (timestamp-based RPE),
coursework_export_map.py (source image IDs and camera optical Z),
coursework_tum_reference.py, coursework_replica_reference.py and
coursework_map_depth.py. Upstream scripts/trajectory_errors.py measures ATE with
and without fitted scale. Map-depth scoring uses valid 0.1–5.0 m reference depth.

For a new run, export the actual source timestamps with:

    python3 scripts/submission/export_trajectory.py /path/to/trajectory_source.json /new/output.tum

The coursework-wide aggregates are rebuilt by scripts/submission/build_results.py.
They preserve backend/sensor settings and report mean, sample SD, median and n.
Tracking-call time excludes end-to-end pipeline cost. Initialization is distinct
from LOST. Confirm timestamp associations and map-export validity on the missing
original files before claiming complete error recomputation.
