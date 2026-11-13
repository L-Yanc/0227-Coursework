# Group 10 COMP0227 CW1 — three-stage submission assembly

## Layout update authorised by the owner — 13 November 2026

This update supersedes the folder placement described below. `REPO/Group10_COMP0227_CW1/` keeps the working `code/` directory and the final submission artifacts: `report.pdf`, `code.zip`, `results.csv` and `trajectories_tum/` (or a trajectory archive only if the upload form requires it).

Working code stays at `GROUP/code/` per the owner’s subsequent correction. Other working material is at `REPO/_assembly/`, `REPO/_preserved/` and `REPO/SUBMISSION_GUIDE.md`. Resolve every later instruction mentioning GROUP/_assembly, GROUP/_preserved or GROUP/SUBMISSION_GUIDE.md to these sibling REPO locations instead. Keep report assets, fixtures, temporary checkouts, audit logs and intermediate outputs outside GROUP. The code ZIP is built from GROUP/code; its finished archive is placed inside GROUP. Keep code inside GROUP; keep audit, preservation and temporary folders outside GROUP.

Stage 1 is complete. Its original inventories are historical evidence; subsequent owner/assistant relocations are recorded separately in `REPO/_assembly/layout_updates/`. This layout update does not start Stage 2 or Stage 3.

## Task and authority

Execute the following three stages in order when asked to implement this handoff. The user explicitly authorises moving existing submission-related material from the current repository into `Group10_COMP0227_CW1`, implementing locally possible assembly work, and preparing submission artifacts. This document itself is instructions only: its creation has not performed any moves.

**Nothing may be deleted.** Preserve all tracked/untracked work, old packages, source results and provenance. Move existing relevant files rather than leaving duplicates in their old repository locations. Copies inside generated archives or isolated validation fixtures are allowed. Never overwrite a non-identical file; preserve its previous version under a versioned path first. Do not reset/clean Git, merge unrelated branches, commit, push or submit to Moodle. Do not launch new SLAM/depth/reconstruction batches merely to assemble the submission. Do not modify a running worker/terminal.

Repository root, called REPO below:

`/Users/l_yanc/Desktop/UCL 4/UCL 4.1/0227 Situational Awareness/0227 CW1/0227 Coursework`

Coursework installation root, called CW below: REPO's parent. Remain inside `/Users/l_yanc/Desktop/UCL 4/UCL 4.1/0227 Situational Awareness` for all new work, including temporary validation checkouts. Downloads may be read only when explicitly supplied by the user. Check applicable AGENTS.md first.

Target, called GROUP below: `REPO/Group10_COMP0227_CW1`.

## Required final structure

Table 1 of `CW/../COMP0227-Coursework1.pdf` is authoritative. Read sections 8 and 10. It requires an IEEE report PDF, ONE code ZIP containing the final diff and reproduction scripts/README, and ONE results CSV with each run's TUM estimated trajectory. It does not prescribe archive/folder names or require a trajectory ZIP. Do not invent extra compulsory deliverables.

```text
Group10_COMP0227_CW1/
  report.pdf                         # ONLY the user's approved final PDF
  code.zip                           # contents: code/ below, no full pySLAM/data/weights
  results.csv                        # consolidated per-run results, all reported attempts
  trajectories_tum/                  # paths exactly match results.csv
    ...                              # keep existing internal naming if valid
  code/                              # inspectable source used to build code.zip
    README.md
    SETUP.md                         # if useful
    patches/
      pyslam_changes.patch           # validated final combined diff vs pinned commit
    scripts/
      ...                            # actual scripts; do not rename gratuitously
    configs/
      ...
    reference/
      own_reference_tum.txt
      camera.yaml
      calibration_summary.json
      marker_scale.json
      reference_quality.json
    tests/                           # if tests are separate from script packages
    requirements-analysis.txt        # plus actual required dependency manifests
  _assembly/                         # local audit/status; NOT a Moodle deliverable
    stage1_report.md
    stage2_report.md
    stage3_report.md
    missing_inputs.md
    inventory_before.json
    inventory_after.json
    moves.csv
    validation.json
    report_artifacts.md
    ...
  _preserved/                        # historical/support material; NOT uploaded wholesale
    source_results/
    source_uploads/
    historical_packages/
    previous_versions/
    ...
```

The `code/`, `_assembly/` and `_preserved/` folders make the build inspectable and preserve everything. They are not extra required uploads. Clearly identify the upload set in a top-level submission guide. Never zip GROUP wholesale and call it the code ZIP. If Moodle requires trajectories archived, optionally generate trajectories.zip; leave original directory intact.

Keep `.git`, `.gitignore`, this instruction file and genuinely repository-level non-submission files at REPO. Do not move the Git metadata or create a nested Git repository. Leave a short root README pointing to GROUP; preserve/move the original README contents first.

## Current evidence — recheck, do not assume it remains current

At instruction-writing time (13 November 2026):

- REPO has README.md, SETUP.md, MISSING_INPUTS.md, README_Part1.md, README_part2.md, README_part4.md, configs/, scripts/, run-part4, requirements-analysis.txt, patches/, Results/, trajectories_tum/, part1/, part3/, iteration1/, iteration2/, Part 2 Results/.
- Existing modified and untracked files are substantial. Preserve working-tree contents, not just Git HEAD.
- `Results/submission_validation.json` records 397 rows: Part 1 30, Part 2 7, historical Part 3 220, own Part 4 35 and standard Part 4 105; 397 valid trajectories, no missing links. This supersedes old handoff claims of missing Part 1 trajectories. Revalidate against actual files.
- `Results/part1_import.json` and `part1/` document recovery of the original 30 matching records. Do not substitute fresh runs for old scores.
- `MISSING_INPUTS.md` still identifies methodological issues: raw folders for 160/220 historical Part 3 final runs are absent, historical timestamps were matched using GT positions, and newer one-second RPE results require an association audit before integration. These are not all mandatory file-format blockers; distinguish submission requirements from provenance limitations.
- `scripts/submission/` already contains build_results.py, validate.py, package_release.py, import_part1.py. Inspect and adapt these rather than writing competing builders.
- Part 4 report generators were previously at scripts/report/part4_tables.py and outputs at Results/part4_report/. Find them if moved. They generate exactly ONE combined results table and TWO report figures. Do not regenerate ten supplementary report tables.
- Actual Part 4 implementation/work artifacts live at CW/part4, outside REPO; installed pySLAM lives at CW/COMP0227_26-27/pyslam. Do not relocate installed environments, data or heavy work directories. Supply portable code plus configurable external input paths.
- Earlier reports exist outside REPO; do not assume a downloaded version is the approved final report. The owner previously requested the report remain outside GitHub. Ask for the chosen final file/permission if needed; do not silently publish it to GitHub.

# Stage 1 — move existing material and report remaining work

## 1.1 Inventory before moving

Read current README.md, SETUP.md, MISSING_INPUTS.md, part handovers, CW/handoff.md, latest validation/import manifests, submission scripts, and relevant report-artifact generators. Read the brief, not only this outline. Record `git status --short` and commit identities without mutations.

Create GROUP/_assembly. Inventory every relevant source file with repository-relative path, byte size, SHA-256, tracked/untracked status and symlink destination. Inventory archive contents without destructive extraction. Identify symlinks outside REPO and avoid following/copying huge environments. Record a proposed move map before moving. Exclude GROUP itself when walking REPO to avoid recursive self-inclusion.

## 1.2 Move, preserving all existing material

Move current portable code/config/manifests into GROUP/code, retaining package/import relationships. Keep runnable wrappers with their required scripts. Place individual historical patches in `_preserved/source_uploads/patches` until reviewed; do not label them as the final combined diff. Preserve any additional patch README/application-order evidence.

Move trajectories_tum into GROUP/trajectories_tum, maintaining its internal structure initially. Move Results and Part 2 Results into `_preserved/source_results` except report assets promoted into a clearly identified `_assembly/report_assets` location. Move original part READMEs/MISSING_INPUTS into preservation or incorporate useful documents into code with unchanged originals preserved. Move iteration1/iteration2/part1/part3 source uploads into `_preserved/source_uploads` unless individual runnable components must be promoted into code. Do not lose compressed logs, JSON poses, annotations, archived metrics or old ZIP snapshots.

Choose between moving an entire source directory and splitting it only after inspecting imports/data paths. For any split, record each actual file move. An identical hash at the destination does not justify deleting the source: move the source into a uniquely named preservation path instead. Preserve empty legacy files too.

Write a moves.csv with original path, new path, size and SHA-256. For renamed/edited code, preserve the exact pre-edit file first and record the new hash separately. Stage 1 should primarily organise; do not claim unresolved imports work before Stage 2 checks.

Do not move/report-link datasets, weights, .pixi, cache, full installed pySLAM or original room media into code. Existing packages containing those must be preserved outside the upload ZIP and flagged, not deleted.

After moving, verify that every inventoried relevant source exists at its mapped destination with the same hash. Record any external references now needing updates. Update the root README to point to GROUP after preserving its original contents. Do not create compatibility symlinks just to hide broken path assumptions.

## 1.3 Stage 1 report

Write `_assembly/stage1_report.md` and `_assembly/missing_inputs.md`. Include the tree actually created, verified move/hash counts, original-to-new mapping, files intentionally retained at REPO, and remaining tasks grouped explicitly:

- **LOCAL: can complete with existing code/results/information.** Identify exact source paths and intended outputs.
- **EXTERNAL: requires teammate/user input.** Give missing item, who can provide it, what format and why needed.
- **UNCERTAIN: must inspect/audit locally before requesting input.** No premature missing-file claims.

For each task, state whether it blocks a required deliverable, only a reported claim, or stronger reproducibility. Audit current 397-row evidence; do not carry over obsolete 360-row or missing-Part-1 conclusions. Stage 1 is complete only after the no-loss verification and report exist.

# Stage 2 — implement everything possible locally

## 2.1 Repair portable paths and consolidate results

Adapt existing builders, validators and wrappers to GROUP as artifact root. Portable scripts must accept dataset/work/reference paths through arguments/configuration instead of relying on this user's absolute desktop paths. Preserve original run IDs, scores, method settings and scientific cache identity. Do not edit raw metrics to improve the paper.

Build GROUP/results.csv from the verified source exports, including the Part 2 SLAM runs when appropriate. At present expected count is 397 unless source inspection proves additional legitimate runs or duplicates. Explain any count change in the audit. First 14 columns should preserve the established schema:

run_id,sequence,method,settings,run_number,ate_unscaled_m,ate_scaled_m,fitted_scale,rpe_rmse_m,fraction_tracked,fraction_lost,time_per_frame_ms,map_depth_mae_m,trajectory_file

Additional provenance/protocol fields are allowed and important. Do not place one-metre RPE into a column labelled one-second RPE or playback wall time into a tracking-only field. Retain historical values in explicitly defined additional columns if needed. Incorporate newer Part 3 metrics ONLY after timestamp/frame associations and timing definitions are audited; otherwise keep their valid historical values with transparent metadata. Missing unavailable quantities stay blank with reasons, never fabricated zeros.

Use repository-independent trajectory paths relative to GROUP. Keep existing internal trajectory layout unless renaming improves correctness; if renaming, update every reference. Validate each row's actual associated trajectory, monotonic timestamps, finite poses, eight-column TUM format, quaternion norms and unique run identity. Audit that score and trajectory identities match, not merely syntax/file existence.

## 2.2 Combined Git diff

Inspect current final source patches and actual installed modifications. Use a temporary clean pinned source checkout UNDER GROUP/_assembly or elsewhere inside the authorised coursework parent. Base: 302cf18bb15a7f9dd5363e1f7a75f9bb648ad72b. Do not reset or modify the active installed checkout to build a package.

Integrate Parts 1–4 intentionally, resolving overlapping main_slam/depth-sampling changes while preserving each required feature. Confirm teammate version provenance with local immutable uploads before declaring something absent. Include new untracked source intentionally in the final diff; plain git diff misses untracked files. In the isolated fixture, index operations are allowed; do not stage the user's working repository unexpectedly.

Generate code/patches/pyslam_changes.patch as ONE diff against the tag. Confirm `git apply --check` and actual application in a separate clean fixture. Run meaningful source/import/unit checks and available short fixture-based CLI tests. Preserve all earlier patch versions. Distinguish syntactic application success from runtime reproduction. Do not claim all experiments reproduced from clean source unless actually done. Keep installation-only changes documented separately if required; no compiled binaries, full pySLAM or heavy data in code.zip.

## 2.3 Reproduction and report artifacts

Place all final scripts/configurations necessary to generate depth, run configurations, score and rebuild every reported table/figure in code. Dependencies must be documented; keep pinned versions/checkpoints/CPU-GPU protocol where known. Gather the own-sequence metric reference, calibration and marker-quality summaries into code/reference. Do not include raw room video, image sequences or network weights. Explain how excluded input media is supplied for full reruns.

Make the Part 4 report generator write only its ONE table and TWO figures to `_assembly/report_assets/part4` (or another documented location). Update defaults to the new CSV/source paths and validate unchanged results. Preserve older generated assets under _preserved, not beside the final report assets. Use existing source tables/derived inputs for other report figures; include necessary lightweight inputs or executable derivations, not unverifiable screenshots.

Create code/README.md mapping each table/figure in the actual final report to one precise command, required inputs and output filename. If the final report is absent, create a clearly provisional mapping and list that dependency. Do not infer final numbering from an older PDF. Requirements include scripts for every reported configuration, not just the report renderer.

## 2.4 Generate candidate upload artifacts

Build code.zip from code/ only using a checked allowlist and exclusion scan. Exclude source sequences, predicted-map collections, model weights, environments, .git, old archives, personal metadata and caches. Audit ZIP entries against code source hashes and test extraction in a preserved versioned validation directory. Retain every old ZIP under _preserved/previous_versions before replacing a canonical output.

Stage report.pdf only if the user has supplied/identified an approved final report. Preserve the original chosen PDF; do not rewrite it silently or assume its academic declarations. Reconcile its metrics, citations, page count and contribution/AI statements against the brief and report issues; report problems rather than fabricate text/provenance. If report stays outside GitHub, document that it is a local Moodle artifact and respect existing user choices about version control.

## 2.5 Stage 2 report

Write `_assembly/stage2_report.md`: generated files, checks actually run/results, inventory preservation verification, and an exact list of remaining missing files/folders. For every missing item give expected destination, required contents, available partial evidence, who supplies it and how to validate it. Do not create empty report.pdf/patches with success-like filenames as placeholders. Part 3 missing raw folders/checkpoint/CPU details must be described with their actual impact; their absence is not automatically equivalent to missing estimated trajectories.

Stage 2 should finish all independent local work before requesting any necessary external input. Do not stop just because one component is blocked. Do not start heavy new experiments without explaining their necessity/load and obtaining task-appropriate authorisation.

# Stage 3 — recheck supplied data and finalise the required format

Re-read `_assembly/missing_inputs.md`, recent user messages and new files. Compare hashes/identities to Stage 2; never assume elapsed time means input arrived. Search authorised local locations and immutable teammate uploads before asking again. Validate incoming run IDs, geometry/timestamps, hardware/checkpoint provenance and patch base. Preserve incoming originals in _preserved and document import/move operations.

For each newly resolved item, regenerate ONLY dependent results/mapping/package artifacts. Preserve previous versions, and leave unchanged scientific runs cached. Keep disputed newer metrics separate until their associations are resolved. If data is still absent, complete other tasks and state the exact remaining requirement. Do not mark the submission complete on file count alone.

Verify final format:

1. Approved report.pdf opens, follows the IEEE/report requirements, ends with the required contribution statement, and discloses actual AI usage. Flag unresolved claims and page-limit issues without inventing declarations or a pre-recording hypothesis.
2. code.zip is one archive, includes the validated combined diff plus scripts/configuration/README for all parts, and excludes prohibited bulk content.
3. results.csv is one per-run table with all applicable reported runs and explicit metric protocols; every trajectory_file resolves relative to GROUP and refers to the matching eight-column TUM trajectory.
4. Own reference trajectory and reconstruction/scale limitations are included so phone errors can be recomputed. Existing approximate reference is not labelled ground truth.
5. Every final table/figure is mapped to a command with required lightweight inputs. No manual number transcription is required.
6. Every pre-assembly relevant file remains accounted for with a preserved hash or exact pre-edit version. No file was deleted. Record unexpected external changes rather than silently overwriting them.
7. Confirm existing repository ignore rules do not accidentally hide required submission files, and do not auto-commit/push private media or the report. Record Git status only.

Write `_assembly/stage3_report.md`, `_assembly/validation.json`, a final missing-input list (explicitly empty only if resolved), and `GROUP/SUBMISSION_GUIDE.md`. The guide identifies EXACT files/folders to upload: report.pdf, code.zip, results.csv and trajectories_tum (or optional trajectory archive if the Moodle form requires it). Explicitly exclude _assembly, _preserved and the unzipped code/ from that upload list. Provide counts/hashes and a concise readiness verdict separating format completeness, metric/provenance limitations and full scientific reproducibility.

If something remains missing, provide a concrete next action and owner for each item. Do not submit, publish, delete preserved material or rerun finished experiments to obtain a green status.


## Verified Part 3 final upload — supersedes earlier missing-input notes

Commit 41bde4c is local. Use part3/results/part3_results.csv as the final authoritative source in Stage 2; do not use iteration2 as the final import. See REPO/_assembly/part3_update_41bde4c/README.md and REPO/_assembly/missing_inputs.md for targeted validation, supplied hardware/model provenance and the remaining optional raw-source limitations. The combined CSV has not yet been rebuilt.
