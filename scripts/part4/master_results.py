"""Part 3 + Part 4 master CSV, preserving different RPE/time definitions."""
import json
import math
from pathlib import Path
import shutil
from common import ROOT,TEAM,Blocked,artifact,read,rows,dump,table,digest,fingerprint
from geometry import read_tum
from scoring import FIELDS

EXTRA=['source_part','source_run_id','source_sequence','source_configuration','rpe_protocol','rpe_1m_m','source_wall_time_per_frame_ms','tracking_fraction_basis','trajectory_timestamp_provenance']


def canonical_sequence(value):
    v=value.lower()
    if 'kitti' in v:return 'KITTI 06'
    if 'replica' in v or 'room0' in v:return 'Replica room0'
    if 'freiburg3' in v or 'tum' in v or 'fr3' in v:return 'TUM fr3'
    return 'own' if v=='own' or 'living_room' in v else value


def clean_number(value,factor=1.):
    try:
        number=float(value)
        return number*factor if math.isfinite(number) else ''
    except (ValueError,TypeError):return ''


def historical_row(r,trajectory):
    row=dict.fromkeys(FIELDS+EXTRA,'')
    rid=f"part3_{r['config']}_{r['mode']}_{r['seq']}_r{r['run']}"
    row.update(run_id=rid,sequence=canonical_sequence(r['seq']),method=r['config']+':'+r['mode'],settings=json.dumps({'source':'teammate iteration2','configuration':r['config'],'sensor_mode':r['mode'],'source_row':r},sort_keys=True),run_number=int(r['run'])+1,
               ate_unscaled_m=clean_number(r['ate_se3_m']),ate_scaled_m=clean_number(r['ate_sim3_m']),fitted_scale=clean_number(r['scale']),fraction_tracked=clean_number(r['pct_tracked'],.01),fraction_lost=clean_number(r['pct_lost'],.01),trajectory_file=trajectory,
               source_part='part3',source_run_id=f"{r['config']}/{r['mode']}/{r['seq']}/{r['run']}",source_sequence=r['seq'],source_configuration=r['config'],rpe_protocol='1 metre; historical',rpe_1m_m=clean_number(r['rpe_1m_m']),source_wall_time_per_frame_ms=clean_number(r['wall_s_per_frame'],1000.),tracking_fraction_basis='teammate percent_tracked / 100; historical evaluator denominator',trajectory_timestamp_provenance='teammate GT-position matching; not certified source-image timestamps')
    # Canonical RPE and tracking-call time are intentionally blank: the old
    # distance-interval RPE and playback-inclusive wall time have separate columns.
    return row


def copy_trajectory(source,dest):
    read_tum(source);dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists() and digest(dest)!=digest(source):raise Blocked(f'Trajectory already exists with different bytes: {dest}')
    if not dest.exists():shutil.copyfile(source,dest)


def export_master(c,work,allow_partial=False):
    imported=artifact(work,'part3_import');evaluation=artifact(work,'evaluation')
    standard=work/'standard_reruns/part4_standard_results.csv'
    if not allow_partial:
        status=read(work/'standard_reruns/status.json')
        if not status.get('full_standard_part4_completed'):raise Blocked('Master export waits for all requested standard attempts')
    result=[];inputs={}
    source_csv=imported/'runs.csv';inputs[str(source_csv.relative_to(ROOT))]=digest(source_csv)
    for r in rows(source_csv):
        name=f"{r['config']}_{r['mode']}_{r['seq']}_{r['run']}.txt"
        if Path(name).name!=name:raise Blocked('Invalid historical trajectory name')
        source=imported/'trajectories'/name;dest=TEAM/'trajectories_tum/part3'/name
        copy_trajectory(source,dest);result.append(historical_row(r,str(dest.relative_to(TEAM))))
    for path,part in [(evaluation/'part4_submission_results.csv','part4_own'),(standard,'part4_standard')]:
        if not path.exists():
            if allow_partial:continue
            raise Blocked(f'Missing results: {path}')
        inputs[str(path.relative_to(ROOT))]=digest(path)
        for r in rows(path):
            extra=dict.fromkeys(EXTRA,'');extra.update(source_part=part,source_run_id=r['run_id'],source_sequence=r['sequence'],source_configuration=r['method'],rpe_protocol='approximately 1 second; scale-corrected',tracking_fraction_basis='OK states / all input frames',trajectory_timestamp_provenance='source image timestamp retained by worker')
            if r['trajectory_file']:
                dest=TEAM/r['trajectory_file']
                if not dest.resolve().is_relative_to(TEAM.resolve()):raise Blocked('Trajectory path escapes repository')
                if part=='part4_own':copy_trajectory(evaluation/'trajectories_tum'/dest.name,dest)
                else:read_tum(dest)
            result.append({**r,'sequence':canonical_sequence(r['sequence']),**extra})
    ids=[r['run_id'] for r in result]
    if len(set(ids))!=len(ids):raise Blocked('Duplicate master run IDs')
    key=fingerprint({'inputs':inputs,'rows':result})[:16]
    target=(work/'master_preview'/key) if allow_partial else TEAM/'Part 4 Results'/(c['experiment_id']+'_master')/key
    target.mkdir(parents=True,exist_ok=True);output=target/'part3_part4_combined_results.csv';table(output,result,FIELDS+EXTRA)
    counts={part:sum(r['source_part']==part for r in result) for part in ['part3','part4_own','part4_standard']}
    manifest={'partial':allow_partial,'rows':len(result),'counts':counts,'input_sha256':inputs,'csv_sha256':digest(output),
              'metric_notes':['First 14 columns follow the submission schema. Historical Part 3 RPE and wall time remain in additional columns; canonical RPE/time fields are blank for those historical rows.','Native Part 4 RPE uses approximately one second; cached inference cost is not measured deployment wall time.','Part 3 timestamp reconstruction is historical and not independently certified.','Own reference is approximate; measured 0.500m check reconstructed as 0.53987m.','This file combines Parts 3 and 4. The separate Part 1 CSV is not silently concatenated.']}
    dump(target/'manifest.json',manifest)
    if not allow_partial and c.get('publish_results',True):
        alias=TEAM/'Results/part3_part4_combined_results.csv';owner=work/'master_export.json'
        if alias.exists() and digest(alias)!=digest(output):
            previous=read(owner) if owner.exists() else {}
            if previous.get('csv_sha256')!=digest(alias):raise Blocked('Combined CSV has independent edits; versioned export preserved')
        shutil.copyfile(output,alias);dump(owner,{'path':str(output.relative_to(ROOT)),**manifest})
        print(f'Master CSV: {alias} ({len(result)} rows; {counts})',flush=True)
    elif not allow_partial:
        print(f'Reproduced master CSV: {output} ({len(result)} rows; {counts}); submitted source CSV preserved',flush=True)
    return output
