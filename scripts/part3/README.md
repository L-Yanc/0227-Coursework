# Part 3 source and portable runner

Imported from origin/main2 revision 94c47e1. Original hashes/source paths are in
Results/part3/provenance.json. Server-specific shell/patching scripts are archived
outside the repo. run_configurations.py replaces their launch logic with explicit
input paths and a dry-run default. Dedicated part3_plots.py is in the external
report_tools folder at the owner's request.

    python3 scripts/part3/run_configurations.py

This previews all 220 recorded attempts. Limit with --config fr3_B80E1. --execute
starts new experiments. Set PYSLAM_ROOT and CW1_DATASETS, or --pyslam/--datasets.
Historical associations use the dav2 suffix; --depth-name dav2b explicitly selects
the Part 2 owner's different naming.

part3_score.py scores original folders. part3_tum.py is the historical GT-position
matching exporter, not a certified source-timestamp exporter. New combined-patch
runs write trajectory_source.json; use scripts/submission/export_trajectory.py.
part3_points.py analyses match logs, which are not independent persistent-point
tracks. part3_lm_time.py reads original mapping logs, absent from this upload.
