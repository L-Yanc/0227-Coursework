# COMP0227 Coursework 1 — Group 10

This code package contains the combined pySLAM patch, four source-result CSVs,
reproduction scripts, report assets and tests. The artifact root is the parent
directory containing results.csv and trajectories_tum/.

- [Part 1: baselines](README_part1.md)
- [Part 2: learned depth](README_part2.md)
- [Part 3: depth integration](README_part3.md)
- [Part 4: scheduling and agreement](README_part4.md)

## Layout

| Directory | Contents |
|---|---|
| configs/part1 through part4 | Experiment settings and fitted uncertainty models |
| scripts/part1 through part4 | Each part's run/scoring/preparation tools |
| scripts/shared | Common alignment, RPE, reference and map-export utilities |
| scripts/submission | Common import, CSV build, validation and packaging |
| scripts/report | Matching part1.py through part4.py renderers |
| inputs | Four original CSVs and supplementary saved evidence |
| reference | Own approximate trajectory, calibration/marker QA and standard GT |
| report_assets | All three draft figures, seven tables and numbered source map |
| tests | Submission and Part 4 suites, with one required patch fixture |
| patches | One combined research diff and consistent four-part provenance |

## Setup

Use Python 3.11+ and the course pySLAM checkout at comp0227-2026-lab04,
commit 302cf18bb15a7f9dd5363e1f7a75f9bb648ad72b. Install saved-analysis dependencies:

    python3 -m pip install -r requirements-analysis.txt

CSV building/validation use the Python standard library. Plots use NumPy,
Matplotlib, SciPy/evo; raw depth scripts also need OpenCV (4.13.0 in the checked
course environment). Full pySLAM, native pixi environments, network weights,
datasets and raw videos are external.

Apply the combined diff to a separate clean checkout:

    export PYSLAM_ROOT=/absolute/path/to/pyslam
    git -C "$PYSLAM_ROOT" apply --check "$PWD/patches/pyslam_changes.patch"
    git -C "$PYSLAM_ROOT" apply "$PWD/patches/pyslam_changes.patch"
    python3 scripts/submission/verify_patch.py --pyslam "$PYSLAM_ROOT"

The 24-file patch combines all four contributions; provenance.json lists them
with the same fields. Null individual revisions mean not supplied, while original
patch hashes identify each contribution. Machine-only install fixes are excluded.
A new clean native build/full experimental rerun is not claimed.

## Results and identifiers

    python3 scripts/submission/build_results.py
    python3 scripts/submission/validate.py

Expected: 397 unique rows/trajectories: 30, 7, 220 and 140 from Parts 1-4.
Run IDs use p<part>_<sequence>_<configuration>_r<NN>. Configuration includes batch,
backend, trust and scheduling distinctions when needed. The original exporter ID
is retained in source_run_id. inputs/part1.csv through part4.csv remain unchanged.
Trajectory filenames and scientific cache keys retain their original names.

The first 14 columns follow the brief. Extra columns preserve source identities,
one-metre RPE, playback wall time, timestamp provenance and offsets. Tracking-only
time excludes cached depth generation; unavailable metrics remain blank.
Do not pool the different model/hardware/timing protocols across parts.

Use the same per-part import command for any source export:

    python3 scripts/submission/import_results.py --part 1
    python3 scripts/submission/import_results.py --part 2
    python3 scripts/submission/import_results.py --part 3
    python3 scripts/submission/import_results.py --part 4

Add --out /external/partN.csv to write a derived normalised per-part table.
--inputs and --group select alternate roots. Raw source-package verification has
separate verify_sources.py tools in scripts/part1 and scripts/part2.

## Report reproduction

    python3 scripts/report/reproduce_report.py

Or render one part with the same interface:

    python3 scripts/report/part1.py --out /external/report_assets
    python3 scripts/report/part2.py --out /external/report_assets
    python3 scripts/report/part3.py --out /external/report_assets
    python3 scripts/report/part4.py --out /external/report_assets

All accept --group when trajectories live elsewhere. The combined command defaults
to the sibling ../../_assembly/report_assets/current_draft directory. It renders
saved evidence only: no SLAM, depth inference or reconstruction.

report_assets/manifest.json maps Tables I-VII and Figures 1-3 to scripts/inputs.
All exact draft figure images and table snippets are included. LaTeX snippets
need booktabs and graphicx. New renderings may differ in fonts/layout. Figure 1
uses submitted TUM/GT when historical selected-run JSONs are absent; the exact
published image remains included. Table III's saved evaluation samples every
fifth frame (498 TUM, 400 Replica); distinguish these from source sequence counts.
The draft's page limit and final approval remain report-owner tasks.

## Tests and packaging

    python3 tests/run_tests.py
    python3 scripts/submission/package_release.py

The 55 tests cover source-frame associations, geometry, scheduling, logging and
cache/CSV guards. Integration checks require PYSLAM_ROOT and standard datasets.
They do not run full SLAM batches. tests/fixtures/part3_historical.diff is retained
only because the core-overlay regression test requires the pre-integration base.
Unused historical snapshots are excluded from the package.

code.zip contains code/ only, with CRC/hash/extraction checks. Previous different
outputs are archived outside the submission folder. Required uploads are the final
report PDF, code.zip, results.csv and the matching trajectories. Do not upload
the audit/preservation trees or duplicate unzipped code unless requested.

## Runtime paths and limits

For deliberate Part 4 experiments set PART4_ROOT to an external writable work/input
root, PYSLAM_ROOT to the installation, and CW1_TUM_FR3, CW1_REPLICA_ROOM0,
CW1_KITTI06 to data paths. CW1_PYTHON and CW1_SLAM_ENV/CW1_DEPTH_ENV or explicit
worker Python variables select environments. CW1_RECON_BIN or CW1_COLMAP,
CW1_FFMPEG, CW1_FFPROBE select preparation tools. Put TMPDIR/MPLCONFIGDIR in a
writable external work directory where necessary.

Hardware/model records are in protocols/hardware_and_metrics.json. Final Part 2
hardware is explicitly unconfirmed; Part 3's GPU statement must not be assigned
to it. Original raw folders for 160 Part 3 runs and checkpoint binary hashes are
not bundled, limiting complete independent historical rescoring. The own reference
is approximate, with an independent marker disagreement; see Part 4.
