"""Independent fixed-intrinsics COLMAP reconstruction and reviewed metric markers."""
from pathlib import Path
import http.server
import itertools
import json
import mimetypes
import urllib.parse
import numpy as np
from common import ROOT, SOURCE, AUX, Stage, Blocked, atomic, artifact, dump, read, rows, publish_pointer, digest, executable
from geometry import colmap_pose, triangulate, write_tum

def reconstruction_settings(settings):
    settings=settings.get('reference',settings)
    scoring={'min_ray_angle_deg','max_marker_residual_px','annotation_sigma_px','marker_border_margin_px',
             'max_check_error_m','annotation_trials','min_registered_fraction','max_relative_focal_change'}
    return {k:v for k,v in settings.items() if k not in scoring}

def parse_images(path):
    lines=Path(path).read_text().splitlines(); result={}; i=0
    while i<len(lines):
        line=lines[i]; i+=1
        if not line.strip() or line.lstrip().startswith('#'): continue
        p=line.split(maxsplit=9)
        if len(p)!=10: raise ValueError('Malformed COLMAP pose line')
        pose=colmap_pose([float(x) for x in p[1:5]],[float(x) for x in p[5:8]])
        if i>=len(lines): raise ValueError('Missing COLMAP observations line')
        obs=lines[i].split(); i+=1
        if len(obs)%3: raise ValueError('Malformed COLMAP observations')
        result[p[9]]={'image_id':int(p[0]),'camera_id':int(p[8]),'Twc':pose.tolist(),'observations':len(obs)//3}
    return result

def reference(c,work):
    prep=artifact(work,'prepare'); settings=c['reference']; cam=read(prep/'camera.json')
    # A completed COLMAP reconstruction can be reused when the actual image table and
    # camera are byte-identical, even if preparation provenance was regenerated.
    # Preserve its original source/command provenance; never pretend it was rerun.
    try:
        previous=artifact(work,'reference'); meta=read(previous/'stage.json')
        old_inputs=[ROOT/p for p in meta['input_hashes'] if p.endswith('/stage.json')]
        equivalent=any((p.parent/'frames.csv').exists() and digest(p.parent/'frames.csv')==digest(prep/'frames.csv')
                       and digest(p.parent/'camera.json')==digest(prep/'camera.json') for p in old_inputs)
        intact=all((previous/p).is_file() and digest(previous/p)==h for p,h in meta['outputs'].items())
        if equivalent and intact and reconstruction_settings(meta['settings'])==reconstruction_settings(settings):
            print('Reusing validated COLMAP reconstruction of identical prepared images/camera (original provenance retained).',flush=True)
            return scale_markers(c,work) if (work/'annotations.json').exists() else previous
    except Blocked: pass
    stage=Stage(work,'reference',settings,[prep/'stage.json',prep/'camera.json'])
    if stage.cached():
        publish_pointer(work,'reference',stage)
        return scale_markers(c,work) if (work/'annotations.json').exists() else stage.path
    out=stage.begin(); models=out/'models'; models.mkdir(exist_ok=True); database=out/'database.db'
    colmap=executable('colmap')
    for cmd in ['feature_extractor','sequential_matcher','matches_importer','mapper','model_converter']:
        stage.run([colmap,cmd,'-h'])
    k=np.array(cam['K']); params=','.join(str(v) for v in [k[0,0],k[1,1],k[0,2],k[1,2]])
    stage.run([colmap,'feature_extractor','--database_path',database,'--image_path',prep/'rgb',
               '--ImageReader.camera_model','PINHOLE','--ImageReader.single_camera','1','--ImageReader.camera_params',params,
               '--SiftExtraction.use_gpu','0','--SiftExtraction.num_threads',settings['threads'],
               '--SiftExtraction.max_num_features',settings['max_features']])
    stage.run([colmap,'sequential_matcher','--database_path',database,'--SiftMatching.use_gpu','0',
               '--SiftMatching.num_threads',settings['threads'],'--SequentialMatching.overlap',settings['overlap']])
    frames=rows(prep/'frames.csv'); candidates=[Path(r['image']).name for r in frames[::settings['loop_stride']]]
    pairs=[(a,b) for i,a in enumerate(candidates) for b in candidates[i+2:]]
    atomic(out/'loop_pairs.txt',''.join(f'{a} {b}\n' for a,b in pairs))
    if pairs:
        stage.run([colmap,'matches_importer','--database_path',database,'--match_list_path',out/'loop_pairs.txt','--match_type','pairs',
                   '--SiftMatching.use_gpu','0','--SiftMatching.num_threads',settings['threads']])
    stage.run([colmap,'mapper','--database_path',database,'--image_path',prep/'rgb','--output_path',models,
               '--Mapper.num_threads',settings['threads'],'--Mapper.ba_refine_focal_length','0',
               '--Mapper.ba_refine_principal_point','0','--Mapper.ba_refine_extra_params','0'])
    components=[]
    for p in sorted(models.iterdir()):
        if not p.is_dir(): continue
        text=out/f'text_{p.name}'; text.mkdir(exist_ok=True)
        stage.run([colmap,'model_converter','--input_path',p,'--output_path',text,'--output_type','TXT'])
        images=parse_images(text/'images.txt')
        components.append((len(images),text,images))
    if not components: raise Blocked('COLMAP produced no reconstruction. Inspect logs, calibration and motion.')
    components.sort(key=lambda x:x[0],reverse=True); n,text,images=components[0]
    byname={Path(r['image']).name:r for r in frames}
    if any(name not in byname for name in images): raise ValueError('COLMAP image names do not join prepared frames')
    ordered=sorted(images,key=lambda name:float(byname[name]['timestamp']))
    pts=[]; track=[]; reproj=[]
    for line in (text/'points3D.txt').read_text().splitlines():
        if not line.strip() or line.startswith('#'): continue
        p=line.split(); pts.append([float(x) for x in p[1:4]]); reproj.append(float(p[7])); track.append((len(p)-8)//2)
    times=[float(byname[name]['timestamp']) for name in ordered]
    quality={'reference_type':'approximate shared-image triangulation; not ground truth','components':[x[0] for x in components],
             'main_component':text.name,'registered_frames':n,'input_frames':len(frames),'registered_fraction':n/len(frames),
             'temporal_start_s':min(times),'temporal_end_s':max(times),'max_gap_s':float(np.max(np.diff(times))) if len(times)>1 else None,
             'median_track_length':float(np.median(track)) if track else None,'median_reprojection_error_px':float(np.median(reproj)) if reproj else None,
             'intrinsics_fixed':True,'passes_registered_fraction':n/len(frames)>=settings['min_registered_fraction'],
             'limitations':['Shared images and triangulation bias','Mirrors, glass, blank walls, blur and low parallax may harm reconstruction',
                            'A known distance fixes global scale only; does not validate the complete trajectory']}
    dump(out/'reference_quality.json',quality); dump(out/'registered.json',images)
    dump(out/'points.json',pts)
    candidates=[{'image':name,'timestamp':byname[name]['timestamp'],'frame_id':byname[name]['frame_id']} for name in ordered]
    dump(out/'annotation_candidates.json',candidates)
    write_tum(out/'reference_unscaled.tum',times,[np.array(images[name]['Twc']) for name in ordered])
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    xyz=np.array([images[name]['Twc'] for name in ordered])[:,:3,3]
    fig,ax=plt.subplots(1,2,figsize=(10,4)); ax[0].plot(xyz[:,0],xyz[:,2],'.-'); ax[0].set_aspect('equal'); ax[0].set_xlabel('x (arbitrary units)'); ax[0].set_ylabel('z')
    ax[1].plot([float(r['timestamp']) for r in frames],[int(Path(r['image']).name in images) for r in frames],'.'); ax[1].set_xlabel('time (s)'); ax[1].set_ylabel('registered')
    fig.tight_layout(); fig.savefig(out/'reference_quality.png'); plt.close(fig)
    stage.finish(['reference_quality.json','registered.json','points.json','annotation_candidates.json','reference_unscaled.tum','reference_quality.png'])
    publish_pointer(work,'reference',stage)
    print(f'COLMAP registered {n}/{len(frames)} frames. Run ./run-part4 annotate for wall marker centres.',flush=True)
    if (work/'annotations.json').exists(): return scale_markers(c,work)
    return out

def scale_markers(c,work):
    from readiness import marker_report
    review=marker_report(c,work)
    if not review['metric_reference_ready']:
        raise Blocked('Metric reference failed preflight: '+'; '.join(review['blockers']))
    ref=artifact(work,'reference'); prep=artifact(work,'prepare'); annpath=work/'annotations.json'
    if not annpath.exists(): raise Blocked('Marker centres required: ./run-part4 annotate')
    stage=Stage(work,'marker_scale',{'markers':c['markers'],'reference':c['reference']},[annpath,ref/'stage.json',prep/'camera.json'])
    if stage.cached(): publish_pointer(work,'marker_scale',stage); return stage.path
    out=stage.begin(); ann=read(annpath)
    dump(out/'annotations.json',ann)
    if ann.get('reference_key')!=read(ref/'stage.json')['key']: raise Blocked('Annotations refer to another reconstruction; review them again')
    images=read(ref/'registered.json'); k=np.array((read(ref/'camera.json') if (ref/'camera.json').exists() else read(prep/'camera.json'))['K']); fits={}; scales=[]
    rng=np.random.default_rng(20261112)
    for group in c['markers']:
        endpoints=[]; details={}; samples=[]
        for endpoint in group['endpoints']:
            accepted=review['markers'][group['id']]['endpoints'][endpoint]['inlier_views']
            clicks=[v for v in ann['selections'] if v['marker']==group['id'] and v['endpoint']==endpoint and v['image'] in accepted]
            if len({v['image'] for v in clicks})<3: raise Blocked(f'{group["id"]}/{endpoint}: select at least three well-separated registered views')
            uv=np.array([[v['u'],v['v']] for v in clicks]); poses=np.array([images[v['image']]['Twc'] for v in clicks])
            x,diag=triangulate(uv,poses,k,c['reference']['min_ray_angle_deg'],c['reference']['max_marker_residual_px'])
            endpoints.append(x); details[endpoint]={'point':x.tolist(),**diag,'views':[v['image'] for v in clicks]}
            trials=[]
            for _ in range(c['reference'].get('annotation_trials',25)):
                try: trials.append(triangulate(uv+rng.normal(0,c['reference']['annotation_sigma_px'],uv.shape),poses,k,c['reference']['min_ray_angle_deg'],c['reference']['max_marker_residual_px'])[0])
                except ValueError: pass
            samples.append(trials)
        distance=float(np.linalg.norm(endpoints[1]-endpoints[0]))
        if distance<=1e-8: raise ValueError('Marker endpoint distance is zero')
        distances=[float(np.linalg.norm(b-a)) for a,b in zip(*samples)]
        fits[group['id']]={'reconstructed_distance':distance,'measured_distance_m':group['distance_m'],'uncertainty_m':group['uncertainty_m'],
                          'role':group['role'],'endpoints':details,'annotation_distance_sd_units':float(np.std(distances,ddof=1)) if len(distances)>1 else None}
        if group['role']=='scale': scales.append(group['distance_m']/distance)
    if not scales: raise ValueError('At least one scale marker required')
    scale=float(np.median(scales))
    for fit in fits.values():
        fit['estimated_distance_m']=fit['reconstructed_distance']*scale
        fit['distance_error_m']=fit['estimated_distance_m']-fit['measured_distance_m']
    record={'metres_per_reference_unit':scale,'fit_uses_check_markers':False,'markers':fits,
            'uncertainty_note':'Tape +/-0.005m is a stated bound, not a Gaussian SD; annotation SD uses 1px Gaussian perturbations, excludes pose/calibration uncertainty'}
    dump(out/'marker_scale.json',record)
    frames={Path(r['image']).name:float(r['timestamp']) for r in rows(prep/'frames.csv')}
    names=sorted(images,key=lambda n:frames[n]); poses=[]
    for name in names:
        p=np.array(images[name]['Twc']); p[:3,3]*=scale; poses.append(p)
    write_tum(out/'reference_tum.txt',[frames[n] for n in names],poses)
    dump(out/'metric_points.json',(np.array(read(ref/'points.json'))*scale).tolist())
    stage.finish(['marker_scale.json','annotations.json','reference_tum.txt','metric_points.json']); publish_pointer(work,'marker_scale',stage)
    print(json.dumps(record,indent=2)); return out

def annotate(c,work,port):
    ref=artifact(work,'reference'); prep=artifact(work,'prepare'); candidates=read(ref/'annotation_candidates.json')
    key=read(ref/'stage.json')['key']; path=work/'annotations.json'; allowed={v['image'] for v in candidates}
    markers={m['id']:m['endpoints'] for m in c['markers']}; camera=read(prep/'camera.json')
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def send(self,data,kind='application/json'):
            if not isinstance(data,bytes): data=data.encode()
            self.send_response(200); self.send_header('Content-Type',kind); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
        def do_GET(self):
            url=urllib.parse.urlparse(self.path)
            if url.path=='/': self.send((SOURCE/'annotate.html').read_text(),'text/html; charset=utf-8')
            elif url.path=='/data': self.send(json.dumps({'candidates':candidates,'markers':markers,'reference_key':key,'saved':read(path) if path.exists() else {'selections':[]}}))
            elif url.path=='/image':
                name=urllib.parse.parse_qs(url.query).get('name',[''])[0]
                if name not in allowed: self.send_error(404); return
                self.send((prep/'rgb'/name).read_bytes(),'image/png')
            else: self.send_error(404)
        def do_POST(self):
            if self.path!='/save': self.send_error(404); return
            try:
                if int(self.headers.get('Content-Length','0'))>1000000: raise ValueError('Too large')
                d=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if d['reference_key']!=key: raise ValueError('Wrong reconstruction')
                seen=set()
                for v in d['selections']:
                    if v['image'] not in allowed or v['marker'] not in markers or v['endpoint'] not in markers[v['marker']]: raise ValueError('Unknown selection')
                    if not 0<=float(v['u'])<camera['width'] or not 0<=float(v['v'])<camera['height']: raise ValueError('Invalid pixel')
                    item=(v['image'],v['marker'],v['endpoint'])
                    if item in seen: raise ValueError('Duplicate view/endpoint')
                    seen.add(item)
                history=work/'annotation_history'; history.mkdir(exist_ok=True)
                if path.exists():
                    old=read(path); oldhash=__import__('hashlib').sha256(path.read_bytes()).hexdigest()
                    if not (history/f'{oldhash}.json').exists(): dump(history/f'{oldhash}.json',old)
                dump(path,d)
                if not (history/f'{digest(path)}.json').exists(): dump(history/f'{digest(path)}.json',d)
                self.send('{"saved":true}')
            except (ValueError,KeyError) as e: self.send_error(400,str(e))
    print(f'Open http://127.0.0.1:{port} — click each endpoint in 4–6 translated views, Save, then run reference. Ctrl+C stops this local server.',flush=True)
    try: http.server.ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
    except KeyboardInterrupt: pass
