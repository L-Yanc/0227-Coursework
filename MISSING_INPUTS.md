# Remaining inputs before submission

## Part 1: original 30 trajectories and supporting outputs

All 30 rows in `Results/part1_submission_results_30.csv` lack their matching
trajectory files. Exact run IDs/required filenames are listed in
`Results/missing_trajectories.csv`. Ask the Part 1 owner for the original TUM
exports or the complete original run folders for these batches:

- `eval_2026_10_30-15_42_06` (5)
- `eval_2026_10_30-15_57_04` (5)
- `eval_2026_11_02-17_00_25` (5)
- `eval_2026_11_02-17_26_25` (5)
- `eval_2026_11_02-18_35_51` (1)
- `eval_2026_11_02-18_38_13` (1)
- `eval_2026_11_04-19_08_08` (4)
- `eval_2026_11_04-19_36_33` (4)

Include `plot/trajectory_final.json`, full saved poses, source frame IDs/timestamps,
metrics, run configuration and map-depth outputs where available. The archive on
`main2/iteration1/part1/runs.zip` has different November 8 batches. It cannot be
used as the trajectories for these October/November scores.

The older upstream exporter zipped full frame IDs with GT-associated poses. When
GT matching drops initial/interior poses, those saved JSON IDs can be offset.
The Part 2 TUM check demonstrably had this issue and was corrected by matching its
saved poses to the full output. Part 1's timestamp/RPE association should be
verified on its genuine source files before claiming its errors are reproducible.

## Part 3: original timing/configuration provenance

The 220 scores, TUM trajectories, point logs and source scripts are present. Full
original run folders remain on the teammate's server. Ask for the exact network
checkpoint/size and input settings, machine specifications, and original pose/
timestamp outputs if available. The uploaded TUM timestamps were reconstructed
from GT positions, rather than retained directly from camera inputs.

Historical one-metre RPE and playback-inclusive time are preserved in explicitly
named columns. They are not fabricated into one-second RPE or tracking-call cost.
Raw run folders would also let the report owner rerun the original trajectory
plotting script without relying on the teammate's absolute server paths.

## Part 2 and report owner

The supplied Part 2 ZIP, analysis scripts, seven recovered SLAM trajectories and
timestamp evidence are present. The SharePoint links in `Part 2 Results/Maps.md`
are historical locations for dense predictions; their accessibility has not been
checked during this local preparation. Saved predictions are not required inside
the code ZIP, but the precise model/setup and commands must remain documented.

The complete final report is outside this repository. Its owner must supply the
finished PDF, contribution statement and AI disclosure, and confirm a command for
each final report table/figure. Dedicated report scripts were moved outside the
GitHub tree as requested; the final Moodle code ZIP can include them separately.

No further Part 4 recording, marker annotation or full batch is needed to resolve
these packaging gaps. Part 4's existing 140 runs remain unchanged.
