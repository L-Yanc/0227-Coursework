"""Fast marker/reference checks. Never launches SLAM, inference or reconstruction."""
from pathlib import Path
import numpy as np
from common import ROOT, Stage, Blocked, artifact, digest, dump, read, rows, publish_pointer
from geometry import triangulate

def marker_report(c,work,write=True,reference_path=None,annotations_path=None):
    ref=Path(reference_path) if reference_path else artifact(work,'reference'); prep=artifact(work,'prepare'); annotations=Path(annotations_path) if annotations_path else work/'annotations.json'
    if not annotations.exists(): raise Blocked('Save marker selections in the annotation tool first')
    settings={'markers':c['markers'],'reference':c['reference']}
    stage=Stage(work,'marker_review',settings,[annotations,ref/'stage.json',prep/'camera.json'])
    if write and stage.cached():
        publish_pointer(work,'marker_review',stage); return read(stage.path/'review.json')
    ann=read(annotations); images=read(ref/'registered.json'); camera=read(ref/'camera.json') if (ref/'camera.json').exists() else read(prep/'camera.json')
    k=np.array(camera['K']); border=c['reference'].get('marker_border_margin_px',12.)
    result={'annotations_sha256':digest(annotations),'reference_key':read(ref/'stage.json')['key'],
            'saved_selections':len(ann['selections']),'markers':{},'blockers':[],
            'measurement_units':'metres','image_points_changed':False,
            'limitations':['Reference-pose/calibration uncertainty is not included in the conditional pixel-noise covariance.',
                           'Adjacent frames are correlated evidence; extra clicks cannot replace camera translation.']}
    if ann.get('reference_key')!=result['reference_key']: raise Blocked('Selections refer to another reconstruction; validate/rebase identical image geometry before using them')
    scales=[]
    for m in c['markers']:
        item={'role':m['role'],'measured_distance_m':m['distance_m'],'measurement_uncertainty_m':m['uncertainty_m'],'endpoints':{}}
        points=[]
        for endpoint in m['endpoints']:
            original=[v for v in ann['selections'] if v['marker']==m['id'] and v['endpoint']==endpoint]
            clicks=[v for v in original if border<=v['u']<camera['width']-border and border<=v['v']<camera['height']-border]
            diag={'selected_views':len(original),'usable_border_views':len(clicks),
                  'border_exclusions':[v['image'] for v in original if v not in clicks]}
            try:
                if len({v['image'] for v in clicks})!=len(clicks): raise ValueError('Duplicate image for this endpoint')
                if any(v['image'] not in images for v in clicks): raise ValueError('Unknown/unregistered annotation image')
                uv=np.array([[v['u'],v['v']] for v in clicks]); poses=np.array([images[v['image']]['Twc'] for v in clicks])
                x,d=triangulate(uv,poses,k,c['reference']['min_ray_angle_deg'],c['reference']['max_marker_residual_px'])
                keep=np.array(d['inliers']); errors=np.array(d['residual_px'])
                diag.update(d,point=x.tolist(),views=[v['image'] for v in clicks],inlier_views=[v['image'] for v,ok in zip(clicks,keep) if ok],
                            median_inlier_residual_px=float(np.median(errors[keep])),status='fit')
                points.append(x)
            except ValueError as e:
                diag.update(status='failed',reason=str(e)); result['blockers'].append(f'{m["id"]}/{endpoint}: {e}')
            item['endpoints'][endpoint]=diag
        if len(points)==2:
            distance=float(np.linalg.norm(points[1]-points[0])); item['reconstructed_distance_units']=distance
            if distance<=1e-8: result['blockers'].append(f'{m["id"]}: zero endpoint separation')
            elif m['role']=='scale': scales.append(m['distance_m']/distance)
        result['markers'][m['id']]=item
    result['selections_sufficient']=not result['blockers']
    if scales:
        scale=float(np.median(scales)); result['metres_per_reference_unit']=scale
        for mid,item in result['markers'].items():
            if 'reconstructed_distance_units' not in item: continue
            estimate=scale*item['reconstructed_distance_units']; error=estimate-item['measured_distance_m']
            item.update(estimated_distance_m=estimate,error_m=error)
            if item['role']=='check':
                limit=c['reference'].get('max_check_error_m',.05)
                item['acceptance_limit_m']=limit; item['passes_check']=abs(error)<=limit
                if not item['passes_check']: result['blockers'].append(f'{mid}: held-out distance is {estimate:.3f}m, measured {item["measured_distance_m"]:.3f}m (limit {limit:.3f}m). Reference geometry is not validated.')
    else: result['blockers'].append('No valid primary scale marker')
    quality=read(ref/'reference_quality.json'); result['reference_coverage']=quality['registered_fraction']
    result['reference_max_gap_s']=quality['max_gap_s']
    if quality['registered_fraction']<c['reference']['min_registered_fraction']:
        result['blockers'].append(f'Reference coverage {quality["registered_fraction"]:.1%} is below configured target {c["reference"]["min_registered_fraction"]:.1%}')
    if quality.get('max_relative_focal_change',0)>c['reference'].get('max_relative_focal_change',.1):
        result['blockers'].append(f'Scene-refined focal length differs from checkerboard calibration by more than the configured {c["reference"].get("max_relative_focal_change",.1):.0%} tolerance; review calibration before final scoring.')
    result['metric_reference_ready']=not result['blockers']
    result['recommendation']='No more clicking is requested while reference geometry is being checked.' if result['selections_sufficient'] else 'Inspect excluded/cropped views and the reported fit failure before requesting additional views.'
    if write:
        stage.begin(); dump(stage.path/'review.json',result); stage.finish(['review.json']); publish_pointer(work,'marker_review',stage)
    return result

def preflight(c,work):
    result=marker_report(c,work)
    result['long_stages_started']=False
    print(__import__('json').dumps(result,indent=2))
    if not result['metric_reference_ready']:
        failed_repair=False
        if (work/'reference_repair_candidate.json').exists():
            candidate=artifact(work,'reference_repair_candidate')
            failed_repair=not read(candidate/'repair_review.json')['metric_reference_ready']
        advice='The declared repair already failed; use a new recording/configuration rather than repeating the same repair.' if failed_repair else 'Inspect marker_review.json and the declared repair before starting the expensive batch.'
        raise Blocked('Metric reference is not ready. '+advice+' Your existing selections are preserved.')
    return result

def validate_prepared_inputs(c,work):
    """Validate existing inputs for an explicit reuse request; do not re-extract media."""
    prep=artifact(work,'prepare'); calibration=artifact(work,'calibration')
    meta=read(prep/'stage.json'); saved=meta['settings'].get('frames',meta['settings'])
    if saved!=c['frames']: raise Blocked('Frame preparation settings changed; run prepare explicitly')
    if digest(ROOT/c['video']) not in meta['input_hashes'].values(): raise Blocked('Scene video changed; run prepare explicitly')
    if digest(calibration/'calibration.json') not in meta['input_hashes'].values(): raise Blocked('Calibration changed; run prepare explicitly')
    cal=read(calibration/'calibration.json')
    for field in ['board_cols','board_rows','square_size_m']:
        if not np.isclose(cal[field],c['calibration'][field]): raise Blocked('Checkerboard parameters changed; recalibrate explicitly')
    import yaml
    if yaml.safe_load((prep/'camera.yaml').read_text())['DepthMapFactor']!=c['depth']['png_factor']:
        raise Blocked('PNG factor changed; regenerate camera settings with prepare')
    for name,hash_ in meta['outputs'].items():
        if not (prep/name).exists() or digest(prep/name)!=hash_: raise Blocked(f'Prepared output is missing/corrupted: {name}')
    return prep
