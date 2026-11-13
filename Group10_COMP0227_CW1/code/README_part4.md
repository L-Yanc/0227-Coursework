# Part 4 — agreement, frame scheduling and own recording

## Inputs and configurations

inputs/part4.csv contains all 140 attempts: seven configurations, five repeats
on TUM, Replica, KITTI and the own room. configs/part4/living_room.json is the
recorded final configuration. Copy it outside the submission folder and change
media/work paths for deliberate reproduction. Older pilot configurations are not
included in the submission.

reference contains the own approximate trajectory, camera/calibration, marker and
quality evidence. inputs/part4 contains the fixed report bin summaries/failure
traces; report_assets contains the exact draft figures.

## Commands

    ./run-part4 --help
    ./run-part4 doctor --config /external/living_room.json
    python3 scripts/report/part4.py --out /external/report_assets
    python3 scripts/submission/import_results.py --part 4

run/run-standard/run-all are explicit long operations, not CSV rebuilding.
Set PYSLAM_ROOT, PART4_ROOT and standard dataset overrides as described in README.md.
Part 4's adapter imports final Part 3 evidence for comparisons; it does not use
the removed historical branch snapshot.

## Methods and measurement


The seven configurations are mono; pseudo RGB-D every/stride-five; Part 3 B80+E1
every/keyframes/stride-five; and B80+E1 keyframes with online temporal rejection.
E1 initializes map scale from learned depth. B fills rejected low-parallax matches
passing existing checks, with an 80th-percentile gradient-uncertainty cutoff.
Triangulated points take precedence; there is no persistent learned-depth constraint.
B80+E1 was chosen before own scoring to exercise both hooks, not as a universal winner.

The temporal gate uses current online poses and deployable map scale, developing on
the first half of input time then freezing median + 3 x 1.4826 x MAD, with a 0.05
floor and at least 30 samples. It does not use reference poses or GT-fitted scale.
Offline final-map diagnostics are distinct from these online insertion decisions.

DAV2 base uses indoor Hypersim/outdoor Virtual KITTI weights at input size 518.
Depth factors: TUM/phone 5000, Replica 6553.5, KITTI 256. All RGB frames enter
tracking. All methods use corrected 1.5x pacing with original timestamps. Five
independent processes measure variability; no deterministic seed is claimed.
Cached depth supports request-count/inference-cost estimates, not measured online
speedup. New RPE uses approximately one second; gaps are excluded.

The 80.5 s room video produced 805 prepared frames, 1280x720, target 10 fps using
original PTS. Calibration used matching phone settings and 8x6 checkerboard inner
corners, 11.5 cm across nine squares. COLMAP registered 789/805 frames (98.0%),
with a largest gap of 1.5 s. Scale uses the 1.005 m wall pair; the held-out 0.500 m
pair reconstructs as 0.53987 m. Measurement bounds are +/-0.005 m. Centres are tape
cross intersections. This shared-image reference is approximate, not centimetre
truth. The user's prediction/timing is left for the report and is not invented.


## Report and provenance

Table VII and Figures 2-3 regenerate from saved inputs; no new inference is needed.
The snapshot images match the supplied draft PDF. Font/layout changes may affect
new raster output. Fitted-scale agreement is not independent metric accuracy;
the own COLMAP reference and held-out marker discrepancy remain explicit.

Hardware: Apple M5 Pro, 24 GB RAM, DAV2 base/MPS. Cached prediction cost estimates
are separate from measured tracking-call latency. Normalised submitted IDs retain
all scheduling/temporal distinctions; source IDs/cache paths remain unchanged.

The 55 shared/Part 4 tests are centralised under tests/ and run with
python3 tests/run_tests.py. One historical patch fixture is required by the
core-overlay regression test; unused result snapshots are excluded.
