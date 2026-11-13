# Part 2 — learned depth and uncertainty

## Inputs and configurations

inputs/part2.csv contains seven saved SLAM evaluations. The separate final
DAV2-base analysis for Tables III-V is in inputs/part2_report: per-frame errors,
held-out model validation, stability pairs and per-run/keyframe scale summaries.
Fitted uncertainty models are centralised under configs/part2. Model JSONs record
feature selection, calibration and training provenance.

inputs/part2_depth and plot_saved_exploratory.py are older DAV2-large exploratory
evidence. They are distinct from the final base-model report measurements.
Final Part 2 CPU/RAM/inference device and timing environment still need teammate
confirmation; they have explicit unknown fields in the hardware metadata.

## Commands

    python3 scripts/report/part2.py --out /external/report_assets
    python3 scripts/submission/import_results.py --part 2
    python3 scripts/part2/verify_sources.py --archive /external/part2_results.zip --timestamps /external/timestamps --out /external/new_fixture

The verifier reimports/scores seven saved runs into a fresh fixture, without SLAM.
Raw depth analysis tools all live in scripts/part2:
- part2_depth_errors.py: --seq, --name dav2b, --factor, --step 5, --out.
- part2_keypoint_uncertainty.py: --seq, --name dav2b, --factor, --features,
  --model for transfer and --out.
- part2_map_scale.py: --seq, --name dav2b, --factor, --model, --runs and --out.
- part2_depth_stability.py and part2_kitti_examples.py: temporal and outdoor checks.
- part2_replica_to_tum.py and part2_kitti_to_tum.py: data conversions.
- part2_sigma.py and part2_stability.py: exploratory keypoint/scale analyses.

Each raw tool provides --help. It needs external RGB/depth and the saved predicted
depth maps. Prediction factors are TUM 5000, Replica 6553.5 and KITTI 256.
Original source settings embedded in summaries describe historical paths; current
model files are under configs/part2.

## Report definitions

Table III uses stride-five saved scoring: 498 TUM and 400 Replica samples from
2488/2000 source frames. The draft's every-frame wording needs clarification.
Table IV uses held-out uncertainty scores and the model fitted on the first half
of the sequence, with original transfer checks. Table V uses run means/sample SD;
its drift interval spans the per-run 10th/90th quantile bounds. No numbers are
transcribed manually and no missing KITTI sensor-depth MAE is fabricated.

See README.md for common setup, identifiers, validation and packaging.
