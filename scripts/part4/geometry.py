"""Coordinate conventions and trajectory scoring, independent of SLAM internals."""
import itertools
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.optimize import least_squares
from common import atomic

def colmap_pose(qwxyz, t):
    q = np.asarray(qwxyz, float)
    if abs(np.linalg.norm(q)-1) > 1e-3:
        raise ValueError('Non-unit COLMAP quaternion')
    rcw = Rotation.from_quat(q[[1,2,3,0]]).as_matrix()
    twc = np.eye(4)
    twc[:3,:3] = rcw.T
    twc[:3,3] = -rcw.T @ np.asarray(t, float)
    return twc

def read_tum(path):
    data = np.array([[float(v) for v in l.split()] for l in Path(path).read_text().splitlines() if l.strip() and not l.lstrip().startswith('#')])
    if data.size == 0:
        raise ValueError(f'Empty trajectory: {path}')
    if data.ndim != 2 or data.shape[1] != 8 or not np.isfinite(data).all() or np.any(np.diff(data[:,0]) <= 0):
        raise ValueError('TUM must have eight finite columns and increasing timestamps')
    if np.max(np.abs(np.linalg.norm(data[:,4:], axis=1)-1)) > 1e-3:
        raise ValueError('TUM quaternion not unit length')
    return data

def write_tum(path, timestamps, poses):
    data = []
    for t,p in zip(timestamps, poses):
        r = p[:3,:3]
        if not np.allclose(r.T@r, np.eye(3), atol=1e-5) or np.linalg.det(r)<0:
            raise ValueError('Invalid rotation')
        data.append([t, *p[:3,3], *Rotation.from_matrix(r).as_quat()])
    atomic(path, ''.join(' '.join(f'{v:.10f}' for v in row)+'\n' for row in data))

def match_times(a,b,tolerance):
    candidates=[]
    for i,t in enumerate(a):
        j=int(np.searchsorted(b,t))
        for k in (j-1,j):
            if 0<=k<len(b) and abs(b[k]-t)<=tolerance:
                candidates.append((abs(b[k]-t),i,k))
    useda,usedb=set(),set()
    pairs=[]
    for _,i,j in sorted(candidates):
        if i not in useda and j not in usedb:
            pairs.append((i,j)); useda.add(i); usedb.add(j)
    return np.asarray(sorted(pairs),int).reshape(-1,2)

def align(x,y,scale):
    if len(x)<3:
        raise ValueError('Need at least three matched poses')
    xc,yc=x-x.mean(0),y-y.mean(0)
    if np.linalg.matrix_rank(xc,tol=1e-9)<2:
        raise ValueError('Trajectory alignment is degenerate (stationary/collinear)')
    u,s,vt=np.linalg.svd(yc.T@xc/len(x))
    d=np.diag([1.,1.,np.linalg.det(u@vt)])
    r=u@d@vt
    k=float(np.sum(s*np.diag(d))/np.mean(np.sum(xc*xc,axis=1))) if scale else 1.
    t=y.mean(0)-k*r@x.mean(0)
    return k,r,t

def trajectory_metrics(est,ref,tolerance=.025,interval=1.,pair_tolerance=.12,max_gap=.25):
    pairs=match_times(est[:,0],ref[:,0],tolerance)
    if len(pairs)<3:
        raise ValueError('Insufficient timestamp matches')
    e,g=est[pairs[:,0]],ref[pairs[:,1]]
    x,y=e[:,1:4],g[:,1:4]
    k,r,t=align(x,y,True)
    _,rr,tr=align(x,y,False)
    sim=np.linalg.norm((k*(r@x.T)).T+t-y,axis=1)
    rigid=np.linalg.norm((rr@x.T).T+tr-y,axis=1)
    er=Rotation.from_quat(e[:,4:]).as_matrix()
    gr=Rotation.from_quat(g[:,4:]).as_matrix()
    gaps=np.maximum(np.diff(e[:,0]), np.diff(g[:,0]))>max_gap
    rp=[]
    for i,ti in enumerate(e[:,0]):
        j=int(np.searchsorted(e[:,0],ti+interval))
        opts=[v for v in (j-1,j) if i<v<len(e)]
        if not opts: continue
        j=min(opts,key=lambda z:abs(e[z,0]-ti-interval))
        if abs(e[j,0]-ti-interval)>pair_tolerance or gaps[i:j].any(): continue
        de=er[i].T@(x[j]-x[i]); dg=gr[i].T@(y[j]-y[i])
        rp.append({'i':i,'j':j,'interval_s':float(e[j,0]-ti),
                   'scaled_error_m':float(np.linalg.norm(k*de-dg)), 'rigid_error_m':float(np.linalg.norm(de-dg))})
    rmse=lambda a:float(np.sqrt(np.mean(np.square(a))))
    result={'ate_unscaled_m':rmse(rigid),'ate_scaled_m':rmse(sim),'fitted_scale':k,
            'rpe_rmse_m':rmse([p['scaled_error_m'] for p in rp]) if rp else None,
            'rpe_rigid_rmse_m':rmse([p['rigid_error_m'] for p in rp]) if rp else None,
            'rpe_pairs':len(rp),'matched_poses':len(pairs),'reference_coverage':len(pairs)/len(ref),
            'rpe_unavailable_reason':None if rp else 'No valid interval pairs without tracking/reference gaps',
            'rpe_scale_convention':'one global fitted Sim(3) scale; orientations remain in local camera axes',
            'timestamp_tolerance_s':tolerance,'max_gap_s':max_gap}
    matched=[{'timestamp':float(e[i,0]),'reference_timestamp':float(g[i,0]),'rigid_error_m':float(rigid[i]),'scaled_error_m':float(sim[i])} for i in range(len(e))]
    return result,matched,rp

def rotate_intrinsics(k,w,h,clockwise):
    k=np.array(k,float).copy()
    if clockwise==0: return k,(w,h)
    fx,fy,cx,cy=k[0,0],k[1,1],k[0,2],k[1,2]
    if clockwise==90: vals=(fy,fx,h-1-cy,cx); size=(h,w)
    elif clockwise==180: vals=(fx,fy,w-1-cx,h-1-cy); size=(w,h)
    elif clockwise==270: vals=(fy,fx,cy,w-1-cx); size=(h,w)
    else: raise ValueError('Only multiples of 90 degrees supported')
    fx,fy,cx,cy=vals
    return np.array([[fx,0,cx],[0,fy,cy],[0,0,1.]]),size

def resize_intrinsics(k,old_size,new_size):
    sx,sy=np.asarray(new_size,float)/np.asarray(old_size,float)
    out=np.array(k,float).copy(); out[0]*=sx; out[1]*=sy
    out[0,2]=(k[0,2]+.5)*sx-.5; out[1,2]=(k[1,2]+.5)*sy-.5
    return out

def triangulate(uv,poses,k,min_angle=1.,max_residual=4.):
    uv=np.asarray(uv,float); poses=np.asarray(poses,float)
    if len(uv)<3: raise ValueError('Need at least three views per endpoint')
    if uv.shape!=(len(poses),2) or not np.isfinite(uv).all() or not np.isfinite(poses).all():
        raise ValueError('Marker pixels/poses must be finite and paired')
    # Canonical ordering makes deterministic sampling independent of annotation order.
    signature=np.c_[poses[:,:3,3],poses[:,:3,:3].reshape(len(poses),-1),uv]
    order=np.lexsort(signature[:,::-1].T); inverse=np.argsort(order)
    uv=uv[order]; poses=poses[order]
    rays=np.array([p[:3,:3]@np.linalg.solve(k,[*u,1]) for u,p in zip(uv,poses)])
    rays/=np.linalg.norm(rays,axis=1)[:,None]
    centers=poses[:,:3,3]
    angle=float(np.degrees(np.arccos(np.clip(rays@rays.T,-1,1))).max())
    if angle<min_angle: raise ValueError(f'Degenerate rays: maximum angle {angle:.3f} degrees')
    def fit(ids):
        a=np.array([np.eye(3)-np.outer(rays[i],rays[i]) for i in ids])
        return np.linalg.lstsq(a.reshape(-1,3),np.einsum('nij,nj->ni',a,centers[ids]).reshape(-1),rcond=None)[0]
    def residuals(x):
        pc=np.array([p[:3,:3].T@(x-p[:3,3]) for p in poses]); q=(k@pc.T).T
        den=np.where(abs(q[:,2:])<1e-10,1e-10,q[:,2:])
        return q[:,:2]/den-uv,pc[:,2]
    def errors(x):
        residual,z=residuals(x)
        return np.linalg.norm(residual,axis=1),z
    def ray_angle(ids):
        a,b=np.triu_indices(len(ids),1)
        if not len(a): return 0.
        return float(np.degrees(np.arccos(np.clip(np.sum(rays[ids[a]]*rays[ids[b]],axis=1),-1,1))).max())
    best=None
    n=len(uv); total=n*(n-1)*(n-2)//6
    if total<=512: subsets=list(itertools.combinations(range(n),3))
    else:
        rng=np.random.default_rng(20261112); chosen=set()
        while len(chosen)<512: chosen.add(tuple(sorted(rng.choice(n,3,replace=False).tolist())))
        subsets=sorted(chosen)
    for subset in subsets:
        if ray_angle(np.array(subset))<min_angle: continue
        x=fit(list(subset)); err,z=errors(x); keep=(err<=max_residual)&(z>0)
        score=(int(keep.sum()),-float(np.minimum(err,max_residual).sum()))
        if best is None or score>best[0]: best=(score,x,keep)
    if best is None: raise ValueError('No nondegenerate marker hypothesis')
    x,keep=best[1:]
    if keep.sum()<3: raise ValueError('Fewer than three consistent positive-depth marker views')
    # Minimise actual image reprojection error; linear ray fitting is only an initializer.
    # Reclassify inliers after every refinement instead of validating a stale mask.
    for _ in range(12):
        ids=np.flatnonzero(keep)
        opt=least_squares(lambda p:residuals(p)[0][ids].ravel(),x,loss='soft_l1',f_scale=1.,max_nfev=120)
        x=opt.x; err,z=errors(x); updated=(err<=max_residual)&(z>0)
        if updated.sum()<3: raise ValueError('Refined marker has fewer than three valid views')
        if np.array_equal(updated,keep): break
        keep=updated
    else: raise ValueError('Marker inlier refinement did not stabilise')
    accepted_angle=ray_angle(np.flatnonzero(keep))
    if accepted_angle<min_angle: raise ValueError('Inlier marker rays are degenerate')
    if np.any(z[keep]<=0) or np.max(err[keep])>max_residual: raise ValueError('Marker fit failed validation')
    covariance=np.linalg.pinv(opt.jac.T@opt.jac)
    return x,{'ray_angle_deg':accepted_angle,'residual_px':err[inverse].tolist(),'positive_depth':(z[inverse]>0).tolist(),
              'inliers':keep[inverse].tolist(),'hypotheses_tested':len(subsets),'fit':'deterministic order-invariant sampling and robust reprojection refinement',
              'covariance_for_1px_noise':covariance.tolist(),
              'uncertainty_limit':'Conditional on fixed reference poses; adjacent-frame and pose/calibration errors are not independent'}

def encode_depth(d,factor):
    if factor<=0: raise ValueError('Depth factor must be positive')
    valid=np.isfinite(d)&(d>0)
    raw=np.zeros(d.shape,np.uint16)
    raw[valid]=np.clip(np.rint(d[valid]*factor),1,65535).astype(np.uint16)
    return raw,{'invalid_pixels':int((~valid).sum()),'clipped_pixels':int((valid&(d*factor>65535)).sum()),'max_representable_m':65535/factor}
