"""Local standard-sequence reruns, with native timestamps and source image IDs.

This is an explicit long command. Historical Part 3 RPE (1 metre) and wall-time
figures remain separate from the 1 second RPE and synchronous timing computed here.
"""
from pathlib import Path
import copy
import os
import cv2
import numpy as np
import yaml
from common import ROOT,SLAM,TEAM,Stage,Blocked,atomic,artifact,dump,read,rows,table,publish_pointer
from geometry import write_tum,read_tum,trajectory_metrics

SEQUENCES={
 'tum_fr3':{'path':'datasets/rgbd_dataset_freiburg3_long_office_household','settings':'TUM3.yaml','fps':30.,'factor':5000.,'scene':'indoor'},
 'replica_room0':{'path':'datasets/Replica/room0','settings':'REPLICA.yaml','fps':25.,'factor':6553.5,'scene':'indoor'},
 'kitti06':{'path':'COMP0227_26-27/pyslam/data/videos/kitti06','settings':'KITTI04-12.yaml','fps':10.,'factor':256.,'scene':'outdoor'},
}

def source_records(name):
    cfg=SEQUENCES[name]; base=Path(os.environ.get({'tum_fr3':'CW1_TUM_FR3','replica_room0':'CW1_REPLICA_ROOM0','kitti06':'CW1_KITTI06'}[name],ROOT/cfg['path'])); records=[]
    if name=='tum_fr3':
        for line in (base/'associations.txt').read_text().splitlines():
            if not line.strip() or line.startswith('#'): continue
            t,rgb,td,dep=line.split()[:4]
            records.append({'timestamp':float(t),'rgb':base/rgb,'true_depth':base/dep,'depth_timestamp':float(td)})
        gt=np.loadtxt(base/'groundtruth.txt')[:,:8]
    elif name=='replica_room0':
        files=sorted((base/'results').glob('frame*.jpg')); poses=np.loadtxt(base/'traj.txt').reshape(-1,4,4)
        if len(files)!=len(poses): raise Blocked('Replica RGB/pose count mismatch')
        from scipy.spatial.transform import Rotation
        gt=np.c_[np.arange(len(files))/cfg['fps'],poses[:,:3,3],Rotation.from_matrix(poses[:,:3,:3]).as_quat()]
        for i,p in enumerate(files):
            if p.stem!=f'frame{i:06d}': raise Blocked('Replica frame numbering has a gap')
            records.append({'timestamp':i/cfg['fps'],'rgb':p,'true_depth':p.with_name(f'depth{i:06d}.png')})
    else:
        ts=np.loadtxt(base/'times.txt'); poses=np.loadtxt(base/'06.txt').reshape(-1,3,4)
        if len(ts)!=len(poses): raise Blocked('KITTI time/pose count mismatch')
        from scipy.spatial.transform import Rotation
        gt=np.c_[ts,poses[:,:3,3],Rotation.from_matrix(poses[:,:3,:3]).as_quat()]
        records=[{'timestamp':float(t),'video_index':i} for i,t in enumerate(ts)]
    ts=np.array([r['timestamp'] for r in records])
    if not len(ts) or np.any(np.diff(ts)<=0): raise Blocked('Non-monotone source timestamps')
    return records,gt

def prepare_standard(c,work,name,smoke=False):
    cfg=dict(SEQUENCES[name]); cfg['path']=str(Path(os.environ.get({'tum_fr3':'CW1_TUM_FR3','replica_room0':'CW1_REPLICA_ROOM0','kitti06':'CW1_KITTI06'}[name],ROOT/cfg['path'])))
    records,gt=source_records(name)
    if smoke: records=records[:3]
    settings_path=SLAM/'settings'/cfg['settings']; camera=yaml.safe_load(settings_path.read_text())
    inputs=[settings_path,Path(__file__)]
    for filename in ['associations.txt','groundtruth.txt','traj.txt','times.txt','06.txt','video_color.mp4']:
        p=ROOT/cfg['path']/filename
        if p.exists(): inputs.append(p)
    # Hash the actual input media; changed source images invalidate the prepared stage.
    inputs.extend(r[k] for r in records for k in ['rgb','true_depth'] if k in r)
    stage=Stage(work,'prepare',{'dataset':name,'source':cfg,'smoke':smoke},inputs)
    if stage.cached(): publish_pointer(work,'prepare',stage);return stage.path
    out=stage.begin();(out/'rgb').mkdir(exist_ok=True);(out/'true_depth').mkdir(exist_ok=True)
    k=np.array([[camera['Camera.fx'],0,camera['Camera.cx']],[0,camera['Camera.fy'],camera['Camera.cy']],[0,0,1.]])
    width,height=camera['Camera.width'],camera['Camera.height']
    dist=[camera.get('Camera.'+x,0.) for x in ['k1','k2','p1','p2','k3']]
    if np.any(dist): raise Blocked('Standard inputs require a reviewed common RGB/depth undistortion map')
    cap=cv2.VideoCapture(str(ROOT/cfg['path']/'video_color.mp4')) if name=='kitti06' else None
    frames=[];truth={};expected=['frames.csv','camera.json','camera.yaml','reference_tum.txt','true_depth.json']
    try:
        for i,r in enumerate(records):
            if cap is not None:
                ok,image=cap.read()
                if not ok: raise Blocked(f'KITTI video decode ended at {i}')
            else: image=cv2.imread(str(r['rgb']))
            if image is None or image.shape[:2]!=(height,width): raise Blocked(f'{name} source geometry mismatch at {i}; no silent resize')
            path=f'rgb/{i:06d}.png'
            if not cv2.imwrite(str(out/path),image): raise RuntimeError('Image write failed')
            expected.append(path)
            frames.append({'frame_id':i,'source_frame_index':i,'timestamp':r['timestamp'],'image':path})
            if 'true_depth' in r:
                depth=cv2.imread(str(r['true_depth']),cv2.IMREAD_UNCHANGED)
                if depth is None or depth.shape!=image.shape[:2]: raise Blocked('Reference depth geometry mismatch')
                rel=f'true_depth/{i:06d}.png'
                if not cv2.imwrite(str(out/rel),depth): raise RuntimeError('Reference depth write failed')
                truth[str(i)]={'path':str((out/rel).relative_to(ROOT)),'factor':cfg['factor']};expected.append(rel)
        if cap is not None and not smoke and cap.read()[0]: raise Blocked('KITTI video has more images than timestamps')
    finally:
        if cap is not None: cap.release()
    camera.update({'Camera.RGB':0,'DepthMapFactor':cfg['factor'],'Viewer.on':0,'FeatureTrackerConfig.nFeatures':2000})
    (out/'camera.yaml').write_text(yaml.safe_dump(camera))
    dump(out/'camera.json',{'K':k.tolist(),'width':width,'height':height,'distortion':dist,'source':str(settings_path.relative_to(ROOT))})
    table(out/'frames.csv',frames);dump(out/'true_depth.json',truth)
    from scipy.spatial.transform import Rotation
    poses=np.repeat(np.eye(4)[None],len(gt),axis=0);poses[:,:3,:3]=Rotation.from_quat(gt[:,4:8]).as_matrix();poses[:,:3,3]=gt[:,1:4]
    write_tum(out/'reference_tum.txt',gt[:,0],poses)
    stage.finish(expected);publish_pointer(work,'prepare',stage);return out

def run_standard(c,work,smoke=False):
    from experiments import depth,slam_run
    from analysis import analyse_run,failure_trace
    from scoring import FIELDS,aggregate
    results=[];statuses=[]
    for name,cfg in SEQUENCES.items():
        sw=work/'standard_reruns'/name; sw.mkdir(parents=True,exist_ok=True)
        local=copy.deepcopy(c); local['sequence']=name;local['environment']=cfg['scene'];local['frames']['target_fps']=cfg['fps']
        local['depth'].update(scene=cfg['scene'],png_factor=cfg['factor']); local['experiment_id']=c['experiment_id']+'_'+name
        prep=prepare_standard(local,sw,name,smoke)
        dep=depth(local,sw,smoke=smoke)
        if smoke:
            statuses.append({'sequence':name,'prepared_frames':len(rows(prep/'frames.csv')),'depth_frames':read(dep/'info.json')['frames'],'status':'input/depth smoke only; no SLAM accuracy claim'})
            continue
        truth={int(k):(ROOT/v['path'],v['factor']) for k,v in read(prep/'true_depth.json').items()}
        ref=read_tum(prep/'reference_tum.txt');n=len(rows(prep/'frames.csv'));ev=c['evaluation']
        configurations=[('mono','every',False),('pseudo_rgbd','every',False),('pseudo_rgbd','stride5',False),('selected','every',False),('selected','keyframes',False),('selected','stride5',False),('selected_temporal','keyframes',True)]
        evalout=sw/'evaluation_tables';evalout.mkdir(exist_ok=True);(evalout/'matched').mkdir(exist_ok=True)
        seqrows=[];metadata={}
        for method,policy,temporal in configurations:
            for repetition in range(1,c['methods']['runs']+1):
                run=slam_run(local,sw,method,policy,repetition,temporal=temporal)
                rid=f'{name}_{method}_{policy}_r{repetition}_{run.name}'
                row=dict.fromkeys(FIELDS,'');row.update(run_id=rid,sequence=name,method=method+('' if policy=='every' else '_'+policy),run_number=repetition,settings=(run/'spec.json').read_text().strip())
                status={'raw_run':str(run.relative_to(ROOT)),'status':'failed'}
                if (run/'run.json').exists():
                    info=read(run/'run.json');status.update(info)
                    states=rows(run/'frame_status.csv');row.update(fraction_tracked=sum(r['state']=='OK' for r in states)/n,fraction_lost=sum(r['state']=='LOST' for r in states)/n,time_per_frame_ms=info['mean_tracking_ms'])
                    if info['status']=='complete':
                        try:
                            metrics,matched,rpe=trajectory_metrics(read_tum(run/'trajectory.tum'),ref,ev['timestamp_tolerance_s'],ev['interval_s'],ev['pair_tolerance_s'],ev['max_gap_s'])
                        except ValueError as e:
                            status['evaluation_unavailable_reason']=str(e)
                            metrics={key:None for key in FIELDS[5:9]};matched=[];rpe=[]
                        status.update(metrics)
                        row.update({key:metrics[key] if metrics[key] is not None else '' for key in FIELDS[5:9]})
                        traj=TEAM/'trajectories_tum/part4'/f'{rid}.tum';traj.parent.mkdir(parents=True,exist_ok=True)
                        if traj.exists() and traj.read_bytes()!=(run/'trajectory.tum').read_bytes(): raise Blocked('Existing standard trajectory differs')
                        if not traj.exists(): traj.write_bytes((run/'trajectory.tum').read_bytes())
                        row['trajectory_file']=str(traj.relative_to(TEAM));table(evalout/'matched'/f'{rid}.csv',matched)
                        try:
                            summary=analyse_run(run,prep,dep,evalout/'analysis'/run.name,local,truth)
                            if truth:
                                errors=[float(r['map_error_m']) for r in rows(evalout/'analysis'/run.name/'observations.csv') if r['map_error_m']!='']
                                row['map_depth_mae_m']=float(np.mean(errors)) if errors else ''
                        except Exception as e:
                            import traceback
                            status['analysis_blocker']=f'{type(e).__name__}: {e}'
                            dump(evalout/(rid+'_analysis_error.json'),{'error':status['analysis_blocker'],'traceback':traceback.format_exc()})
                elif (run/'failure.json').exists():status.update(read(run/'failure.json'))
                seqrows.append(row);metadata[rid]=status
                # Durable checkpoints after every attempt, before the next worker.
                table(evalout/'results.csv',seqrows,FIELDS)
                dump(evalout/'metrics_per_run.json',metadata)
                table(work/'standard_reruns/part4_standard_results.csv',results+seqrows,FIELDS)
        table(evalout/'results.csv',seqrows,FIELDS);dump(evalout/'metrics_per_run.json',metadata);table(evalout/'aggregates.csv',aggregate(seqrows))
        failure_trace(seqrows,metadata,evalout,prep,sw)
        results.extend(seqrows);statuses.append({'sequence':name,'rows':len(seqrows),'path':str(evalout.relative_to(ROOT))})
    out=work/'standard_reruns';out.mkdir(exist_ok=True)
    dump(out/('smoke_status.json' if smoke else 'status.json'),{'sequences':statuses,'historical_part3_metrics_merged':False,'full_standard_part4_completed':not smoke and len(results)==len(SEQUENCES)*7*c['methods']['runs'],'attempts':len(results),'successful_scored_runs':sum(r['ate_scaled_m']!='' for r in results)})
    if not smoke:
        table(out/'part4_standard_results.csv',results,FIELDS);table(out/'aggregates.csv',aggregate(results))
        target=ROOT/'part4/exports'/(c['experiment_id']+'_standard');target.mkdir(parents=True,exist_ok=True)
        import shutil
        shutil.copytree(out,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns('prepare','depth','slam'))
        from master_results import export_master
        export_master(c,work)
    return out
