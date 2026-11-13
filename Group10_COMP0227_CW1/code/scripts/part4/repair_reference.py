"""Explicit user-launched reference repair. No SLAM/depth batch is started here.

One declared focal/pose/point bundle refinement plus registration against the existing
map. Neither measured marker length enters COLMAP optimisation. Failed candidates
are retained without replacing the active reconstruction or moving annotation pixels.
"""
from pathlib import Path
import os
import shutil
import numpy as np
from common import ROOT,AUX,Stage,Blocked,artifact,atomic,digest,dump,read,rows,publish_pointer,executable
from geometry import write_tum
from reference import parse_images
from readiness import marker_report

def parse_camera(path):
    lines=[l.split() for l in Path(path).read_text().splitlines() if l.strip() and not l.startswith('#')]
    if len(lines)!=1 or lines[0][1]!='PINHOLE': raise Blocked('Repair expects one shared PINHOLE camera')
    p=lines[0]; fx,fy,cx,cy=map(float,p[4:8]); w,h=map(int,p[2:4])
    if not np.isfinite([fx,fy,cx,cy]).all() or min(fx,fy)<=0: raise Blocked('Invalid refined camera')
    return {'K':[[fx,0,cx],[0,fy,cy],[0,0,1]],'width':w,'height':h,'distortion':[0]*5,
            'geometry':'same already-undistorted input pixels; reference-only focal refinement'}

def repair_reference(c,work):
    source=artifact(work,'reference'); prep=artifact(work,'prepare'); quality=read(source/'reference_quality.json')
    if quality.get('repair_applied'):
        report=marker_report(c,work)
        if report['metric_reference_ready']: print('Declared reference repair already passed.'); return source
        raise Blocked('The declared repair has already been tried; inspect its diagnostics instead of tuning to the check length')
    database=source/'database.db'; model=source/'models'/quality['main_component'].removeprefix('text_')
    if not database.exists() or not (model/'images.bin').exists(): raise Blocked('Original COLMAP database/binary model is missing')
    annotations=work/'annotations.json'; original_ann_hash=digest(annotations)
    settings={'reference':c['reference'],'repair':'focal_only_intrinsics_and_pose_point_BA_then_register_then_BA',
              'iterations':[30,20],'marker_validation':c['markers'],'marker_lengths_used_in_optimisation':False}
    stage=Stage(work,'reference_repair',settings,[source/'stage.json',prep/'stage.json',annotations])
    if stage.cached():
        report=read(stage.path/'repair_review.json')
        if not report['metric_reference_ready']: raise Blocked(f'Previously completed repair did not pass; inspect {stage.path/"repair_review.json"}')
        ann=read(stage.path/'annotations.json')
        if ann['selections']!=read(annotations)['selections']: raise Blocked('Newer click coordinates differ; candidate not promoted')
        history=work/'annotation_history'; history.mkdir(exist_ok=True)
        if not (history/f'{original_ann_hash}.json').exists(): shutil.copyfile(annotations,history/f'{original_ann_hash}.json')
        dump(annotations,ann); publish_pointer(work,'reference',stage)
        print('Reused and promoted the completed passing repair; no long stages rerun.'); return stage.path
    out=stage.begin(); colmap=executable('colmap'); env=dict(os.environ,OMP_NUM_THREADS=str(c['reference']['threads']),OPENBLAS_NUM_THREADS='1')
    shutil.copyfile(database,out/'database.db'); database=out/'database.db'
    for command in ['bundle_adjuster','image_registrator','model_converter']: stage.run([colmap,command,'-h'])
    for folder in ['ba','registered_model','final_model','text_repaired']: (out/folder).mkdir(exist_ok=True)
    def ba(before,after,iterations):
        stage.run([colmap,'bundle_adjuster','--input_path',before,'--output_path',after,
                   '--BundleAdjustment.max_num_iterations',iterations,'--BundleAdjustment.max_linear_solver_iterations','100',
                   '--BundleAdjustment.refine_focal_length','1','--BundleAdjustment.refine_principal_point','0',
                   '--BundleAdjustment.refine_extra_params','0','--BundleAdjustment.use_gpu','0'],env=env)
    ba(model,out/'ba',30)
    stage.run([colmap,'image_registrator','--database_path',database,'--input_path',out/'ba','--output_path',out/'registered_model',
               '--Mapper.num_threads',c['reference']['threads'],'--Mapper.ba_refine_focal_length','0',
               '--Mapper.ba_refine_principal_point','0','--Mapper.ba_refine_extra_params','0'],env=env)
    ba(out/'registered_model',out/'final_model',20)
    stage.run([colmap,'model_converter','--input_path',out/'final_model','--output_path',out/'text_repaired','--output_type','TXT'])
    camera=parse_camera(out/'text_repaired/cameras.txt')
    original=read(prep/'camera.json')
    if (camera['width'],camera['height'])!=(original['width'],original['height']): raise Blocked('Repair changed image geometry; existing click coordinates cannot be reused')
    dump(out/'camera.json',camera)
    images=parse_images(out/'text_repaired/images.txt'); dump(out/'registered.json',images)
    frames=rows(prep/'frames.csv'); byname={Path(v['image']).name:v for v in frames}
    if any(name not in byname for name in images): raise Blocked('Repaired reference names do not match input images')
    names=sorted(images,key=lambda n:float(byname[n]['timestamp'])); times=[float(byname[n]['timestamp']) for n in names]
    dump(out/'annotation_candidates.json',[{'image':n,'timestamp':byname[n]['timestamp'],'frame_id':byname[n]['frame_id']} for n in names])
    points=[]; errors=[]; tracks=[]
    for line in (out/'text_repaired/points3D.txt').read_text().splitlines():
        if not line.strip() or line.startswith('#'): continue
        p=line.split(); points.append(list(map(float,p[1:4]))); errors.append(float(p[7])); tracks.append((len(p)-8)//2)
    dump(out/'points.json',points); write_tum(out/'reference_unscaled.tum',times,[np.array(images[n]['Twc']) for n in names])
    focal=np.diag(np.array(camera['K']))[:2]; initial=np.diag(np.array(original['K']))[:2]
    quality={**quality,'repair_applied':True,'intrinsics_fixed':False,'main_component':'text_repaired',
             'registered_frames':len(images),'input_frames':len(frames),'registered_fraction':len(images)/len(frames),
             'components':[len(images),*quality.get('components',[])[1:]],
             'passes_registered_fraction':len(images)/len(frames)>=c['reference']['min_registered_fraction'],
             'max_gap_s':float(np.diff(times).max()) if len(times)>1 else None,
             'median_reprojection_error_px':float(np.median(errors)) if errors else None,'median_track_length':float(np.median(tracks)) if tracks else None,
             'max_relative_focal_change':float(np.max(abs(focal/initial-1))),
             'source_reference':str(source.relative_to(ROOT)),'database_source':str(database.relative_to(ROOT)),
             'marker_lengths_used_in_optimisation':False,
             'check_interpretation':'0.5m excluded from optimisation and scale fit, but its earlier failure motivated QA; it is not an unseen model-selection test.'}
    dump(out/'reference_quality.json',quality)
    ann=read(annotations)
    if digest(annotations)!=original_ann_hash: raise Blocked('Selections changed during repair; candidate saved, current selections left intact')
    ann['reference_key']=stage.key
    ann['reference_rebase']={'from':read(source/'stage.json')['key'],'same_image_table_sha256':digest(prep/'frames.csv'),'pixel_coordinates_changed':False}
    dump(out/'annotations.json',ann)
    report=marker_report(c,work,write=False,reference_path=out,annotations_path=out/'annotations.json')
    dump(out/'repair_review.json',report)
    stage.finish(['camera.json','registered.json','points.json','annotation_candidates.json','reference_unscaled.tum','reference_quality.json','annotations.json','repair_review.json'])
    publish_pointer(work,'reference_repair_candidate',stage)
    if not report['metric_reference_ready']:
        raise Blocked(f'Repair finished but did not validate metric geometry. Active reference/selections preserved. Read {out/"repair_review.json"}')
    history=work/'annotation_history'; history.mkdir(exist_ok=True)
    archive=history/f'{original_ann_hash}.json'
    if not archive.exists(): shutil.copyfile(annotations,archive)
    dump(annotations,ann); publish_pointer(work,'reference',stage)
    print('Repaired reference passed configured checks. Existing click coordinates preserved. Run preflight, then run/evaluate as required.')
    return out
