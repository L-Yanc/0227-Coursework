"""Immutable raw trajectories -> consistent metrics, per-run CSV, portable package."""
import csv
import io
import json
from pathlib import Path
import shutil
import zipfile
import numpy as np
from common import ROOT,CODE, TEAM, SLAM, SOURCE, Stage, Blocked, artifact, atomic, digest, dump, read, rows, table, publish_pointer, command, fingerprint
from geometry import read_tum, trajectory_metrics

FIELDS='run_id sequence method settings run_number ate_unscaled_m ate_scaled_m fitted_scale rpe_rmse_m fraction_tracked fraction_lost time_per_frame_ms map_depth_mae_m trajectory_file'.split()

def configuration_key(row):
    value=row.get('settings','')
    if value.startswith('backend='): return value
    try:
        s=json.loads(value)
        keys=['method','policy','features','backend','playback_speed','selected','temporal','environment','png_factor','depth_config','depth_weights_sha256']
        return json.dumps({k:s[k] for k in keys if k in s},sort_keys=True,separators=(',',':'))
    except (ValueError,TypeError): return value

def aggregate(records):
    output=[]
    config_key=configuration_key
    groups=sorted(set((r.get('sequence','own'),r['method'],config_key(r)) for r in records))
    for sequence,method,configuration in groups:
        group=[r for r in records if r['method']==method and r.get('sequence','own')==sequence and config_key(r)==configuration]
        for metric in FIELDS[5:13]:
            values=np.array([float(r[metric]) for r in group if r.get(metric) not in ('',None)])
            output.append({'sequence':sequence,'method':method,'configuration':configuration,'metric':metric,'n':len(values),'mean':float(values.mean()) if len(values) else None,
                           'sd':float(values.std(ddof=1)) if len(values)>1 else None,'median':float(np.median(values)) if len(values) else None})
    return output

def evaluate(c,work):
    scaled=artifact(work,'marker_scale'); refpath=scaled/'reference_tum.txt'; ref=read_tum(refpath)
    prep=artifact(work,'prepare'); paths=[]
    for p in sorted((work/'slam').glob('*/spec.json')):
        s=read(p)
        oldprep=ROOT/s['prepare']
        same_images=oldprep.exists() and digest(oldprep/'frames.csv')==digest(prep/'frames.csv') and digest(oldprep/'camera.json')==digest(prep/'camera.json')
        if s.get('max_frames') is None and same_images: paths.append(p.parent)
    if not paths: raise Blocked('No full-sequence runs for current prepared input')
    inputs=[refpath,*[p/'spec.json' for p in paths],*[p/('run.json' if (p/'run.json').exists() else 'failure.json') for p in paths]]
    inputs += [p/'trajectory.tum' for p in paths if (p/'trajectory.tum').exists()]
    stage=Stage(work,'evaluation',c['evaluation'],inputs)
    if stage.cached(): publish_pointer(work,'evaluation',stage); return stage.path
    out=stage.begin(); (out/'matched').mkdir(exist_ok=True); (out/'trajectories_tum').mkdir(exist_ok=True)
    results=[]; metadata={}; allframes=len(rows(prep/'frames.csv')); common_times=None
    reference_quality=read(artifact(work,'reference')/'reference_quality.json')
    depth_timing={}
    try: depth_timing={int(r['frame_id']):float(r['inference_ms']) for r in rows(artifact(work,'depth')/'timing.csv')}
    except Blocked: pass
    for p in paths:
        s=read(p/'spec.json'); runid=f'{c["experiment_id"]}_{s["method"]}_{s["policy"]}_r{s["run_number"]}_{p.name}'
        method=s['method']+('' if s['policy']=='every' else '_'+s['policy'])
        reported_settings=dict(s)
        if s.get('depth_path') and (ROOT/s['depth_path']/'info.json').exists():
            depth_info=read(ROOT/s['depth_path']/'info.json')
            reported_settings['depth_config']=depth_info['model']; reported_settings['depth_weights_sha256']=depth_info['weights_sha256']
        row=dict.fromkeys(FIELDS,''); row.update(run_id=runid,sequence='own',method=method,settings=json.dumps(reported_settings,sort_keys=True,separators=(',',':')),run_number=s['run_number'])
        meta={'reference_type':'approximate COLMAP, metric from wall scale pair','raw_run':str(p.relative_to(ROOT)),'status':'failed',
              'reference_quality_gate_passed':reference_quality['passes_registered_fraction'],
              'reference_registered_fraction':reference_quality['registered_fraction'],'reference_max_gap_s':reference_quality['max_gap_s'],
              'exploratory':c['methods']['runs']<5}
        if (p/'run.json').exists():
            rr=read(p/'run.json'); meta.update(rr)
            states=rows(p/'frame_status.csv'); counts={state:sum(r['state']==state for r in states) for state in {r['state'] for r in states}}
            row['fraction_tracked']=counts.get('OK',0)/allframes
            row['fraction_lost']=counts.get('LOST',0)/allframes
            row['time_per_frame_ms']=rr['mean_tracking_ms']
            meta['frame_state_counts']=counts; meta['input_frame_denominator']=allframes
            meta['missing_processed_frames']=allframes-len(states)
            meta['full_pipeline_cached_ms_per_frame']=rr['subprocess_wall_s']*1000/allframes
            requested=set(rr.get('part3_runtime',{}).get('requested_timestamps',[])) if rr.get('part3_runtime') else None
            cost=sum(depth_timing.get(int(r['frame_id']),0) for r in states if (round(float(r['timestamp']),6) in requested if requested is not None else r['depth_used']=='True'))/allframes
            meta['estimated_inference_ms_per_input_frame']=cost
            meta['estimated_deployment_tracking_plus_inference_ms']=row['time_per_frame_ms']+cost
            meta['compute_note']='Cached SLAM runs do not measure saved inference wall time; deployment inference estimate sums measured per-frame network costs. Playback wait/backend shutdown included only in full subprocess cost.'
            if rr['status']=='complete':
                est=read_tum(p/'trajectory.tum')
                shutil.copyfile(p/'trajectory.tum',out/'trajectories_tum'/f'{runid}.tum')
                row['trajectory_file']=f'trajectories_tum/part4/{runid}.tum'
                ev=c['evaluation']
                try:
                    m,matched,rpe=trajectory_metrics(est,ref,ev['timestamp_tolerance_s'],ev['interval_s'],ev['pair_tolerance_s'],ev['max_gap_s'])
                    row.update({k:('' if m[k] is None else m[k]) for k in ['ate_unscaled_m','ate_scaled_m','fitted_scale','rpe_rmse_m']})
                    meta.update(m); table(out/'matched'/f'{runid}.csv',matched); table(out/'matched'/f'{runid}_rpe.csv',rpe,['i','j','interval_s','scaled_error_m','rigid_error_m'])
                    times={round(float(r['reference_timestamp']),7) for r in matched}
                    common_times=times if common_times is None else common_times&times
                except ValueError as e:
                    meta['evaluation_unavailable_reason']=str(e)
        else: meta.update(read(p/'failure.json'))
        metadata[runid]=meta; results.append(row)
    # Distinct real attempts retain distinct run IDs; a cache hit never adds a row.
    table(out/'part4_submission_results.csv',results,FIELDS); dump(out/'metrics_per_run.json',metadata)
    common_metrics=[]
    if common_times and len(common_times)>=3:
        common_ref=ref[[round(float(t),7) in common_times for t in ref[:,0]]]
        for row in results:
            path=out/'trajectories_tum'/f'{row["run_id"]}.tum'
            if not path.exists(): continue
            try:
                ev=c['evaluation']; m,_,_=trajectory_metrics(read_tum(path),common_ref,ev['timestamp_tolerance_s'],ev['interval_s'],ev['pair_tolerance_s'],ev['max_gap_s'])
                common_metrics.append({'run_id':row['run_id'],'common_reference_poses':len(common_ref),'fraction_of_reference':len(common_ref)/len(ref),**m})
            except ValueError: pass
    table(out/'common_subset_metrics.csv',common_metrics,['run_id','common_reference_poses','fraction_of_reference',*list(common_metrics[0].keys())[3:]] if common_metrics else ['run_id','common_reference_poses','fraction_of_reference'])
    table(out/'aggregates.csv',aggregate(results))
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(8,4))
    for i,method in enumerate(sorted(set(r['method'] for r in results))):
        vals=[float(r['ate_scaled_m']) for r in results if r['method']==method and r['ate_scaled_m']!='']
        ax.scatter([i]*len(vals),vals,label=method)
    ax.set_xticks(range(len(set(r['method'] for r in results))),sorted(set(r['method'] for r in results)),rotation=15)
    ax.set_ylabel('Sim(3) ATE RMSE (m), approximate reference'); fig.tight_layout(); fig.savefig(out/'ate_runs.png'); plt.close(fig)
    from analysis import analyse_run,failure_trace
    for p in paths:
        if (p/'run.json').exists() and read(p/'run.json')['status']=='complete':
            try: analyse_run(p,prep,artifact(work,'depth'),out/'analysis'/p.name,c)
            except Blocked as e: dump(out/f'analysis_{p.name}_blocked.json',{'reason':str(e)})
    failure_trace(results,metadata,out,prep,work)
    stage.finish(['part4_submission_results.csv','metrics_per_run.json','aggregates.csv','common_subset_metrics.csv','ate_runs.png','failure_trace.json'])
    publish_pointer(work,'evaluation',stage); return out

def validate_csv(path,base,allow_failed=False):
    data=rows(path)
    with Path(path).open(newline='') as f:
        if next(csv.reader(f))!=FIELDS: raise ValueError('CSV schema/order differs from Part 1')
    ids=[r['run_id'] for r in data]
    if len(ids)!=len(set(ids)): raise ValueError('Duplicate run IDs')
    for r in data:
        if not r['trajectory_file']:
            if allow_failed and all(r[k]=='' for k in ['ate_scaled_m','ate_unscaled_m','fitted_scale','rpe_rmse_m']): continue
            raise ValueError(f'Missing trajectory for {r["run_id"]}')
        p=Path(base)/r['trajectory_file']
        if not p.resolve().is_relative_to(Path(base).resolve()): raise ValueError('Trajectory escapes repository root')
        read_tum(p)
    return data

def merge(paths,out):
    data=[]
    for p in paths: data.extend(validate_csv(p,p.parent.parent,True))
    if len({r['run_id'] for r in data})!=len(data): raise ValueError('Duplicate run IDs across CSV inputs')
    if Path(out).exists(): raise ValueError('Merge output already exists; choose a new path')
    table(out,data,FIELDS)

def verified_previous_ownership(source,manifests):
    verified={}
    for manifest in manifests:
        for rel,expected in read(manifest).items():
            dest=source/rel
            if dest.is_file() and dest.resolve().is_relative_to(source.resolve()) and digest(dest)==expected:
                verified[rel]=expected
    return verified

def package_code(c,work):
    import sys
    command([sys.executable,CODE/'scripts/submission/package_release.py','--out',TEAM,'--code-only'])
    print(f'Combined code archive: {TEAM/"code.zip"}',flush=True)
    return TEAM


def package_unscored(c,work):
    """A reviewable snapshot of real runs while metric markers remain pending.

    It is separate from the final submission CSV and never fills unavailable errors.
    """
    code=package_code(c,work); prep=artifact(work,'prepare'); analysis=artifact(work,'own_analysis')
    runs=[]
    for p in sorted((work/'slam').glob('*/spec.json')):
        s=read(p); old=ROOT/s['prepare']
        if s.get('max_frames') is None and digest(old/'frames.csv')==digest(prep/'frames.csv') and ((p.parent/'run.json').exists() or (p.parent/'failure.json').exists()): runs.append(p.parent)
    if not runs: raise Blocked('No actual full-sequence run attempts to package')
    inputs=[analysis/'stage.json',prep/'frames.csv',*[p/'spec.json' for p in runs],*[p/('run.json' if (p/'run.json').exists() else 'failure.json') for p in runs]]
    if (work/'validation_status.json').exists(): inputs.append(work/'validation_status.json')
    stage=Stage(work,'unscored_package',{'experiment_id':c['experiment_id'],'status':'metric scale/ATE/RPE pending marker review'},inputs)
    target=ROOT/'part4/exports'/f'{c["experiment_id"]}_pending'/stage.key[:16]
    if target.exists():
        validate_csv(target/'part4_pending_results.csv',TEAM,True)
        print(f'Unscored snapshot already exists: {target}'); return target
    out=stage.begin(); results=[]; metadata={}; n=len(rows(prep/'frames.csv'))
    trajectories=TEAM/'trajectories_tum/part4'; trajectories.mkdir(parents=True,exist_ok=True)
    for p in runs:
        s=read(p/'spec.json'); rid=f'{c["experiment_id"]}_{s["method"]}_{s["policy"]}_r{s["run_number"]}_{p.name}'
        settings=dict(s)
        if s.get('depth_path'):
            info=read(ROOT/s['depth_path']/'info.json'); settings.update(depth_config=info['model'],depth_weights_sha256=info['weights_sha256'])
        row=dict.fromkeys(FIELDS,''); row.update(run_id=rid,sequence='own',method=s['method']+('' if s['policy']=='every' else '_'+s['policy']),settings=json.dumps(settings,sort_keys=True),run_number=s['run_number'])
        unavailable='Metric scoring omitted in this unscored snapshot; run evaluate' if (work/'marker_scale.json').exists() else 'Wall-marker metric scale has not been selected/reviewed'
        m={'raw_run':str(p.relative_to(ROOT)),'metric_errors_unavailable_reason':unavailable,
           'map_depth_mae_unavailable_reason':'No true phone depth exists','status':'failed'}
        if (p/'run.json').exists():
            r=read(p/'run.json'); m.update(r)
            states=rows(p/'frame_status.csv')
            row.update(fraction_tracked=sum(v['state']=='OK' for v in states)/n,fraction_lost=sum(v['state']=='LOST' for v in states)/n,time_per_frame_ms=r['mean_tracking_ms'])
            m['frame_state_counts']={state:sum(v['state']==state for v in states) for state in {v['state'] for v in states}}
            if r['status']=='complete':
                read_tum(p/'trajectory.tum'); dest=trajectories/f'{rid}.tum'
                if dest.exists() and digest(dest)!=digest(p/'trajectory.tum'): raise Blocked('Existing trajectory differs; refusing overwrite')
                if not dest.exists(): shutil.copyfile(p/'trajectory.tum',dest)
                row['trajectory_file']=str(dest.relative_to(TEAM))
        else: m.update(read(p/'failure.json'))
        results.append(row); metadata[rid]=m
    table(out/'part4_pending_results.csv',results,FIELDS); dump(out/'metrics_pending.json',metadata)
    table(out/'tracking_compute_aggregates.csv',aggregate(results))
    successful=sum(m['status']=='complete' for m in metadata.values()); failed=sum(m['status']=='failed' for m in metadata.values())
    dump(out/'status.json',{'status':'unscored; not final submission results','successful_full_runs':successful,
                           'failed_attempts':failed,'full_experiment_completed':False,
                           'blockers':['Metric scoring pending','Selected Part 3 comparison deferred' if c['methods'].get('selected') is None else 'Selected method metric comparison pending','Standard-sequence dense maps and validated geometry'],
                           'code_bundle':str(code.relative_to(TEAM))})
    stage.finish(['part4_pending_results.csv','metrics_pending.json','tracking_compute_aggregates.csv','status.json'])
    pending=target.with_name(target.name+'.partial'); pending.mkdir(parents=True,exist_ok=True)
    for name in ['part4_pending_results.csv','metrics_pending.json','tracking_compute_aggregates.csv','status.json','stage.json']:
        shutil.copyfile(out/name,pending/name)
    dump(pending/'config.json',c)
    for name in ['hardware.json','tracking_per_run.csv','tracking_aggregates.csv','validation_status.json']:
        if (work/name).exists(): shutil.copyfile(work/name,pending/name)
    shutil.copyfile(artifact(work,'reference')/'reference_quality.json',pending/'reference_quality.json')
    shutil.copyfile(artifact(work,'calibration')/'calibration.json',pending/'calibration_summary.json')
    for p in analysis.iterdir():
        if p.is_dir(): shutil.copytree(p,pending/'analysis_tables'/p.name,ignore=shutil.ignore_patterns('observations.csv'))
    import gzip
    for p in runs:
        record=pending/'run_records'/p.name; record.mkdir(parents=True,exist_ok=True)
        for name in ['frame_status.csv','run.json','failure.json','stage.json','spec.json']:
            if (p/name).exists(): shutil.copyfile(p/name,record/name)
        for log in p.glob('command_*'):
            if log.suffix=='.json': shutil.copyfile(log,record/log.name)
            elif log.suffix=='.log':
                with log.open('rb') as src,gzip.open(record/(log.name+'.gz'),'wb') as dst: shutil.copyfileobj(src,dst)
    shutil.copyfile(analysis/'index.json',pending/'analysis_index.json')
    atomic(pending/'summary.md',f'# Unscored Part 4 snapshot\n\nThese are actual phone-sequence runs and depth/map diagnostics. Metric errors are unavailable in this snapshot. Missing error fields are blank, never zero. {successful} successful full runs and {failed} failed attempts are preserved. No claim of a completed Part 4 experiment or a completed Part 3 comparison is made.\n\nOpen part4_pending_results.csv and tracking_compute_aggregates.csv; trajectories link relative to the team repository root. Run records include per-frame statuses: LOST counts only the actual LOST state, and initialization/relocalization remain separate. Analysis tables exclude the large per-observation raw table, which remains in the local work directory with its provenance.\n')
    validate_csv(pending/'part4_pending_results.csv',TEAM,True)
    dump(pending/'manifest.json',{'status':'unscored','raw_analysis_path':str(analysis.relative_to(ROOT)),
                                'files':{str(p.relative_to(pending)):digest(p) for p in pending.rglob('*') if p.is_file()},
                                'original_video_sha256':digest(ROOT/c['video']),'raw_media_included':False})
    pending.rename(target); print(f'Unscored snapshot: {target}'); return target

def package(c,work):
    """Final code package; saved experimental exports stay in their work root."""
    return package_code(c,work)
