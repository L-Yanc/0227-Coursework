"""Render report Tables I-V from original saved score exports."""
import csv,json,statistics as st
from pathlib import Path
def rows(path):
    with path.open(newline='') as f:return list(csv.DictReader(f))
def wrap(path,caption,headers,body,wide=False):
    env='table*' if wide else 'table'
    text=['\\begin{'+env+'}[t]','\\centering','\\caption{'+caption+'}','\\scriptsize',
          '\\resizebox{'+('\\textwidth' if wide else '\\columnwidth')+'}{!}{%',
          '\\begin{tabular}{l'+'r'*(len(headers)-1)+'}','\\toprule',
          ' & '.join(headers)+r' \\','\\midrule']
    text+=[' & '.join(row)+r' \\' for row in body]
    text+=['\\bottomrule','\\end{tabular}','}','\\end{'+env+'}']
    path.write_text('\n'.join(text)+'\n')
def part1(code,out):
    p1=rows(code/'inputs/part1.csv')
    def group(seq,mode,backend):
        found=[r for r in p1 if r['sequence']==seq and r['method']==mode and ('backend='+backend+';') in r['settings']]
        assert len(found)==5,(seq,mode,backend,len(found))
        return found
    order=[('KITTI 06','monocular','cpp','KITTI M/C++'),('KITTI 06','monocular','python','KITTI M/Py'),
           ('fr3','monocular','cpp','fr3 M/C++'),('fr3','rgbd','cpp','fr3 D/C++'),
           ('room0','monocular','cpp','room0 M/C++'),('room0','rgbd','cpp','room0 D/C++')]
    def values(rs,key):return [float(r[key]) for r in rs if r[key]!='']
    def mean(rs,key,n):return f'{st.mean(values(rs,key)):.{n}f}'
    def pm(rs,key,n):
        v=values(rs,key)
        return '--' if not v else '$'+f'{st.mean(v):.{n}f}\\pm{st.stdev(v):.{n}f}'+'$'
    one=[];two=[]
    for index,(seq,mode,backend,label) in enumerate(order):
        rs=group(seq,mode,backend)
        rigid,scaled,scale=[(2,2,2),(2,2,2),(3,4,2),(4,4,3),(3,5,2),(5,5,3)][index]
        one.append([label,pm(rs,'ate_unscaled_m',rigid),pm(rs,'ate_scaled_m',scaled),mean(rs,'fitted_scale',scale)])
        rpe=3 if seq=='KITTI 06' else 4 if seq=='fr3' else 5
        two.append([label,pm(rs,'rpe_rmse_m',rpe),f"{100*st.mean(values(rs,'fraction_tracked')):.2f}",
                    pm(rs,'time_per_frame_ms',2),pm(rs,'map_depth_mae_m',4)])
    wrap(out/'table1.tex','Baseline trajectory error (mean and sample SD, five runs).',
         ['Sequence / mode','Rigid ATE (m)','Sim(3) ATE (m)','Scale'],one)
    wrap(out/'table2.tex','Tracking and map quality (mean and sample SD, five runs).',
         ['Sequence / mode','RPE (m)','Tracked (\\%)','Time (ms)','Map MAE (m)'],two)

def part2(code,out):
    inputs=code/'inputs/part2_report'
    def data(name):return json.loads((inputs/name).read_text())
    three=[]
    for folder,label in [('tum','TUM fr3'),('replica','Replica room0')]:
        d=data(folder+'_dav2b/summary.json')
        three.append([label,f"{d['raw_all']['absrel']:.2f}",f"{d['raw_all']['delta125']:.2f}",
                      f"{d['scaled_all']['absrel']:.2f}",f"{d['scaled_all']['delta125']:.2f}"])
    wrap(out/'table3.tex','Network depth against sensor depth. Saved evaluation samples every fifth frame: 498 TUM and 400 Replica frames.',
         ['Sequence','Metric AbsRel',r'Metric $\delta<1.25$','Shape AbsRel',r'Shape $\delta<1.25$'],three)
    four=[]
    for folder,label in [('tum_dav2b_uncertainty','TUM / 4 features (TUM)'),
                         ('replica_dav2b_uncertainty_tummodel','Replica / 4 features (TUM)'),
                         ('tum_dav2b_uncertainty_kittimodel','TUM / spread+border (Replica)')]:
        d=data(folder+'/validation.json')['local']
        four.append([label,*[f"{x['error_median']:.3f}" for x in d['bins']],f"{d['spearman']:.2f}",
                     f"{d['absrel_all']:.3f}",f"{d['absrel_drop20_by_sigma']:.3f}",f"{d['absrel_drop20_oracle']:.3f}"])
    wrap(out/'table4.tex','Held-out uncertainty: five error bins, rank correlation and dropping the least certain fifth.',
         ['Test / model','Bin 1','Bin 2','Bin 3','Bin 4','Bin 5','Rank','All','Drop 20\\%','Oracle'],four,True)
    seqs=['tum','replica','kitti'];summaries=[data(s+'_dav2b_scale/summary.json') for s in seqs]
    five=[]
    for label,key,digits in [('Scale fitted to true trajectory','oracle',3),('Scale from predicted depth','global',3),
                             ('Error (\\%)','global_err_pct',1)]:
        five.append([label,*['$'+f"{d[key]['mean']:.{digits}f}\\pm{d[key]['sd']:.{digits}f}"+'$' for d in summaries]])
    drift=[]
    for seq in seqs:
        pairs=[json.loads(r['traj_drift_p10_p90']) for r in rows(inputs/(seq+'_dav2b_scale/runs.csv'))]
        drift.append(f"{min(p[0] for p in pairs):.2f}--{max(p[1] for p in pairs):.2f}")
    five.append(['SLAM scale drift (range of run p10--p90)',*drift])
    wrap(out/'table5.tex','Map scale from predicted depth (mean and run SD; metres = scale times map units).',
         ['Quantity','TUM (5)','Replica (5)','KITTI (3)'],five)
    return {'table3_source_frames':{'TUM':2488,'Replica':2000},'table3_frames_scored':{'TUM':498,'Replica':400},
            'table3_stride':5,'table5_drift_definition':'range across runs of per-run p10/p90'}
