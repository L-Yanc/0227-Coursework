"""Direct pySLAM track() adapter with no scoring/reference inputs.

Same ORB2, DBOW3, C++ backend and playback speed for every method. No sensor-depth
fabrication: skipped frames receive None, while RGB continues normally.
"""
import sys
from pathlib import Path
from common import ROOT, SLAM
sys.path.insert(0,str(SLAM))
import pyslam
import argparse
import copy
import csv
import json
import time
import cv2
import numpy as np
from common import ROOT, SLAM, atomic, dump, read, rows, table
from geometry import write_tum
from pacing import playback_delay

def export_observations(slam,out,frame_rows):
    byid={int(r['frame_id']):r for r in frame_rows}; records=[]
    for point in slam.map.get_points():
        if point.is_bad(): continue
        world=np.asarray(point.pt()).reshape(3)
        for kf,idx in point.observations():
            if kf is None or kf.is_bad(): continue
            source=int(kf.img_id); idx=int(idx)
            if source not in byid: raise ValueError(f'Keyframe source image {source} not in frames.csv')
            if idx<0 or idx>=len(kf.kps): raise ValueError('Invalid point observation index')
            tcw=np.asarray(kf.pose()); pc=tcw[:3,:3]@world+tcw[:3,3]
            if not np.isfinite(pc).all() or pc[2]<=0: continue
            u,v=kf.kps[idx][:2]; twc=np.linalg.inv(tcw)
            records.append({'frame_id':source,'source_frame_index':int(byid[source]['source_frame_index']),
                            'timestamp':float(byid[source]['timestamp']),'keyframe_id':int(kf.id),'point_id':int(point.id),
                            'u':float(u),'v':float(v),'map_depth':float(pc[2]),
                            'world_x':float(world[0]),'world_y':float(world[1]),'world_z':float(world[2]),
                            'Twc':json.dumps(twc.tolist(),separators=(',',':'))})
    fields=['frame_id','source_frame_index','timestamp','keyframe_id','point_id','u','v','map_depth','world_x','world_y','world_z','Twc']
    table(out/'map_observations.csv',records,fields)
    return len(records)

def quiesce(slam):
    # Let local mapping finish queued frames before stopping its producer/consumer.
    lm=slam.local_mapping; deadline=time.monotonic()+120
    while lm.queue_size() or not lm.is_idle():
        if time.monotonic()>deadline: raise RuntimeError('Local mapping did not drain within 120s; export refused')
        time.sleep(.05)
    lc=slam.loop_closing
    if lc is not None:
        while lc.is_closing() or lc.GBA.is_running():
            if time.monotonic()>deadline: raise RuntimeError('Loop closing/GBA did not settle; export refused')
            time.sleep(.05)
    slam.quit()
    for obj in [lm,lc]:
        if obj is not None:
            thread=getattr(obj,'work_thread',None)
            if thread is not None and thread.is_alive(): raise RuntimeError('Backend thread still alive; export refused')
    thread=getattr(lm,'thread_large_BA',None)
    if thread is not None and thread.is_alive():
        thread.join(timeout=30)
        if thread.is_alive(): raise RuntimeError('Large BA still alive; export refused')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--spec',required=True); a=ap.parse_args(); s=read(a.spec)
    from part3_adapter import configure
    configure(s.get("selected"),ROOT/s["depth_path"] if s.get("depth_path") else None,ROOT/s["out"],s["policy"],s.get("png_factor",5000.))
    from pyslam.config import Config
    from pyslam.slam import PinholeCamera
    from pyslam.slam.slam import Slam, SlamState
    from pyslam.local_features.feature_tracker_configs import FeatureTrackerConfigs
    from pyslam.loop_closing.loop_detector_configs import LoopDetectorConfigs
    from pyslam.io.dataset_types import SensorType,DatasetEnvironmentType
    from pyslam.config_parameters import Parameters
    prep=ROOT/s['prepare']; out=ROOT/s['out']; out.mkdir(parents=True,exist_ok=True)
    config=Config(config_path=str(out/'slam_config.yaml'))
    camera=PinholeCamera(config)
    Parameters.kLogsFolder=str(out/'backend_logs')
    Parameters.kDoVolumetricIntegration=False
    Parameters.kUseDepthEstimatorInFrontEnd=False
    ft=copy.deepcopy(FeatureTrackerConfigs.ORB2); ft['num_features']=2000
    selected=bool(s.get('selected'))
    ismono=s['method']=='mono' or selected
    frame_rows=rows(prep/'frames.csv'); frame_rows=frame_rows[:s['max_frames']] if s.get('max_frames') else frame_rows
    runtime=None
    if selected:
        from pyslam.depth_estimation import part4_policy,pred_depth
        runtime=part4_policy.Runtime(s['selected']['parameters'],frame_rows,s['policy'],out,s.get('temporal',{}))
        part4_policy.runtime=runtime
    slam=Slam(camera,ft,LoopDetectorConfigs.DBOW3,None,SensorType.MONOCULAR if ismono else SensorType.RGBD,
              environment_type=DatasetEnvironmentType.OUTDOOR if s.get("environment")=="outdoor" else DatasetEnvironmentType.INDOOR,config=config,headless=True)
    timings=[]; start=time.perf_counter(); previous_t=None; previous_start=None; used=0
    try:
        with (out/'frame_status.csv').open('w',newline='') as f:
            fields=['frame_id','timestamp','state','tracking_ms','input_ms','depth_used','initialisation_fallback']; writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader()
            for row in frame_rows:
                frame=int(row['frame_id']); timestamp=float(row['timestamp'])
                delay=playback_delay(previous_start,previous_t,timestamp,s['playback_speed'],time.perf_counter())
                if delay: time.sleep(delay)
                previous_start=time.perf_counter(); previous_t=timestamp
                t=time.perf_counter(); img=cv2.imread(str(prep/row['image']))
                if img is None: raise ValueError('RGB decoding failed')
                depth=None; fallback=False
                if not ismono:
                    fallback=slam.tracking.state!=SlamState.OK
                    take=s['policy']=='every' or frame%5==0 or fallback
                    if take:
                        depth=cv2.imread(str(ROOT/s['depth_path']/'png'/f'{frame:06d}.png'),cv2.IMREAD_UNCHANGED)
                        if depth is None or depth.shape!=img.shape[:2] or depth.dtype!=np.uint16: raise ValueError('Missing/invalid cached depth')
                        used+=1
                if runtime is not None:
                    fallback=slam.tracking.state!=SlamState.OK
                    runtime.before_frame(frame,timestamp,fallback)
                    if s['policy']=='every': pred_depth.depth(timestamp)

                input_ms=(time.perf_counter()-t)*1000
                t=time.perf_counter(); slam.track(img,None,depth,frame,timestamp)
                tracking_ms=(time.perf_counter()-t)*1000

                rec={'frame_id':frame,'timestamp':timestamp,'state':slam.tracking.state.name,'tracking_ms':tracking_ms,
                     'input_ms':input_ms,'depth_used':depth is not None,'initialisation_fallback':fallback}
                writer.writerow(rec); f.flush(); timings.append(rec)
        quiesce(slam)
        poses,timestamps,ids=slam.get_final_trajectory()
        # Empty trajectory is a genuine failed run; preserve an empty file plus explicit status.
        write_tum(out/'trajectory.tum',timestamps,poses)
        obs=export_observations(slam,out,frame_rows)
        runtime_report=runtime.finish() if runtime else None
        if runtime_report:
            runtime_report['initialization_events']=pred_depth.part4_initializations
            dump(out/'part3_runtime.json',runtime_report)
        if runtime_report: used=runtime_report['unique_depth_requests']
        dump(out/'run.json',{'status':'complete' if poses else 'failed','failure_reason':None if poses else 'SLAM did not initialise',
                            'frames':len(frame_rows),'trajectory_poses':len(poses),'map_observations':obs,'inference_calls_if_deployed':used,
                            'cached_depth':not ismono or selected,'part3_runtime':runtime_report,
                            'selected_method':s.get('selected'),'temporal_consistency':s.get('temporal'),'elapsed_s':time.perf_counter()-start,
                            'mean_tracking_ms':float(np.mean([r['tracking_ms'] for r in timings])),
                            'backend_quiescent':True,'reference_inputs':False,'policy':s['policy'],
                            'scale_semantics':s['selected']['metric_scale_semantics'] if selected else 'arbitrary map units' if ismono else 'metric network depth; scale bias remains'})
    finally:
        slam.quit()

if __name__=='__main__': main()
