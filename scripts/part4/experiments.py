"""Resumable isolated depth and SLAM workers, with explicit prerequisite reports."""
import json
from pathlib import Path
import sys
import time
import yaml
from common import ROOT, SLAM, SOURCE, Stage, Blocked, artifact, dump, read, rows, env_python, publish_pointer, digest
from geometry import read_tum

def depth(c,work,smoke=False):
    prep=artifact(work,'prepare'); weights=SLAM/('thirdparty/depth_anything_v2/metric_depth/checkpoints/depth_anything_v2_metric_'+('vkitti' if c['depth']['scene']=='outdoor' else 'hypersim')+'_vitb.pth')
    settings={**c['depth'],'max_frames':3 if smoke else None}
    if settings['model']!='DEPTH_ANYTHING_V2' or settings['size']!='base' or settings['scene'] not in ('indoor','outdoor'):
        raise ValueError('This adapter supports metric DAV2 base indoor/outdoor; other networks require a reviewed adapter')
    stage=Stage(work,'depth',settings,[prep/'stage.json',weights])
    pointer='depth_smoke' if smoke else 'depth'
    if stage.cached(): publish_pointer(work,pointer,stage); return stage.path
    out=stage.begin()
    spec={'prepare':str(prep.relative_to(ROOT)),'out':str(out.relative_to(ROOT)),'depth':c['depth'],'max_frames':settings['max_frames']}
    dump(out/'spec.json',spec)
    python,env=env_python('depth')
    stage.run([python,SOURCE/'depth_worker.py','--spec',out/'spec.json'],SLAM,env)
    info=read(out/'info.json'); n=min(len(rows(prep/'frames.csv')),settings['max_frames'] or 10**9)
    if info['frames']!=n: raise ValueError('Incomplete depth predictions')
    stage.finish(['info.json','timing.csv','associations_dav2b.txt']+[f'{d}/{i:06d}.{ext}' for i in range(n) for d,ext in [('raw_m','npy'),('png','png')]])
    publish_pointer(work,pointer,stage); return out

def slam_run(c,work,method,policy,run_number,smoke=False,temporal=False):
    prep=artifact(work,'prepare'); dep=None if method=='mono' else artifact(work,'depth_smoke' if smoke and policy!='stride5' and method=='pseudo_rgbd' else 'depth')
    selected=c['methods'].get('selected') if method in ('selected','selected_temporal') else None
    if method in ('selected','selected_temporal') and selected is None: raise Blocked('Selected Part 3 method adapter deferred; no substitute will be claimed')
    if policy not in ('every','stride5','keyframes') or (policy=='keyframes' and not selected): raise Blocked('Keyframe-only online policy requires a Part 3 insertion hook; unsupported by generic pseudo-RGB-D adapter')
    if policy=='stride5' and '# Part 4 sparse-depth playback:' not in (SLAM/'pyslam/slam/tracking.py').read_text():
        raise Blocked('Apply the Part 4 sparse-depth tracking guard before running stride5')
    settings={'method':method,'policy':policy,'run_number':run_number,'features':c['methods']['features'],
              'backend':c['methods']['backend'],'playback_speed':c['methods']['playback_speed'],'max_frames':90 if smoke and selected else 30 if smoke and (method=='mono' or policy=='stride5') else 3 if smoke else None,'selected':selected,
              'temporal':{**c['methods'].get('temporal_consistency',{}),'enabled':temporal},'png_factor':c['depth']['png_factor'],'environment':c.get('environment','indoor')}
    if settings['features']!='ORB2' or settings['backend']!='cpp': raise ValueError('Use the validated ORB2/C++ adapter')
    inputs=[prep/'stage.json',SOURCE/'slam_worker.py',SLAM/'pyslam/slam/slam.py',SLAM/'pyslam/slam/tracking.py']
    # Hash the actual research hooks, including for baselines whose imported core changed.
    for name in ['pyslam/slam/initializer.py','pyslam/slam/local_mapping.py','pyslam/depth_estimation/pred_depth.py','pyslam/depth_estimation/part4_policy.py','pyslam/depth_estimation/depth_sampling.py']:
        if (SLAM/name).exists(): inputs.append(SLAM/name)
    inputs.extend([SOURCE/'part3_adapter.py',SOURCE/'pacing.py'])
    if dep: inputs.append(dep/'stage.json')
    if selected:
        required=['module','parameters','insertion_location','persistent_constraint','conflict_policy','metric_scale_semantics','random_seed_support']
        if any(k not in selected for k in required): raise Blocked('Selected adapter must declare '+', '.join(required))
        inputs.append(SOURCE/Path(selected['module']).name)
    stage=Stage(work,'slam',settings,inputs)
    if stage.cached(): return stage.path
    out=stage.begin()
    spec={**settings,'prepare':str(prep.relative_to(ROOT)),'out':str(out.relative_to(ROOT)),
          'depth_path':str(dep.relative_to(ROOT)) if dep else None}
    # This config supplies only image geometry and backend settings, never reference poses/depth/scale.
    base=yaml.safe_load((SLAM/'config.yaml').read_text())
    base['DATASET']={'type':'FOLDER_DATASET'}
    base['FOLDER_DATASET']={'type':'folder','sensor_type':'mono' if method=='mono' or selected else 'rgbd','base_path':str(prep/'rgb'),
                            'name':'*.png','fps':c['frames']['target_fps'],'settings':str(prep/'camera.yaml')}
    base['SAVE_TRAJECTORY']={'save_trajectory':False,'format_type':'tum','output_folder':str(out),'basename':'trajectory'}
    base['SYSTEM_STATE']={'load_state':False,'folder_path':'results/part4_unused'}
    base['GLOBAL_PARAMETERS']={'kLogsFolder':str(out/'backend_logs'),'kDoVolumetricIntegration':False}
    (out/'slam_config.yaml').write_text(yaml.safe_dump(base))
    dump(out/'spec.json',spec)
    python,env=env_python(); start=time.perf_counter()
    try:
        stage.run([python,SOURCE/'slam_worker.py','--spec',out/'spec.json'],SLAM,env)
        result=read(out/'run.json')
        if result['status']=='complete': read_tum(out/'trajectory.tum')
        result['subprocess_wall_s']=time.perf_counter()-start; dump(out/'run.json',result)
        stage.finish(['run.json','frame_status.csv','map_observations.csv']+(['part3_runtime.json'] if selected else [])+(['trajectory.tum'] if result['status']=='complete' else []))
    except (RuntimeError,ValueError) as e:
        dump(out/'failure.json',{'status':'failed','reason':str(e),'settings':settings})
        print(f'Failed {method}/{policy}/{run_number}: {e}',flush=True)
        return out
    return out

def run(c,work,smoke=False,reuse_prepared=False,repair_reference_first=False):
    if repair_reference_first:
        if smoke: raise Blocked('Reference repair is a full-workflow option, not a smoke test')
        from readiness import validate_prepared_inputs
        from repair_reference import repair_reference
        validate_prepared_inputs(c,work)
        repair_reference(c,work)
    if not smoke and (work/'reference.json').exists() and (work/'prepare.json').exists():
        from readiness import preflight
        preflight(c,work)  # stop before expensive stages when an existing reference fails
    from media import calibrate,prepare
    # Deliberately don't launch reference/depth/SLAM concurrently on this memory-limited machine.
    if reuse_prepared:
        from readiness import validate_prepared_inputs
        validate_prepared_inputs(c,work)
        print('Reusing hash-validated prepared images and camera; no calibration/extraction rerun.',flush=True)
    else: calibrate(c,work); prepare(c,work)
    stages=[]; blockers=[]
    if smoke:
        stages.append(str(slam_run(c,work,'mono','every',1,True).relative_to(ROOT)))
        depth(c,work,True)
        stages.append(str(slam_run(c,work,'pseudo_rgbd','every',1,True).relative_to(ROOT)))
    else:
        # One real-input smoke before five-run batches.
        smokes=list((work/'slam').glob('*/run.json')) if (work/'slam').exists() else []
        if not any(read(p).get('backend_quiescent') and read(p.parent/'spec.json').get('max_frames') for p in smokes):
            raise Blocked('Run ./run-part4 run --smoke before long batches')
        from reference import reference,scale_markers
        reference(c,work)
        for i in range(1,c['methods']['runs']+1): stages.append(str(slam_run(c,work,'mono','every',i).relative_to(ROOT)))
        depth(c,work)
        for policy in c['methods']['policies']:
            if policy=='stride5':
                check=slam_run(c,work,'pseudo_rgbd',policy,1,True)
                if not (check/'run.json').exists() or read(check/'run.json')['status']!='complete':
                    raise Blocked('Sparse-depth smoke failed; full stride batch was not launched')
            for i in range(1,c['methods']['runs']+1): stages.append(str(slam_run(c,work,'pseudo_rgbd',policy,i).relative_to(ROOT)))
        if c['methods'].get('selected'):
            for policy in c['methods'].get('selected_policies',['every']):
                for i in range(1,c['methods']['runs']+1): stages.append(str(slam_run(c,work,'selected',policy,i).relative_to(ROOT)))
            if c['methods'].get('temporal_consistency',{}).get('enabled'):
                for i in range(1,c['methods']['runs']+1): stages.append(str(slam_run(c,work,'selected_temporal','keyframes',i,temporal=True).relative_to(ROOT)))
        else: blockers.append('Selected Part 3 adapter deferred by user; comparisons remain diagnostic')
        from analysis import analyse_own,analyse_standard
        analyse_own(c,work)
        analyse_standard(c,work)
        try: scale_markers(c,work)
        except Blocked as e: blockers.append(str(e))
        if (work/'marker_scale.json').exists():
            from scoring import evaluate
            evaluate(c,work)
    completion={}
    if not smoke and (work/'evaluation.json').exists():
        from completion import completion_report
        completion=completion_report(c,work,rows(artifact(work,'evaluation')/'part4_submission_results.csv'))
    dump(work/('smoke_status.json' if smoke else 'run_status.json'),{'stages':stages,'blockers':blockers,'full_experiment_completed':False,'note':'See evaluation/package status for scored comparisons and remaining standard-data dependencies',**completion})
    for b in blockers: print('BLOCKED: '+b)
