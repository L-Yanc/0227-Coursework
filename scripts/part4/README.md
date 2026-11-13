# Part 4: completed experiment

All 140 attempts are scored and analysed: seven configurations, five runs each,
on TUM fr3, Replica room0, KITTI 06 and the new living-room recording. No further
recording, annotation or full batch is required for submission assembly.

Results/part4_all_results.csv contains all 140 runs. Its aggregate companion gives
mean, sample SD, median and n. Results/part4/ retains final calibration/reference,
raw frame states, runtime metadata and compact point/depth analyses. All final
trajectories are under trajectories_tum/part4/. The failed original recording,
pilot/preflight outputs and large observation logs are archived outside Git.

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

## Saved results

    python3 scripts/submission/build_results.py
    python3 scripts/submission/validate.py --allow-missing

These commands process saved data only. Part 4 has no missing final trajectories.
The 30 missing files reported by the full validator belong to Part 1. Dedicated
report scripts are outside this repo at the owner's request.

## Deliberate reproduction only

Follow SETUP.md, provide the original media, and use a copied config with a fresh
experiment ID/output directory. The supplied fast config has publish_results=false
so a new master export preserves the submitted 360-row source table.

    ./run-part4 doctor
    ./run-part4 calibrate
    ./run-part4 prepare
    ./run-part4 reference
    ./run-part4 annotate
    ./run-part4 preflight
    ./run-part4 run --reuse-prepared
    ./run-part4 check-standard
    ./run-part4 run-standard

check-standard performs preparation and short representative workers. run and
run-standard are the long 35/105-attempt batches. Content hashes checkpoint work.
The console prints attempt counts, durations and five-minute heartbeats. Validated
complete exports can be recovered from shutdown-only hangs; incomplete outputs
are not declared successful. The CLI has a 30-minute attempt limit and batch lock.
No long batch was launched during submission cleanup.
