"""Pointwise, parallax and temporal diagnostics; no phone true-depth claims."""
import csv
import json
from pathlib import Path
import zipfile
import cv2
import numpy as np
from collections import defaultdict
from common import ROOT,CODE, TEAM, Stage, Blocked, atomic, artifact, dump, read, rows, table, publish_pointer

def bilinear(depth,u,v):
    h,w=depth.shape
    if not (0<=u<w-1 and 0<=v<h-1): return None
    x,y=int(u),int(v); values=depth[y:y+2,x:x+2]
    if not np.isfinite(values).all() or np.any(values<=0): return None
    a,b=u-x,v-y
    return float(values[0,0]*(1-a)*(1-b)+values[0,1]*a*(1-b)+values[1,0]*(1-a)*b+values[1,1]*a*b)

def robust(values):
    a=np.asarray(values,float)
    if not len(a): return {'n':0,'median':None,'mad':None}
    med=float(np.median(a))
    return {'n':len(a),'median':med,'mad':float(np.median(abs(a-med)))}

def bin_label(x,bounds):
    if x is None or not np.isfinite(x): return 'unavailable'
    for lo,hi in zip(bounds[:-1],bounds[1:]):
        if lo<=x<hi: return f'{lo:g}-{hi:g}'
    return 'unavailable'

def analyse_run(run,prep,depth,out,c,true_depth=None,predicted_factor=None,deployable_scale=None):
    out.mkdir(parents=True,exist_ok=True)
    obs=rows(run/'map_observations.csv')
    if not obs: raise Blocked('No final map observations')
    missing=set(['Twc','world_x','world_y','world_z','timestamp'])-set(obs[0])
    if missing: raise Blocked('Observation export lacks '+', '.join(sorted(missing))+'; re-export actual poses/world points for parallax and world-frame consistency')
    frames=rows(prep/'frames.csv'); byid={int(r['frame_id']):r for r in frames}; cam=read(prep/'camera.json'); k=np.array(cam['K'])
    grouped=defaultdict(list)
    for r in obs: grouped[int(r['frame_id'])].append(r)
    allpoints=[]; frame_scales={}
    for fid,group in sorted(grouped.items()):
        if fid not in byid: raise ValueError('Map source frame not present in input frame table')
        if predicted_factor:
            image=cv2.imread(str(depth/f'{fid:06d}.png'),cv2.IMREAD_UNCHANGED)
            if image is None: raise Blocked(f'Missing depth PNG for frame {fid}')
            pred=image.astype(float)/predicted_factor
        else:
            path=depth/'raw_m'/f'{fid:06d}.npy'
            if not path.exists(): raise Blocked(f'Missing learned depth {path}')
            pred=np.load(path)
        if pred.shape!=(cam['height'],cam['width']): raise ValueError('Depth geometry mismatch; no silent resizing')
        truth=None
        if true_depth and fid in true_depth:
            path,factor=true_depth[fid]; truth=cv2.imread(str(path),cv2.IMREAD_UNCHANGED)
            if truth is None: raise Blocked(f'Missing true depth {path}')
            truth=truth.astype(float)/factor
            if truth.shape!=pred.shape: raise ValueError('Reference/predicted image shape mismatch')
        ratios=[]; fr=[]
        for r in group:
            u,v,z=float(r['u']),float(r['v']),float(r['map_depth']); d=bilinear(pred,u,v)
            if d is None or z<=0: continue
            p=np.array([float(r['world_x']),float(r['world_y']),float(r['world_z'])]); twc=np.array(json.loads(r['Twc']))
            # Recheck the exporter convention against the actual map point and pose.
            pc=twc[:3,:3].T@(p-twc[:3,3])
            if not np.isclose(pc[2],z,rtol=1e-4,atol=1e-5): raise ValueError('Camera optical-Z convention mismatch')
            gt=bilinear(truth,u,v) if truth is not None else None
            if gt is not None and not .1<=gt<=5: gt=None
            rec={'frame_id':fid,'timestamp':float(r['timestamp']),'point_id':int(r['point_id']),'u':u,'v':v,
                 'map_z_units':z,'learned_z_m':d,'reference_z_m':gt,'Twc':twc,'world':p,
                 'normalised_radius':float(np.sqrt(((u-k[0,2])/(cam['width']/2))**2+((v-k[1,2])/(cam['height']/2))**2))}
            fr.append(rec); ratios.append(d/z)
        frame_scales[fid]=float(np.median(ratios)) if ratios else None; allpoints+=fr
    if not allpoints: raise Blocked('No valid learned/map-depth correspondences')
    frame_times=[float(r['timestamp']) for r in frames]
    split=min(frame_times)+c['methods']['temporal_policy_development_fraction']*(max(frame_times)-min(frame_times))
    # Infer scale using only network/map correspondences. This is an offline diagnostic,
    # not evidence that the mono method internally recovered metric scale.
    spec=read(run/'spec.json') if (run/'spec.json').exists() else {'method':'unknown'}
    selected_without_metric_init=bool(spec.get('selected')) and (not (run/'part3_runtime.json').exists() or not read(run/'part3_runtime.json').get('initialization_events'))
    arbitrary_scale=spec['method']=='mono' or selected_without_metric_init
    if deployable_scale is None:
        development_scales=[v for fid,v in frame_scales.items() if v and float(byid[fid]['timestamp'])<=split]
        if arbitrary_scale and not development_scales: raise Blocked('No valid network/map scales on development interval')
        scale=1. if not arbitrary_scale else float(np.median(development_scales))
    else: scale=float(deployable_scale)
    points=defaultdict(list)
    for r in allpoints: points[r['point_id']].append(r)
    point_records=[]; training=[]; held=[]
    for pid,group in points.items():
        world=group[0]['world']; rays=np.array([world-r['Twc'][:3,3] for r in group]); rays/=np.linalg.norm(rays,axis=1)[:,None]
        if len(group)>1:
            a,b=np.triu_indices(len(rays),1)
            angle=float(np.degrees(np.arccos(np.clip(np.sum(rays[a]*rays[b],axis=1),-1,1))).max())
        else: angle=None
        learned_world=np.array([r['Twc'][:3,3]*scale+r['Twc'][:3,:3]@(np.linalg.solve(k,[r['u'],r['v'],1])*r['learned_z_m']) for r in group])
        centre=np.median(learned_world,axis=0)
        spread=np.linalg.norm(learned_world-centre,axis=1)
        dev=np.array([r['timestamp']<=split for r in group]); fixed_discrepancy=None
        if int(dev.sum())>=3:
            # The diagnostic reference learned point is fixed using development
            # network samples only. Held-out network predictions never set it.
            development_centre=np.median(learned_world[dev],axis=0)
            fixed_discrepancy=np.linalg.norm(learned_world-development_centre,axis=1)
            training.append(float(np.median(fixed_discrepancy[dev])))
            if (~dev).any(): held.append(float(np.median(fixed_discrepancy[~dev])))
        ratios=np.array([r['learned_z_m']/r['map_z_units'] for r in group])
        normalised=np.array([r['learned_z_m']/(r['map_z_units']*frame_scales[r['frame_id']]) for r in group])
        point_records.append({'point_id':pid,'observations':len(group),'parallax_max_deg':angle,
                              'world_discrepancy_median_m':float(np.median(spread)) if len(group)>=3 else None,
                              'log_ratio_mad':float(np.median(abs(np.log(ratios)-np.median(np.log(ratios))))) if len(group)>=3 else None,
                              'frame_scale_removed_log_ratio_mad':float(np.median(abs(np.log(normalised)-np.median(np.log(normalised))))) if len(group)>=3 else None})
        for ii,(r,discrepancy) in enumerate(zip(group,spread)):
            r['parallax_max_deg']=angle; r['world_discrepancy_m']=float(discrepancy)
            r['development_reference_discrepancy_m']=float(fixed_discrepancy[ii]) if fixed_discrepancy is not None else None
            r['threshold_split']='development' if dev[ii] else 'held_out'
            r['map_z_m']=r['map_z_units']*scale; r['disagreement_m']=abs(r['learned_z_m']-r['map_z_m'])
            r['map_error_m']=None if r['reference_z_m'] is None else abs(r['map_z_m']-r['reference_z_m'])
            r['learned_error_m']=None if r['reference_z_m'] is None else abs(r['learned_z_m']-r['reference_z_m'])
    scalar=[{key:value for key,value in r.items() if key not in ['Twc','world']} for r in allpoints]
    table(out/'observations.csv',scalar); table(out/'points.csv',point_records)
    breakdown=[]
    for field,bounds in [('parallax_max_deg',[0,1,3,10,1e9]),('learned_z_m',[0,1,2,3,5,10,1e9]),('normalised_radius',[0,.5,1,2,1e9])]:
        bins=defaultdict(lambda:defaultdict(list))
        for r in scalar: bins[bin_label(r[field],bounds)][r['point_id']].append(r)
        for label,pts in bins.items():
            for metric in ['disagreement_m','map_error_m','learned_error_m']:
                values=[float(np.median([r[metric] for r in p if r[metric] is not None])) for p in pts.values() if any(r[metric] is not None for r in p)]
                breakdown.append({'dimension':field,'bin':label,'metric':metric,'observations':sum(len(p) for p in pts.values()),**robust(values)})
    table(out/'breakdown.csv',breakdown)
    table(out/'frame_scale.csv',[{'frame_id':fid,'scale_metres_per_map_unit':s} for fid,s in sorted(frame_scales.items())])
    # Fit over per-point development medians, not repeated observations. Evaluate
    # the fixed threshold over later per-point medians with a development reference.
    med=float(np.median(training)) if training else None
    threshold=med+3*1.4826*float(np.median(abs(np.array(training)-med))) if training else None
    summary={'points':len(points),'observations':len(scalar),'map_scale':scale,'scale_source':'network/map development-interval median on final BA map; no reference pose or true depth used' if arbitrary_scale else 'method metric map units (E1 initialisation confirmed when selected)',
             'reference_depth_available':any(r['reference_z_m'] is not None for r in scalar),
             'temporal_world_discrepancy':robust([r['world_discrepancy_median_m'] for r in point_records if r['world_discrepancy_median_m'] is not None]),
             'threshold_development_end_s':split,'diagnostic_threshold_m':threshold,
             'threshold_development_points':len(training),'threshold_heldout_points':len(held),
             'threshold_protocol':'First fraction of input time; fixed learned-point references need >=3 development observations; threshold and rejection use per-point medians. New held-out points without development observations are unavailable.',
             'heldout_rejection_fraction':float(np.mean(np.array(held)>threshold)) if held and threshold is not None else None,
             'policy_applied_to_part3':bool(spec.get('temporal',{}).get('enabled')),'online_policy_report':read(run/'part3_runtime.json') if (run/'part3_runtime.json').exists() else None,
             'limitations':['Final BA map poses include future information; thresholds above are offline diagnostics, not a causal online policy',
                            'World-space learned-point discrepancy includes map/pose error; raw camera depths were not treated as network flicker',
                            'Repeated observations aggregated per persistent point; compare spread across runs',
                            'Pseudo-RGB-D map points can originate from learned depth; their agreement is not independent validation of triangulation. Point creation provenance is unavailable.',
                            'Phone disagreement alone cannot establish which depth source is correct'],
             'parallax_definition':'Maximum angle over distinct observing camera-to-same-map-point world rays; no self-pairs'}
    dump(out/'summary.json',summary)
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(1,2,figsize=(10,4)); sample=[r for r in scalar[::max(1,len(scalar)//5000)] if r['parallax_max_deg'] is not None]
    ax[0].scatter([r['parallax_max_deg'] for r in sample],[r['disagreement_m'] for r in sample],s=2,alpha=.2)
    ax[0].set_xlabel('maximum point parallax (degrees)'); ax[0].set_ylabel('|learned Z - map Z| (m)')
    p=[r for r in point_records if r['world_discrepancy_median_m'] is not None]
    ax[1].hist([r['world_discrepancy_median_m'] for r in p],bins=40); ax[1].set_xlabel('per-point median world discrepancy (m)'); ax[1].set_ylabel('persistent points')
    fig.tight_layout(); fig.savefig(out/'agreement.png'); plt.close(fig)
    return summary

def failure_trace(results,metadata,out,prep,work):
    baseline=[r for r in results if r['method']=='mono' and r['ate_scaled_m']!='']
    diagnostic=[r for r in results if r['method']!='mono' and r['ate_scaled_m']!='']
    record={'selection_rule':'Learned-depth run with largest scaled ATE exceeding baseline mean; then timestamp with largest positive local scaled-error difference against baseline run nearest baseline mean.',
            'causality':'Association only; inspect RGB/prediction/map and tracking states before interpreting cause.'}
    if not baseline or not diagnostic:
        dump(out/'failure_trace.json',{**record,'status':'unavailable','reason':'Need baseline and learned-depth scored runs'}); return
    mean=float(np.mean([float(r['ate_scaled_m']) for r in baseline])); sd=float(np.std([float(r['ate_scaled_m']) for r in baseline],ddof=1)) if len(baseline)>1 else None
    bad=max(diagnostic,key=lambda r:float(r['ate_scaled_m'])); record.update(baseline_mean_ate_m=mean,baseline_sd_m=sd)
    if float(bad['ate_scaled_m'])<=mean:
        dump(out/'failure_trace.json',{**record,'status':'no_worsened_case','reason':'No tested learned-depth configuration exceeded baseline mean scaled ATE; no cause fabricated. A declared higher-trust adapter setting remains a possible follow-up.'}); return
    base=min(baseline,key=lambda r:abs(float(r['ate_scaled_m'])-mean))
    b={r['timestamp']:r for r in rows(out/'matched'/f'{base["run_id"]}.csv')}; diffs=[]
    for r in rows(out/'matched'/f'{bad["run_id"]}.csv'):
        if r['timestamp'] in b: diffs.append((float(r['scaled_error_m'])-float(b[r['timestamp']]['scaled_error_m']),r))
    if not diffs:
        dump(out/'failure_trace.json',{**record,'status':'unavailable','reason':'No common scored timestamps'}); return
    delta,r=max(diffs,key=lambda x:x[0]); t=float(r['timestamp']); frames=rows(prep/'frames.csv'); f=min(frames,key=lambda f:abs(float(f['timestamp'])-t)); fid=int(f['frame_id'])
    record.update(status='candidate_requires_interpretation',learned_run=bad['run_id'],baseline_run=base['run_id'],frame_id=fid,timestamp=t,local_scaled_error_difference_m=delta,
                  exceeds_baseline_sd=None if sd is None else float(bad['ate_scaled_m'])>mean+sd,
                  scene_hazards=['blank walls','mirror','glass surfaces','motion blur'])
    dump(out/'failure_trace.json',record)
    try:
        depth=artifact(work,'depth'); pred=np.load(depth/'raw_m'/f'{fid:06d}.npy'); img=cv2.cvtColor(cv2.imread(str(prep/f['image'])),cv2.COLOR_BGR2RGB)
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,ax=plt.subplots(1,2,figsize=(10,4)); ax[0].imshow(img); ax[1].imshow(pred,cmap='viridis'); ax[0].set_title(f'RGB {t:.3f}s'); ax[1].set_title('Network optical Z (m); no true depth')
        for a in ax: a.axis('off')
        fig.tight_layout(); fig.savefig(out/'failure_candidate.png'); plt.close(fig)
    except Blocked: pass

def analyse_standard(c,work):
    from scoring import aggregate
    from part3_results import import_results
    imported=import_results(c,work) if c.get('part3_source') else None
    source=CODE/'inputs/part2.csv'
    baseline=CODE/'inputs/part1.csv'
    stage=Stage(work,'standard',c['standard'],[source,baseline,*([imported/'stage.json'] if imported else [])])
    if stage.cached():publish_pointer(work,'standard',stage);return stage.path
    out=stage.begin()
    table(out/'part2_inventory.csv',[{'source':'code/inputs/part2.csv','rows':len(rows(source))}])
    table(out/'baseline_aggregates.csv',aggregate(rows(baseline)))
    blockers=[]; analyses=[]
    for entry in c['standard']:
        try:
            paths={k:ROOT/entry[k] for k in ['run','prepared','predicted_depth']}
            truth={int(k):(ROOT/v['path'],v['factor']) for k,v in entry.get('true_depth',{}).items()}
            analyses.append(analyse_run(paths['run'],paths['prepared'],paths['predicted_depth'],out/entry['id'],c,truth,entry.get('predicted_png_factor'),entry.get('deployable_scale')))
        except (Blocked,FileNotFoundError) as e: blockers.append({'id':entry['id'],'reason':str(e)})
    if not c['standard']:
        blockers.append({'id':'all_standard_sequences','reason':'Detailed standard comparisons await the explicit long run-standard command. Local TUM, Replica and KITTI inputs passed three-frame preparation/depth smoke checks. The rerunner generates dense predictions and enriched persistent-point/pose exports without needing more teammate files. Historical Part 2 observations lack sufficient pose/world fields, and historical Part 3 logs are pair matches, so neither is relabelled as a complete temporal intervention experiment.'})
    dump(out/'status.json',{'analyses':analyses,'blockers':blockers,'full_standard_part4_completed':False,
                           'existing_results_are_historical':True,'part3_results_available':bool(imported),'part3_import':str(imported.relative_to(ROOT)) if imported else None,
                           'legacy_map_exports':[r['path'] for r in inventory if r['path'].endswith('map_observations.csv')],
                           'trajectory_exports':[r['path'] for r in inventory if r['path'].endswith('trajectory_final.json')]})
    stage.finish(['part2_inventory.csv','baseline_aggregates.csv','status.json']); publish_pointer(work,'standard',stage)
    print(json.dumps(read(out/'status.json'),indent=2)); return out

def analyse_own(c,work):
    """Run the depth/map diagnostics even while metric marker selection is pending."""
    prep=artifact(work,'prepare'); dep=artifact(work,'depth'); runs=[]
    from common import digest
    for p in sorted((work/'slam').glob('*/run.json')):
        s=read(p.parent/'spec.json'); oldprep=ROOT/s['prepare']
        if s.get('max_frames') is None and read(p)['status']=='complete' and digest(oldprep/'frames.csv')==digest(prep/'frames.csv'):
            runs.append(p.parent)
    if not runs: raise Blocked('No completed full-sequence runs for own-sequence analysis')
    inputs=[dep/'stage.json',prep/'camera.json',*[p/'map_observations.csv' for p in runs],*[p/'spec.json' for p in runs]]
    stage=Stage(work,'own_analysis',{'development_fraction':c['methods']['temporal_policy_development_fraction']},inputs)
    if stage.cached(): publish_pointer(work,'own_analysis',stage); return stage.path
    out=stage.begin(); summaries=[]; expected=[]
    for p in runs:
        print(f'Analysing map/depth: {p.name}',flush=True)
        try:
            summary=analyse_run(p,prep,dep,out/p.name,c)
            summaries.append({'run':str(p.relative_to(ROOT)),'summary':str((out/p.name/'summary.json').relative_to(ROOT)),
                              'points':summary['points'],'observations':summary['observations']})
            expected.extend([f'{p.name}/summary.json',f'{p.name}/breakdown.csv',f'{p.name}/points.csv',f'{p.name}/agreement.png'])
        except Blocked as e: summaries.append({'run':str(p.relative_to(ROOT)),'blocked':str(e)})
    dump(out/'index.json',{'runs':summaries,'no_phone_true_depth':True,'metric_reference_required':False,
                          'part3_intervention_complete':any(read(p/'spec.json').get('temporal',{}).get('enabled') for p in runs),'source':'actual final map observations and actual cached network predictions'})
    stage.finish(['index.json',*expected]); publish_pointer(work,'own_analysis',stage)
    print(out); return out
