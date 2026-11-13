# COMP0227 Coursework 1

Research code and saved results for Parts 1–4. Starting pySLAM revision:
`302cf18bb15a7f9dd5363e1f7a75f9bb648ad72b` (`comp0227-2026-lab04`).

The final Part 4 experiment contains 140 scored runs: 35 own-room runs and
105 standard-sequence runs. The results pipeline does not rerun experiments.

## Saved results and current completeness

`Results/coursework_results.csv` is the coursework-wide table: **397 rows**:

| Source | Runs | Available TUM trajectories |
|---|---:|---:|
| Original Part 1 baseline | 30 | 0 — originals still needed |
| Part 2 saved SLAM checks | 7 | 7 |
| Historical Part 3 | 220 | 220 |
| Part 4 own sequence | 35 | 35 |
| Part 4 standard sequences | 105 | 105 |

The original measurements are retained. Missing trajectories are explicitly
listed in `Results/missing_trajectories.csv`; they are never replaced with poses
from a different run. `Results/submission_validation.json` records the checks.
Read `MISSING_INPUTS.md` before submitting. The results package remains partial.

## Layout

- `patches/coursework_changes.patch`: integrated research changes against the
  tagged commit, including Part 1 exports, Part 2 sampling, Part 3 B/E1 hooks and
  Part 4 policy/shutdown support. Apply this one patch; do not stack old patches.
- `scripts/`: exported Part 1/2 analysis tools, portable baseline/Part 3 runners,
  the Part 4 workflow and submission utilities.
- `configs/`: baseline and historical Part 3 settings.
- `Results/part1_submission_results_30.csv`: original Part 1 source table.
- `Part 2 Results/part2_results.zip`: original Part 2 evidence, kept unchanged.
- `Results/part2/`: verified trajectory conversion, scoring inputs and provenance.
- `Results/part3/`: original 220-run tables, 60 point logs and source provenance.
- `Results/part4/`: final calibration/reference, run states and compact analyses.
  Large observation logs and pilot/preflight experiments are excluded.
- `trajectories_tum/`: each available run's unaligned estimated trajectory,
  with eight columns: timestamp, tx, ty, tz, qx, qy, qz, qw.

Report files and dedicated report-generation scripts are intentionally outside
this GitHub repository at the owner's request. In the shared workspace they are
under `../report_tools/` and `../submission_archive_20261113/`. These locations are
not dependencies of the submitted experiment code. The Moodle code packager can
include the separately maintained report tools with `--report-tools`.

## Rebuild and verify saved results

Use Python 3.11+ with `requirements-analysis.txt`, or the installed course Python.
Commands are run from this repository root:

```bash
python3 scripts/submission/import_part2.py
python3 scripts/submission/build_results.py
python3 scripts/submission/validate.py
```

These commands use saved poses and scores. They do not start SLAM, inference or
reconstruction. Validation currently exits nonzero because 30 Part 1 trajectories
are absent. `--allow-missing` checks all available records while reporting that
the results are incomplete. After the genuine missing files are restored at the
listed paths, rerun the builder and validator.

`Results/coursework_aggregates.csv` gives mean, sample SD, median and sample count
for each part/sequence/method/settings/metric. It also counts missing trajectories.
Part 4-only source tables remain `Results/part4_all_results.csv` (140 rows) and
`Results/part4_all_aggregates.csv`. The 360-row Part 3/4 source table is preserved
separately; its 35 own rows must not be added a second time.

## Protocols that must stay separate

- ATE without scale is translation RMSE after rigid alignment. Scale-corrected
  ATE uses one global Sim(3) alignment; `fitted_scale` is its scale factor.
- Fresh Part 4 RPE uses approximately one second, corrected by the fitted scale,
  and excludes pairs across tracking/reference gaps. Part 1/2's timestamp-based
  scorer additionally requires consecutive source frame IDs between the pair.
- Historical Part 3 RPE is over **one metre**. It is retained in `rpe_1m_m`;
  its canonical one-second RPE field is blank. Its playback-inclusive wall time
  is retained in `source_wall_time_per_frame_ms`, not relabelled as tracking cost.
- Part 3 timestamps were reconstructed by the teammate from GT positions. Syntax
  validation does not certify source-image timing. Original outputs are requested.
- Tracking fractions retain each source evaluator's denominator and are labelled
  in `tracking_fraction_basis`. Initialization is not automatically counted as LOST.
- Part 4 time is the synchronous tracking call. Cached runs do not measure online
  network inference end to end. Separate inference estimates are in run metadata.
- KITTI and the phone have no sensor-depth truth here. Their map-depth MAE is
  unavailable. Part 2 checks have not had map-depth MAE recomputed in this assembly.
- The own-room reference is approximate COLMAP: 98.0% coverage; the held-out
  0.500 m marker reconstructs as 0.53987 m. It is not centimetre-accurate truth.

## Reproduce experiments

Follow `SETUP.md`, then the relevant part README. Both new baseline runners are
dry-run planners unless `--execute` is supplied:

```bash
python3 scripts/part1/run_baselines.py
python3 scripts/part3/run_configurations.py
./run-part4 --help
```

New results are new experiments. Historical scores are not replaced merely because
hardware, pacing, model versions or asynchronous scheduling produce different runs.

## Build submission archives

```bash
python3 scripts/submission/verify_patch.py --pyslam "$PYSLAM_ROOT"
python3 scripts/submission/package_release.py --out ../submission_ready_20261113 \
  --report-tools ../report_tools
```

The code ZIP excludes pySLAM itself, sequence media, network weights, environments
and caches. The results ZIP includes the per-run table, provenance and available
trajectories. It is named `results_partial.zip` while files are missing. A code
draft and GitHub repository do not replace the final Moodle submission.

The separate final report must be IEEE conference format, at most five pages
excluding references, and include contributions and AI-use disclosure. Its owner
must map the final paper's actual table/figure numbers to commands. Existing Part 2
commands and external Part 4 report tools cover the supplied material, not an
unseen final paper. Keep the research changes private until the deadline.
