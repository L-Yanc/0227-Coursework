"""Render older DAV2-large exploratory results; not the draft base-model tables."""
import argparse,csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--inputs',type=Path,default=Path(__file__).resolve().parents[2]/'inputs/part2_depth')
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
summary=[]
fig,axes=plt.subplots(1,2,figsize=(10,3))
for seq in ['fr3','room0','kitti']:
 rows=list(csv.DictReader((a.inputs/('scores_'+seq+'.csv')).open()))
 for key in rows[0]:
  try:values=np.array([float(r[key]) for r in rows])
  except ValueError:continue
  summary.append([seq,key,len(values),np.mean(values),np.median(values),np.min(values),np.max(values)])
 if seq!='kitti':
  ax=axes[0 if seq=='fr3' else 1]
  ax.plot([float(r['frame']) for r in rows],[float(r['median_scale']) for r in rows],lw=.8)
  ax.set_title(seq);ax.set_xlabel('Frame');ax.set_ylabel('True / predicted median depth')
fig.tight_layout();fig.savefig(a.out/'part2_stability.png',dpi=160);plt.close(fig)
with (a.out/'depth_summary.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['sequence','metric','frames','mean','median','min','max']);w.writerows(summary)
def spearman(x,y):
 return np.corrcoef(np.argsort(np.argsort(x)),np.argsort(np.argsort(y)))[0,1]
with (a.out/'uncertainty_summary.csv').open('w',newline='') as f:
 writer=csv.writer(f);writer.writerow(['sequence','proxy','rank_corr_abs','rank_corr_rel','relative_error_bin1','bin2','bin3','bin4','bin5'])
 for seq in ['fr3','room0']:
  d=np.load(a.inputs/('sigma_'+seq+'_keypoints.npz'))
  zp,zt,s,grad=[d[k] for k in ['d_pred','d_true','scale','grad']]
  err_abs=np.abs(s*zp-zt);err_rel=err_abs/zt;eps=np.median(err_rel)
  cands={'fixed eps*d':eps*s*zp,'gradient':grad*s,'gradient/d':grad/zp}
  fig,axes=plt.subplots(1,3,figsize=(15,4))
  for ax,(name,sig) in zip(axes,cands.items()):
   edges=np.quantile(sig,np.linspace(0,1,6))
   b=np.clip(np.searchsorted(edges,sig,side='right')-1,0,4)
   med=[np.median(err_rel[b==k]) for k in range(5)]
   writer.writerow([seq,name,spearman(sig,err_abs),spearman(sig,err_rel),*med])
   sub=np.random.default_rng(0).choice(len(sig),min(5000,len(sig)),replace=False)
   ax.scatter(sig[sub],err_abs[sub],s=2,alpha=.3)
   ax.plot([np.median(sig[b==k]) for k in range(5)],[np.median(err_abs[b==k]) for k in range(5)],'r-o',label='median per bin')
   ax.set_xscale('log');ax.set_yscale('log');ax.set_xlabel('sigma_d: '+name);ax.set_ylabel('actual error (m, scale fixed)');ax.legend()
  fig.tight_layout();fig.savefig(a.out/('sigma_'+seq+'.png'),dpi=120);plt.close(fig)
print('Generated Part 2 depth/uncertainty CSV summaries, stability and two sigma figures.')
