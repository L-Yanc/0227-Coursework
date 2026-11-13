"""Precompute and validate actual standard inputs before the user's long batch."""
import copy
from common import ROOT,read,dump,rows,Blocked,artifact,digest

def check_standard(c,work):
    from standard_sequences import SEQUENCES,prepare_standard
    from experiments import depth,slam_run
    from geometry import read_tum,trajectory_metrics
    from analysis import analyse_run
    checks=[]
    for name,cfg in SEQUENCES.items():
        print(f'CHECK STANDARD: {name} — full input/depth validation, then representative short SLAM checks',flush=True)
        sw=work/'standard_reruns'/name;sw.mkdir(parents=True,exist_ok=True)
        local=copy.deepcopy(c);local.update(sequence=name,environment=cfg['scene'],experiment_id=c['experiment_id']+'_'+name)
        local['frames']['target_fps']=cfg['fps'];local['depth'].update(scene=cfg['scene'],png_factor=cfg['factor'])
        prep=prepare_standard(local,sw,name)
        dep=depth(local,sw)
        # Validate every source/depth frame through completed stage hashes; all
        # 105 configurations use these same input images and prediction files.
        if read(dep/'info.json')['frames']!=len(rows(prep/'frames.csv')):raise Blocked('Incomplete standard depth cache')
        truth={int(k):(ROOT/v['path'],v['factor']) for k,v in read(prep/'true_depth.json').items()}
        ref=read_tum(prep/'reference_tum.txt');ev=c['evaluation'];samples=[]
        for policy,temporal in [('every',False),('stride5',False),('keyframes',False),('keyframes',True)]:
            method='selected_temporal' if temporal else 'selected'
            run=slam_run(local,sw,method,policy,1,smoke=True,temporal=temporal)
            if not (run/'run.json').exists() or read(run/'run.json')['status']!='complete':raise Blocked(f'{name} selected-method smoke did not initialise: {run}')
            runtime=read(run/'part3_runtime.json')
            if not runtime['unique_depth_requests'] or not runtime['initialization_events']:raise Blocked(f'{name} did not consume metric learned depth')
            metrics,_,_=trajectory_metrics(read_tum(run/'trajectory.tum'),ref,ev['timestamp_tolerance_s'],ev['interval_s'],ev['pair_tolerance_s'],ev['max_gap_s'])
            summary=analyse_run(run,prep,dep,sw/'preflight_analysis'/run.name,local,truth)
            samples.append({'method':method,'policy':policy,'run':str(run.relative_to(ROOT)),'status':'passed','matched_poses':metrics['matched_poses'],'map_observations':summary['observations'],'reference_depth_available':summary['reference_depth_available'],'temporal':runtime['temporal']})
        frontends=check_frontends(local,sw,prep,dep,ref,truth)
        checks.append({'sequence':name,'frames':len(rows(prep/'frames.csv')),'prepared':str(prep.relative_to(ROOT)),'depth':str(dep.relative_to(ROOT)),'checks':samples})
        dump(work/'overnight_preflight.json',{'sequences':checks,'complete':len(checks)==len(SEQUENCES),'full_105_started':False})
    finish_readiness(c,work)
    print('STANDARD PREFLIGHT PASSED. Full inputs/predictions cached; 105 full attempts remain user-launched.',flush=True)
    return checks


def check_frontends(local,sw,prep,dep,ref,truth):
    """90-frame prefixes exercise mono and pseudo-RGB-D without full reruns."""
    import shutil
    from common import SOURCE,Stage,publish_pointer,table
    from experiments import slam_run
    from geometry import read_tum,trajectory_metrics
    from analysis import analyse_run
    pw=sw/'frontend_preflight';pw.mkdir(exist_ok=True)
    stage=Stage(pw,'prepare',{'prefix_frames':90,'source_prepare':str(prep.relative_to(ROOT))},[prep/'stage.json',prep/'frames.csv',prep/'camera.json',prep/'camera.yaml',SOURCE/'overnight.py'])
    if not stage.cached():
        out=stage.begin();(out/'rgb').mkdir(exist_ok=True);frames=rows(prep/'frames.csv')[:90]
        for name in ['camera.json','camera.yaml']:shutil.copyfile(prep/name,out/name)
        table(out/'frames.csv',frames)
        for r in frames:
            dest=out/r['image']
            if not dest.exists():dest.symlink_to(prep/r['image'])
        stage.finish(['camera.json','camera.yaml','frames.csv',*[r['image'] for r in frames]])
    publish_pointer(pw,'prepare',stage)
    dump(pw/'depth.json',{'path':str(dep.relative_to(ROOT)),'key':read(dep/'stage.json')['key']})
    results=[];ev=local['evaluation']
    for method,policy in [('mono','every'),('pseudo_rgbd','every'),('pseudo_rgbd','stride5')]:
        run=slam_run(local,pw,method,policy,1)
        if not (run/'run.json').exists() or read(run/'run.json')['status']!='complete':raise Blocked(f'{local["sequence"]} {method}/{policy} did not initialise in prefix test')
        metrics,_,_=trajectory_metrics(read_tum(run/'trajectory.tum'),ref,ev['timestamp_tolerance_s'],ev['interval_s'],ev['pair_tolerance_s'],ev['max_gap_s'])
        summary=analyse_run(run,stage.path,dep,pw/'analysis'/run.name,local,truth)
        if truth and not summary['reference_depth_available']:raise Blocked('No valid ground-truth depth samples in standard prefix analysis')
        results.append({'method':method,'policy':policy,'run':str(run.relative_to(ROOT)),'status':'passed','matched_poses':metrics['matched_poses'],'map_observations':summary['observations'],'reference_depth_available':summary['reference_depth_available']})
    dump(sw/'frontend_preflight.json',{'checks':results,'frames':90})
    return results


def signature(c):
    from common import fingerprint,code_hash,SLAM,SOURCE
    names=['pyslam/slam/initializer.py','pyslam/slam/local_mapping.py','pyslam/slam/tracking.py','pyslam/depth_estimation/pred_depth.py','pyslam/depth_estimation/part4_policy.py','pyslam/depth_estimation/depth_sampling.py']
    return fingerprint({'depth':c['depth'],'methods':c['methods'],'evaluation':c['evaluation'],'slam_code':code_hash('slam'),'research_core':{name:digest(SLAM/name) for name in names},'pacing':digest(SOURCE/'pacing.py')})


def finish_readiness(c,work):
    from standard_sequences import SEQUENCES
    report=read(work/'overnight_preflight.json')
    if not report.get('complete') or len(report['sequences'])!=len(SEQUENCES):raise Blocked('Standard input/depth preflight has not completed')
    for item in report['sequences']:
        frontend=read(work/'standard_reruns'/item['sequence']/'frontend_preflight.json')
        if len(frontend['checks'])!=3:raise Blocked('Incomplete frontend checks')
        item['frontend_checks']=frontend['checks']
        for key in ['prepared','depth']:
            meta=read(ROOT/item[key]/'stage.json')
            if meta['status']!='complete' or not all(digest(ROOT/item[key]/name)==value for name,value in meta['outputs'].items()):raise Blocked('Prepared standard cache failed integrity verification')
    report.update(signature=signature(c),representative_checks=21,complete=True,full_105_started=False)
    dump(work/'overnight_preflight.json',report)
    print('OVERNIGHT READY: all full inputs/depth caches and 21 representative checks verified.',flush=True)
    return report


def require_ready(c,work):
    p=work/'overnight_preflight.json'
    if not p.exists():raise Blocked('Run check-standard before the overnight batch')
    report=read(p)
    if not report.get('complete') or report.get('signature')!=signature(c):raise Blocked('Overnight preflight is missing or configuration/code changed; run check-standard first')
