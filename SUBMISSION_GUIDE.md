# Submission guide — Stage 2 artifacts ready; PDF deferred

Current Group10_COMP0227_CW1 contents:
- code/: inspectable working sources, retained here at the owner's request.
- code.zip: current candidate code archive (410 files; approximately 13 MB).
- results.csv: 397 per-run records.
- trajectories_tum/: 397 matching estimated trajectories.

## Exact eventual upload set

1. Approved report.pdf — intentionally absent until the owner supplies it.
2. code.zip.
3. results.csv.
4. trajectories_tum/ (archive it only if the actual form requires that format).

The unzipped code/ is the source of code.zip; do not upload a second code copy
unless explicitly requested by the form. Do not upload _assembly, _preserved,
this guide or the repository wholesale. Audit and preservation stay outside
Group10_COMP0227_CW1.

## Counts and validation

Part 1: 30; Part 2: 7; Part 3: 220; Part 4 own: 35; standard: 105.
All 397 trajectories resolve relative to the group folder. Part 1 paths use
trajectories_tum/part1; Part 3 .txt files use eight-column TUM format.

The final Part 3 source (41bde4c) is included, with corrected RPE and supplied
tracking/depth metrics. The code ZIP contains a validated 24-file combined diff,
portable reproduction scripts, original score exports, calibration/reference
evidence and lightweight plot inputs. It excludes raw sequences, videos, weights,
dense map collections, environments, Git metadata and historical packages.

The CSV rebuilds byte-identically from extracted code. All 55 existing unit/
integration tests pass. Detailed checks/limits: _assembly/stage2_report.md.
The phone reference is approximate. Raw sources for 160 historical Part 3 runs
and checkpoint binary hashes remain stronger-reproducibility limitations.

## Current draft report coverage

The owner's draft PDF is present under its original filename and remains unchanged.
All three figure images, seven table snippets, generating scripts and saved inputs
are now included in code.zip. From code/, run:

    python3 scripts/report/reproduce_report.py

See code/report_assets/manifest.json and _assembly/report_draft_review/README.md.
The current eight-page draft exceeds the body page limit. Table III's every-frame
wording needs clarification against its stride-five saved evaluation. Final approval
and any subsequent report revisions remain pending.

## Current naming and source layout

Submitted run IDs are standardised; source_run_id retains original identities.
The 397-row CSV differs only in run_id. Original input CSVs/trajectories and all
report images/table snippets are unchanged. code/ has five root READMEs; setup is
in README.md. Configs/scripts/tests/import/report interfaces are organised
consistently. See _assembly/uniform_layout/summary.md.

## Artifact hashes

code.zip: 10b45985ef0d6d713fb1dfafaafb7e76900c5b708fac61db8f1e4376facbf467 (13003190 bytes)

results.csv: b949156cd189177bbb9b3408b3ffb3239c54ca86e630bd5d02d6e0e80f6ad039 (489673 bytes)

Code ZIP files: 410. Final report approval/formatting and Part 2 hardware clarification remain pending.
