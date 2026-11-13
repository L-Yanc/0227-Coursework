"""Causal Part 4 extension to Part 3 B insertion; no reference/true-depth input.

The untouched Part 3 variant bypasses this gate. Thresholds are fitted only on
past development-interval pair discrepancies and frozen on entry to evaluation.
"""
import json
from pathlib import Path
import numpy as np

class ConsistencyGate:
    def __init__(self, split_time, min_samples=30, min_relative_threshold=.05,
                 mad_multiplier=3.):
        self.split=float(split_time); self.minimum=int(min_samples)
        self.floor=float(min_relative_threshold); self.multiplier=float(mad_multiplier)
        self.samples=[]; self.threshold=None
        self.frozen=False; self.records=[]

    def decide(self,timestamp,discrepancies):
        values=np.asarray(discrepancies,float); valid=np.isfinite(values)&(values>=0)
        development=timestamp<=self.split and not self.frozen
        if development:
            # Development observes without rejecting; later thresholds are frozen.
            self.samples.extend(values[valid].tolist())
            return np.ones(len(values),bool)
        if not self.frozen:
            self.frozen=True
            if len(self.samples)>=self.minimum:
                a=np.asarray(self.samples); med=np.median(a)
                self.threshold=max(self.floor,float(med+self.multiplier*1.4826*np.median(abs(a-med))))
        # Insufficient development evidence means no intervention, explicitly logged.
        return np.ones(len(values),bool) if self.threshold is None else (~valid | (values<=self.threshold))

    def report(self):
        return {'development_end_timestamp':self.split,'development_samples':len(self.samples),
                'frozen':self.frozen,'relative_threshold':self.threshold,
                'status':'active' if self.threshold is not None else 'insufficient_development_evidence',
                'protocol':'Pairwise learned 3D discrepancy in the current online map; first interval trains, later interval uses a frozen median+MAD threshold. Missing pair depth passes unchanged.'}

class Runtime:
    def __init__(self,parameters,frames,policy,out,temporal):
        self.policy=policy; self.out=Path(out); self.allowed={};self.loaded=set();self.delivered=set();self.rows=[]
        self.parameters=parameters
        times=[float(r['timestamp']) for r in frames]
        opts={k:v for k,v in temporal.items() if k not in ('enabled','development_fraction')}
        self.gate=ConsistencyGate(min(times)+(max(times)-min(times))*temporal.get('development_fraction',.5),**opts) if temporal.get('enabled') else None

    def before_frame(self,frame,timestamp,fallback):
        self.allowed[round(timestamp,6)]=self.policy!='stride5' or frame%5==0 or fallback

    def permits(self,timestamp):
        return self.allowed.get(round(float(timestamp),6),False)

    def record_depth(self,timestamp): self.loaded.add(round(float(timestamp),6))

    def filter_candidates(self,pred,kf_cur,kf,idxs_cur,idxs,d_hat,scale,candidates):
        if self.gate is None or not np.any(candidates): return candidates
        t=float(pred.ts_of(kf_cur)); other=pred.depth(pred.ts_of(kf))
        if other is None or scale<=0: return candidates
        ids=np.flatnonzero(candidates)
        z,ok=pred.trusted(other,np.asarray(kf.kps)[np.asarray(idxs)[ids]])
        uv1=np.asarray(kf_cur.kpsn)[np.asarray(idxs_cur)[ids]]
        uv2=np.asarray(kf.kpsn)[np.asarray(idxs)[ids]]
        a=np.c_[uv1,np.ones(len(ids))]*d_hat[ids,None]
        b=np.c_[uv2,np.ones(len(ids))]*z[:,None]
        tw1=np.linalg.inv(np.asarray(kf_cur.pose()));tw2=np.linalg.inv(np.asarray(kf.pose()))
        wa=a@tw1[:3,:3].T+tw1[:3,3]*scale
        wb=b@tw2[:3,:3].T+tw2[:3,3]*scale
        discrepancy=np.linalg.norm(wa-wb,axis=1)/np.maximum((d_hat[ids]+z)/2,1e-6)
        discrepancy[~ok]=np.nan
        keep=self.gate.decide(t,discrepancy); result=candidates.copy(); result[ids]&=keep
        for i,j in enumerate(ids):
            self.rows.append({'timestamp':t,'frame_id':int(kf_cur.img_id),'other_frame_id':int(kf.img_id),
                              'keypoint_index':int(np.asarray(idxs_cur)[j]),'relative_discrepancy':float(discrepancy[i]) if np.isfinite(discrepancy[i]) else None,
                              'kept':bool(keep[i]),'development':t<=self.gate.split,'threshold':self.gate.threshold})
        return result

    def finish(self):
        result={'policy':self.policy,'unique_depth_requests':len(self.loaded),'requested_timestamps':sorted(self.loaded),
                'temporal':self.gate.report() if self.gate else {'status':'disabled'},
                'candidate_checks':len(self.rows),'rejected_candidates':sum(not r['kept'] for r in self.rows),
                'reference_inputs':False,'map_pose_information':'current online poses only; no final BA map used to make decisions'}
        self.out.mkdir(parents=True,exist_ok=True)
        (self.out/'part3_runtime.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        with (self.out/'consistency_decisions.jsonl').open('w') as f:
            for row in self.rows: f.write(json.dumps(row,allow_nan=False)+'\n')
        return result

runtime=None
