"""Decode original PTS, calibrate in encoded camera coordinates, undistort once."""
from pathlib import Path
import json
import subprocess
import time
import cv2
import numpy as np
from common import AUX, ROOT, Stage, Blocked, atomic, dump, read, table, publish_pointer, artifact, utc, executable
from geometry import rotate_intrinsics,resize_intrinsics

def probe(video):
    args=[executable('ffprobe'),'-v','error','-select_streams','v:0','-show_streams','-show_frames',
          '-show_entries','stream=width,height,r_frame_rate,avg_frame_rate,color_transfer:stream_tags=rotate:stream_side_data=rotation:frame=best_effort_timestamp_time,pkt_duration_time','-of','json',video]
    r=subprocess.run([str(x) for x in args],capture_output=True,text=True,check=True)
    d=json.loads(r.stdout); s=d['streams'][0]
    timestamps=np.array([float(f['best_effort_timestamp_time']) for f in d['frames'] if 'best_effort_timestamp_time' in f])
    if len(timestamps)!=len(d['frames']) or not len(timestamps) or np.any(np.diff(timestamps)<=0):
        raise ValueError('Missing, repeated or nonmonotonic source presentation timestamps')
    rotation=float(next((x['rotation'] for x in s.get('side_data_list',[]) if 'rotation' in x),s.get('tags',{}).get('rotate',0)))
    if abs(rotation/90-round(rotation/90))>1e-5: raise ValueError('Non-right-angle rotation metadata')
    return {'stream':s,'timestamps':timestamps.tolist(),'clockwise_rotation':int(-rotation)%360,
            'probe_argv':[str(x) for x in args], 'probed_utc':utc()}

def nearest_frames(t,fps,start=None,end=None):
    t=np.asarray(t); start=t[0] if start is None else start; end=t[-1] if end is None else min(end,t[-1])
    if fps<=0 or start>end: raise ValueError('Invalid FPS or trim bounds')
    targets=np.arange(start,end+1e-8,1/fps)
    chosen={}
    for goal in targets:
        j=int(np.searchsorted(t,goal)); opts=[k for k in (j-1,j) if 0<=k<len(t) and start<=t[k]<=end]
        if opts:
            i=min(opts,key=lambda k:abs(t[k]-goal))
            chosen.setdefault(i,float(goal))
    return chosen

def decode(video,meta,selected,stage,label):
    w,h=meta['stream']['width'],meta['stream']['height']
    # Disable FFmpeg autorotation; apply recorded rotation once after undistortion.
    # HLG/Dolby Vision base layer is converted identically for scene and board via FFmpeg swscale.
    args=[executable('ffmpeg'),'-v','error','-noautorotate','-i',str(video),'-map','0:v:0','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','bgr24','pipe:1']
    rec={'argv':args,'started_utc':utc(),'geometry':'encoded; noautorotate','colour':'FFmpeg swscale to BGR8; no scene-specific exposure changes'}
    p=None; t=time.perf_counter(); n=0
    log=stage.path/f'{label}_decode.stderr.log'
    try:
        with log.open('wb') as err:
            p=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=err)
            while True:
                buf=p.stdout.read(w*h*3)
                if not buf: break
                if len(buf)!=w*h*3: raise RuntimeError('Truncated decoded frame')
                if n in selected:
                    yield n,np.frombuffer(buf,np.uint8).reshape(h,w,3).copy()
                n+=1
            rc=p.wait()
            if rc: raise RuntimeError(f'Decode failed: {log}')
        if n!=len(meta['timestamps']): raise RuntimeError(f'Decoded {n} frames, but {len(meta["timestamps"])} PTS records')
    finally:
        if p is not None and p.poll() is None:
            p.kill(); p.wait()
        dump(stage.path/f'{label}_decode.json',{**rec,'ended_utc':utc(),'elapsed_s':time.perf_counter()-t,
                                            'exit_code':None if p is None else p.returncode,'decoded_frames':n})

def contact(images,path,labels=None):
    if not images: return
    cells=[]
    for i,img in enumerate(images):
        h,w=img.shape[:2]; out=np.full((224,360,3),240,np.uint8)
        scale=min(360/w,200/h); thumb=cv2.resize(img,(round(w*scale),round(h*scale)))
        out[:thumb.shape[0],:thumb.shape[1]]=thumb
        cv2.putText(out,str(labels[i] if labels else i),(7,218),cv2.FONT_HERSHEY_SIMPLEX,.43,(20,20,20),1,cv2.LINE_AA)
        cells.append(out)
    while len(cells)%4: cells.append(np.full_like(cells[0],240))
    cv2.imwrite(str(path),np.vstack([np.hstack(cells[i:i+4]) for i in range(0,len(cells),4)]))

def calibrate(config,work,videos=None,cols=None,rows=None,square=None):
    c=config['calibration']; videos=videos or [ROOT/p for p in c['videos']]
    cols=cols or c['board_cols']; rows=rows or c['board_rows']; square=square or c['square_size_m']
    settings={**c,'board_cols':cols,'board_rows':rows,'square_size_m':square,'video_paths':[str(p) for p in videos]}
    stage=Stage(work,'calibration',settings,videos)
    if stage.cached(): publish_pointer(work,'calibration',stage); return stage.path
    out=stage.begin(); (out/'overlays').mkdir(exist_ok=True)
    obj=np.zeros((cols*rows,3),np.float32); obj[:,:2]=np.mgrid[0:cols,0:rows].T.reshape(-1,2)*square
    points=[]; descriptors=[]; views=[]; previews=[]; preview_labels=[]; size=None
    for vi,video in enumerate(videos):
        meta=probe(video); dump(out/f'video_{vi}_probe.json',meta)
        wh=(meta['stream']['width'],meta['stream']['height'])
        if size is not None and size!=wh: raise ValueError('Calibration clips have different encoded image sizes')
        size=wh; selected=nearest_frames(meta['timestamps'],c.get('sample_fps',2))
        for n,img in decode(video,meta,selected,stage,f'calibration_{vi}'):
            gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
            f=min(1,960/size[0]); small=cv2.resize(gray,None,fx=f,fy=f)
            ok,cp=cv2.findChessboardCornersSB(small,(cols,rows),cv2.CALIB_CB_NORMALIZE_IMAGE)
            if not ok: continue
            cp=cp/f
            cp=cv2.cornerSubPix(gray,cp.astype(np.float32),(5,5),(-1,-1),(cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,40,.001))
            uv=cp[:,0]; bounds=np.ptp(uv,axis=0)
            sharp=float(cv2.Laplacian(gray,cv2.CV_64F).var())
            # Occupancy, position, orientation and projective shape prevent retaining near-duplicates.
            grid=uv.reshape(rows,cols,2)
            axis=grid[0,-1]-grid[0,0]; angle=np.arctan2(axis[1],axis[0])
            desc=np.r_[uv.mean(0)/size,bounds/size, np.sin(angle)*.2,np.cos(angle)*.2,
                       np.linalg.norm(grid[0,-1]-grid[0,0])/max(np.linalg.norm(grid[-1,-1]-grid[-1,0]),1)*.15]
            if descriptors and min(np.linalg.norm(desc-d) for d in descriptors)<c.get('diversity_distance',.055): continue
            points.append(cp); descriptors.append(desc)
            views.append({'video':str(Path(video).relative_to(ROOT)),'source_frame':n,'timestamp':meta['timestamps'][n],
                          'sharpness':sharp,'centre_normalised':(uv.mean(0)/size).tolist(),'span_normalised':(bounds/size).tolist()})
            overlay=img.copy(); cv2.drawChessboardCorners(overlay,(cols,rows),cp,True)
            cv2.imwrite(str(out/'overlays'/f'{len(points):03d}.jpg'),overlay)
            previews.append(overlay); preview_labels.append(f'view {len(points)} / clip {vi+1} / {n}')
    if len(points)<12: raise Blocked(f'Only {len(points)} diverse board views detected; need at least 12. Add sharp views at varied tilts/positions.')
    if len(points)>60:
        ids=np.linspace(0,len(points)-1,60).astype(int); points=[points[i] for i in ids]; views=[views[i] for i in ids]
    flags=cv2.CALIB_FIX_K3
    def fit(ids): return cv2.calibrateCamera([obj]*len(ids),[points[i] for i in ids],size,None,None,flags=flags)
    rmse,k,dist,rv,tv=fit(list(range(len(points))))
    errors=[]; normals=[]
    for cp,r,t in zip(points,rv,tv):
        pred=cv2.projectPoints(obj,r,t,k,dist)[0]
        errors.append(float(np.sqrt(np.mean(np.sum((pred-cp)**2,axis=2)))))
        normals.append(cv2.Rodrigues(r)[0][:,2])
    # Hold out every fifth view and refit; solve board extrinsics without changing intrinsics.
    train=[i for i in range(len(points)) if i%5]; hold=[i for i in range(len(points)) if not i%5]
    _,kh,dh,_,_=fit(train); held=[]
    for i in hold:
        ok,r,t=cv2.solvePnP(obj,points[i],kh,dh)
        if ok: held.append(float(np.sqrt(np.mean(np.sum((cv2.projectPoints(obj,r,t,kh,dh)[0]-points[i])**2,axis=2)))))
    fits=[]
    for mod in range(3):
        ids=[i for i in range(len(points)) if i%3!=mod]
        _,ki,_,_,_=fit(ids); fits.append([ki[0,0],ki[1,1],ki[0,2],ki[1,2]])
    stability=np.std(np.array(fits),axis=0)/np.array([k[0,0],k[1,1],size[0],size[1]])
    normal_angles=np.degrees(np.arccos(np.clip(np.array(normals)@np.array(normals).T,-1,1)))
    spans=np.array([v['span_normalised'] for v in views]); centers=np.array([v['centre_normalised'] for v in views])
    warnings=[]
    if normal_angles.max()<15: warnings.append('Weak board tilt diversity')
    if np.any(np.ptp(centers,axis=0)<.25): warnings.append('Weak board-centre coverage in at least one image direction')
    if max(stability[:2])>.05: warnings.append('Focal length changes by over 5% across repeated fits; inspect before final scoring')
    if k[0,0]<=0 or k[1,1]<=0 or not np.isfinite(k).all(): raise ValueError('Invalid fitted intrinsics')
    result={'image_size':size,'K':k.tolist(),'distortion':dist.ravel().tolist(),'board_cols':cols,'board_rows':rows,'square_size_m':square,
            'rms_px':rmse,'views':len(points),'per_view_rmse_px':errors,'holdout_rmse_px':held,'repeated_fit_parameters':fits,
            'relative_fit_stability':stability.tolist(),'max_normal_angle_deg':float(normal_angles.max()),
            'warnings':warnings,'geometry':'encoded video coordinates, before metadata rotation',
            'review_required':True,'note':'No universal pixel-error acceptance threshold; inspect overlays, coverage and fit stability.'}
    dump(out/'calibration.json',result); dump(out/'views.json',views)
    contact(previews,out/'contact_sheet.jpg',preview_labels)
    stage.finish(['calibration.json','views.json','contact_sheet.jpg'])
    publish_pointer(work,'calibration',stage)
    print(json.dumps(result,indent=2),flush=True)
    return out

def prepare(config,work,video=None):
    video=Path(video or ROOT/config['video']); calpath=artifact(work,'calibration')/'calibration.json'; cal=read(calpath)
    stage=Stage(work,'prepare',{'frames':config['frames'],'depth_png_factor':config['depth']['png_factor']},[video,calpath])
    if stage.cached(): publish_pointer(work,'prepare',stage); return stage.path
    out=stage.begin(); rgb=out/'rgb'; rgb.mkdir(exist_ok=True)
    meta=probe(video); dump(out/'video_probe.json',meta)
    w,h=meta['stream']['width'],meta['stream']['height']
    if [w,h]!=cal['image_size']: raise ValueError('Scene encoded resolution differs from calibration')
    k=np.array(cal['K']); dist=np.array(cal['distortion']); rot=meta['clockwise_rotation']
    kr,(wr,hr)=rotate_intrinsics(k,w,h,rot)
    resize=min(1,config['frames']['max_dimension']/max(wr,hr)); wo,ho=round(wr*resize),round(hr*resize)
    ko=resize_intrinsics(kr,(wr,hr),(wo,ho))
    mx,my=cv2.initUndistortRectifyMap(k,dist,None,k,(w,h),cv2.CV_32FC1)
    f=config['frames']; selected=nearest_frames(meta['timestamps'],f['target_fps'],f.get('trim_start_s'),f.get('trim_end_s'))
    frame_rows=[]; samples=[]; labels=[]
    sample_ids=set(np.linspace(0,len(selected)-1,min(20,len(selected))).astype(int)); previous=None
    for source,img in decode(video,meta,selected,stage,'scene'):
        img=cv2.remap(img,mx,my,cv2.INTER_LINEAR)
        if rot: img=cv2.rotate(img,{90:cv2.ROTATE_90_CLOCKWISE,180:cv2.ROTATE_180,270:cv2.ROTATE_90_COUNTERCLOCKWISE}[rot])
        img=cv2.resize(img,(wo,ho),interpolation=cv2.INTER_AREA)
        i=len(frame_rows); name=f'rgb/{i:06d}.png'; path=out/name
        if not cv2.imwrite(str(path),img): raise RuntimeError(f'Cannot write {path}')
        gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
        thumb=cv2.resize(gray,(64,36)); duplicate=bool(previous is not None and np.array_equal(previous,thumb)); previous=thumb
        frame_rows.append({'frame_id':i,'source_frame_index':source,'timestamp':meta['timestamps'][source],
                           'target_timestamp':selected[source],'selection_error_s':meta['timestamps'][source]-selected[source],
                           'image':name,'sha256':__import__('hashlib').sha256(path.read_bytes()).hexdigest(),
                           'blur_laplacian_variance':float(cv2.Laplacian(gray,cv2.CV_64F).var()),
                           'dark_fraction':float((gray<8).mean()),'bright_fraction':float((gray>247).mean()),'duplicate_thumbnail':duplicate})
        if i in sample_ids: samples.append(img); labels.append(f'{i} / {meta["timestamps"][source]:.3f}s')
    if not frame_rows: raise ValueError('No selected frames')
    table(out/'frames.csv',frame_rows)
    atomic(out/'rgb.txt',''.join(f'{r["timestamp"]:.9f} {r["image"]}\n' for r in frame_rows))
    atomic(out/'times.txt',''.join(f'{r["timestamp"]:.9f}\n' for r in frame_rows))
    camera={'K':ko.tolist(),'width':wo,'height':ho,'distortion':[0]*5,'fps':f['target_fps'],'rotation_clockwise':rot,'undistorted':True}
    dump(out/'camera.json',camera)
    values={'Camera.fx':ko[0,0],'Camera.fy':ko[1,1],'Camera.cx':ko[0,2],'Camera.cy':ko[1,2],
            'Camera.width':wo,'Camera.height':ho,'Camera.fps':f['target_fps'],'Camera.RGB':1,
            'Camera.k1':0.,'Camera.k2':0.,'Camera.k3':0.,'Camera.p1':0.,'Camera.p2':0.,
            'Camera.bf':40.,'ThDepth':40.,'DepthMapFactor':config['depth']['png_factor'],
            'FeatureTrackerConfig.nFeatures':2000,'Viewer.on':0}
    atomic(out/'camera.yaml',''.join(f'{key}: {float(val) if isinstance(val,np.floating) else val}\n' for key,val in values.items()))
    dump(out/'quality.json',{'frames':len(frame_rows),'source_frames':len(meta['timestamps']),'selected_all_methods_identically':True,
                            'warnings':cal['warnings'],'colour_policy':'FFmpeg BGR8 conversion of HDR base layer; applied identically to calibration/scene',
                            'challenging_frames_discarded':False,'timestamps':'actual source PTS; no synthetic spacing'})
    contact(samples,out/'contact_sheet.jpg',labels)
    stage.finish(['frames.csv','rgb.txt','times.txt','camera.json','camera.yaml','quality.json','contact_sheet.jpg']+[r['image'] for r in frame_rows])
    publish_pointer(work,'prepare',stage)
    print(f'Prepared {len(frame_rows)} frames at {wo}x{ho}; original PTS retained.',flush=True)
    return out
