# Part 1 reproducible results (30 selected baseline runs)

This directory can be copied to the PRIVATE team repository, e.g. `part1/`.
All file references in `master_results.csv` are relative to this directory.

## Contents
- `master_results.csv`: original 30-run submission results, regenerated from raw per-run metric outputs.
- `trajectories_tum/`: one eight-column TUM-format, timestamped estimated trajectory for each CSV row.
- `source_inputs.zip`: original pySLAM GT-associated trajectory JSONs (with SHA-256 manifest), recorded timing/tracking metrics, precomputed RPE and sparse map-depth scores, plus map-observation exports.
- `build_master_results.py`: computes ATE/scale from original poses, RPE from saved scores or frame timestamps, and reads tracking/timing/depth metrics.
- `make_submission_csv.py`: converts the detailed results to the required submission columns.
- `verify_part1.py`: checks that 30 file references resolve and their poses/ATE correspond to original saved experiments.
- `data/.../times.txt`, `associations.txt`: dataset timestamps used for trajectory export. Replica nominal timestamps are frame_index/25s.

## Rebuild and verify (Python 3, numpy, scipy)
Run **from this directory**:

```bash
python build_master_results.py --zip source_inputs.zip --timestamps-root . --output detailed_results.csv --trajectories-dir trajectories_tum
python make_submission_csv.py detailed_results.csv master_results.csv
python verify_part1.py
```

This regenerates the submitted CSV from original run-level outputs and the estimated TUM trajectories from the saved pose matrices; it does not rerun nondeterministic SLAM. Results should be identical to the source output to CSV precision. Do not pair unrelated newly executed SLAM trajectories with these scores.

**Important methodological limits:** The TUM trajectories contain the **GT-associated estimated poses** saved by pySLAM's original evaluator (`plot/trajectory_final.json`); they may omit a few unmatched input frames. They are unaligned estimated poses, not transformed to the ground truth. RPE used approximately 1 s with 0.06 s tolerance, and a per-run fitted similarity scale; only pose pairs without gaps are eligible. Map-depth MAE is computed over valid sparse feature observations on each method's own map (not a shared dense pixel mask). For independent re-scoring of sparse map-depth errors, the original reference depth images from the datasets and the method's per-run map observations are needed; those source observations are included in `source_inputs.zip`, but dataset depth images are not included, as required by the coursework.

The CSV has only the 30 **selected** baseline runs, five per configuration. Earlier archived TUM runs and teammates' later experiments require separate inclusion if they are reported as coursework results; the submission specification calls for all reported runs.

Original pySLAM git commit: `302cf18`. CPU for these runs: Intel i5-1240P, 16 logical CPUs; Linux environment reports 3.8 GiB RAM. Tracking time is `slam.track()` wall-clock duration, not end-to-end processing.
