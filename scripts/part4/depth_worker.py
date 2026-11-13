"""Isolated metric DA-V2 inference worker; raw float metres plus PNG for pySLAM."""
import sys
from pathlib import Path
from common import ROOT, SLAM
sys.path.insert(0,str(SLAM))
import pyslam  # OpenMP setup before torch/numpy
import argparse
import time
import cv2
import numpy as np
import torch
from common import ROOT, SLAM, atomic, digest, dump, read, rows, table
from geometry import encode_depth

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--spec',required=True); a=ap.parse_args()
    s=read(a.spec); prep=ROOT/s['prepare']; out=ROOT/s['out']; c=s['depth']
    torch.set_num_threads(4)
    from pyslam.depth_estimation.depth_estimator_depth_anything_v2 import DepthEstimatorDepthAnythingV2
    from pyslam.io.dataset_types import DatasetEnvironmentType
    device=torch.device(c['device'])
    if device.type not in ('cpu','mps'): raise ValueError('Use cpu or tested mps')
    network=DepthEstimatorDepthAnythingV2(device=device,max_depth=80 if c['scene']=='outdoor' else 20,dataset_env_type=DatasetEnvironmentType.OUTDOOR if c['scene']=='outdoor' else DatasetEnvironmentType.INDOOR,encoder_name='vitb')
    frames=rows(prep/'frames.csv'); frames=frames[:s['max_frames']] if s.get('max_frames') else frames
    for name in ['raw_m','png']: (out/name).mkdir(parents=True,exist_ok=True)
    records=[]; start=time.perf_counter()
    def sync():
        if device.type=='mps': torch.mps.synchronize()
    for i,r in enumerate(frames):
        stem=Path(r['image']).stem; raw=out/'raw_m'/f'{stem}.npy'; png=out/'png'/f'{stem}.png'; meta=out/'raw_m'/f'{stem}.json'
        if raw.exists() and png.exists() and meta.exists():
            saved=read(meta)
            if digest(raw)==saved['raw_sha256'] and digest(png)==saved['png_sha256']:
                records.append(saved); continue
        img=cv2.imread(str(prep/r['image']))
        if img is None: raise ValueError(f'Cannot read {r["image"]}')
        sync(); t=time.perf_counter()
        with torch.inference_mode():
            tensor,shape=network.model.image2tensor(img,c['input_size'])
            tensor=tensor.to(device)
            result=network.model(tensor)
            d=torch.nn.functional.interpolate(result[:,None],shape,mode='bilinear',align_corners=True)[0,0].cpu().numpy()
        sync(); elapsed=(time.perf_counter()-t)*1000
        d=np.asarray(d,np.float32)
        if d.shape!=img.shape[:2]: raise ValueError('Prediction/image shape mismatch')
        encoded,quality=encode_depth(d,c['png_factor'])
        temp=raw.with_suffix('.tmp')
        with temp.open('wb') as f: np.save(f,d)
        temp.replace(raw)
        if not cv2.imwrite(str(png),encoded): raise RuntimeError('Depth PNG write failed')
        rec={'frame_id':int(r['frame_id']),'timestamp':float(r['timestamp']),'inference_ms':elapsed,
             'raw_sha256':digest(raw),'png_sha256':digest(png),**quality}
        dump(meta,rec); records.append(rec)
        if (i+1)%20==0: print(f'depth {i+1}/{len(frames)}: {elapsed:.0f} ms',flush=True)
    # No measured-depth file is created. Predicted associations explicitly name their source.
    atomic(out/'associations_dav2b.txt',''.join(f'{r["timestamp"]} {prep.relative_to(ROOT)/r["image"]} {r["timestamp"]} {out.relative_to(ROOT)/"png"/(Path(r["image"]).stem+".png")}\n' for r in frames))
    weights=SLAM/('thirdparty/depth_anything_v2/metric_depth/checkpoints/depth_anything_v2_metric_'+('vkitti' if c['scene']=='outdoor' else 'hypersim')+'_vitb.pth')
    table(out/'timing.csv',records)
    dump(out/'info.json',{'model':c,'weights_sha256':digest(weights),'units':'raw float32 optical depth metres; PNG = metres * factor once',
                          'frames':len(records),'elapsed_s':time.perf_counter()-start,'device':str(device),
                          'mean_inference_ms':float(np.mean([r['inference_ms'] for r in records])),
                          'cache':'raw model predictions reused by all compared methods; warm/cold first frame retained'})

if __name__=='__main__': main()
