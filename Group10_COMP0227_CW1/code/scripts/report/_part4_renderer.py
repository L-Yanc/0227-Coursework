#!/usr/bin/env python3
"""Generate ONLY the three Part 4 report inserts: one table and two figures.
Run: python3 scripts/report/part4.py --out /external/report_assets
No SLAM, inference, reconstruction, or experimental reruns are performed.
"""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import statistics as st
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[4]/'_assembly/report_assets/part4')
args = parser.parse_args()
REPO = args.repo.resolve()
CW = REPO.parent
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
except ImportError:
    raise SystemExit('Install requirements-analysis.txt in your chosen Python environment.')

METHODS = {
 'mono': 'Mono', 'pseudo_rgbd': 'Pseudo RGB-D',
 'pseudo_rgbd_stride5': 'Pseudo RGB-D, stride 5',
 'selected': 'B80+E1, every frame', 'selected_keyframes': 'B80+E1, keyframes',
 'selected_stride5': 'B80+E1, stride 5',
 'selected_temporal_keyframes': 'B80+E1, temporal + keyframes'}
SEQS = {'tum_fr3': 'TUM fr3', 'replica_room0': 'Replica room0',
        'kitti06': 'KITTI 06', 'own': 'Own room'}

def read_csv(p):
    with p.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def main():
    work = REPO / 'inputs/part4'
    out = args.out.resolve()
    rows = read_csv(REPO / 'inputs/part4.csv')
    assert len(rows) == 140 and len({r['run_id'] for r in rows}) == 140
    groups = {}
    for r in rows:
        assert r['sequence'] in SEQS and r['method'] in METHODS
        assert math.isfinite(float(r['ate_scaled_m']))
        groups.setdefault((r['sequence'], r['method']), []).append(r)
    assert len(groups) == 28 and all(len(v) == 5 for v in groups.values())
    out.mkdir(exist_ok=True, parents=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,
                         'axes.spines.top':False,'axes.spines.right':False})

    lines = [r'\begin{table*}[t]',r'\centering',
      r'\caption{Part 4 scale-corrected ATE RMSE in metres (mean $\pm$ sample SD, five runs per configuration; all runs included). The own-room trajectory is evaluated against an approximate COLMAP reference. These fresh DAV2-base batches have matched monocular baselines and are separate from the historical Part 3 experiments.}',
      r'\label{tab:p4}',r'\scriptsize',r'\setlength{\tabcolsep}{5pt}',
      r'\begin{tabular}{lcccc}',r'\toprule',
      r'Method & TUM fr3 & Replica room0 & KITTI 06 & Own room \\',r'\midrule']
    for i,m in enumerate(METHODS):
        if i in [1,3]: lines.append(r'\midrule')
        cells=[]
        for s in SEQS:
            v=[float(r['ate_scaled_m']) for r in groups[s,m]]
            d=2 if s=='kitti06' else 4 if s=='replica_room0' else 3
            cells.append(f'${st.mean(v):.{d}f} \\pm {st.stdev(v):.{d}f}$')
        lines.append(METHODS[m]+' & '+' & '.join(cells)+r' \\')
    lines += [r'\bottomrule',r'\end{tabular}',r'\end{table*}']
    (out/'part4_results.tex').write_text('\n'.join(lines)+'\n')

    # Use all five TUM mono runs. Aggregate within persistent point in the saved
    # breakdown, then show mean and sample SD of the five run-level medians.
    panels=[('parallax_max_deg',['0-1','1-3','3-10','10-1e+09'],
             ['<1','1--3','3--10','>10'],'Maximum parallax (degrees)'),
            ('learned_z_m',['0-1','1-2','2-3','3-5'],
             ['<1','1--2','2--3','3--5'],'Predicted depth (m)'),
            ('normalised_radius',['0-0.5','0.5-1','1-2'],
             ['0--0.5','0.5--1','1--2'],'Normalised image radius')]
    runs=[]
    for r in groups['tum_fr3','mono']:
        key=r['run_id'].split('_')[-1]
        runs.append(read_csv(work/'tum_fr3/analysis'/key/'breakdown.csv'))
    fig,axes=plt.subplots(1,3,figsize=(7.15,2.25))
    for ax,(dim,bins,labels,xlabel) in zip(axes,panels):
        vals=[]
        for bn in bins:
            v=[]
            for run in runs:
                match=[x for x in run if x['dimension']==dim and x['bin']==bn and x['metric']=='disagreement_m']
                assert len(match)==1 and int(match[0]['n'])>0
                v.append(float(match[0]['median']))
            vals.append(v)
        ax.errorbar(range(len(bins)),[st.mean(v) for v in vals],
                    yerr=[st.stdev(v) for v in vals],fmt='o-',capsize=3,color='#2166ac')
        ax.set_xticks(range(len(bins)),labels);ax.set_xlabel(xlabel)
        ax.set_ylim(bottom=0);ax.grid(axis='y',alpha=.2)
    axes[0].set_ylabel('Depth disagreement (m)')
    fig.tight_layout(pad=.6)
    fig.savefig(out/'part4_agreement.png',dpi=300,bbox_inches='tight');plt.close(fig)
    agreement_caption=(r'TUM monocular maps: mean $\pm$ sample SD of the five run-level median absolute map/network depth disagreements, grouped by parallax, predicted depth and normalised image radius. Saved bin summaries aggregate repeated observations within map points. The distance panel shows predicted-depth bins below 5 m; radius bins follow the exported normalised-radius definition. Monocular map scale is estimated from network correspondences, so agreement does not establish independent metric accuracy.')

    # Exact saved failure candidate and baseline, without reselecting a favourable run.
    ev=work/'own'
    trace=json.load((ev/'failure_trace.json').open())
    image=plt.imread(Path(__file__).resolve().parent/'inputs/part4_failure_candidate.png')
    fig=plt.figure(figsize=(7.15,4.05))
    gs=fig.add_gridspec(2,1,height_ratios=[1.3,1],hspace=.28)
    ax=fig.add_subplot(gs[0]);ax.imshow(image);ax.axis('off')
    ax=fig.add_subplot(gs[1])
    for field,label,color in [('baseline_run','Mono representative run','#2166ac'),
                              ('learned_run','B80+E1 stride 5, repetition 5','#b2182b')]:
        data=read_csv(ev/'matched'/(trace[field]+'.csv'))
        ts=[float(r['reference_timestamp']) for r in data]
        errors=[float(r['scaled_error_m']) for r in data]
        # Break line at missing intervals instead of suggesting continuous tracking.
        xx=[];yy=[]
        for i,(t,e) in enumerate(zip(ts,errors)):
            if i and t-ts[i-1]>.25:xx.append(float('nan'));yy.append(float('nan'))
            xx.append(t);yy.append(e)
        ax.plot(xx,yy,label=label,color=color,linewidth=1)
    ax.axvline(trace['timestamp'],color='black',linestyle='--',linewidth=.8)
    ax.set_xlabel('Recording time (s)');ax.set_ylabel('Aligned position error (m)')
    ax.legend(fontsize=8,loc='upper left');ax.grid(alpha=.2)
    fig.savefig(out/'part4_failure.png',dpi=300,bbox_inches='tight');plt.close(fig)
    failure_caption=(r'Own-room failure candidate: RGB and network optical depth at 63.11 s (top), and position-error traces after separate global Sim(3) alignments (bottom). B80+E1 stride-five repetition 5 had 1.307 m ATE; its local error exceeded the selected monocular run by approximately 2.53 m at the marked time. Gaps above 0.25 s break the curves. This identifies an association, not a proven depth-error cause; no new depth was requested at the marked timestamp.')

    for stem,caption,label in [('part4_agreement',agreement_caption,'fig:p4-agreement'),
                               ('part4_failure',failure_caption,'fig:p4-failure')]:
        (out/(stem+'.tex')).write_text('\n'.join([r'\begin{figure*}[t]',r'\centering',
          r'\includegraphics[width=\textwidth]{'+stem+'.png}',
          r'\caption{'+caption+'}',r'\label{'+label+'}',r'\end{figure*}','']))
    (out/'README.md').write_text('''# Exactly three report inserts

Generated from saved final results; no experiments are rerun.

1. **After Experimental Setup:** copy `part4_results.tex`. This is the ONLY results table to insert in Part 4. It contains all four sequences and seven configurations, mean +/- sample SD, five runs each.
2. **At the agreement figure marker, after Triangulated and Learned Depth:** upload `part4_agreement.png` to the LaTeX project and copy `part4_agreement.tex` at that marker.
3. **At the failure figure marker in Failure Analysis and Interpretation:** upload `part4_failure.png` and copy `part4_failure.tex` at that marker. The image now includes both RGB/depth and the actual error curves.

Upload PNGs to the same folder as the report main .tex, or adjust the includegraphics paths. The preamble needs `\\usepackage{booktabs}` and `\\usepackage{graphicx}`. Both figure snippets use figure* across the two columns; LaTeX may place them at the next page top. The table is labelled tab:p4, figures fig:p4-agreement and fig:p4-failure.

Do not insert any old supplementary tables. This folder is the complete set of generated Part 4 visuals intended for the report. It contains one table, two PNGs, their two LaTeX snippets, and this guide.

Regenerate from the repository root:

    python3 scripts/report/part4.py --out /external/report_assets

The agreement plot uses TUM mono, five runs; error bars are run-level sample SD. It does not claim that network-aligned map units validate metric accuracy. Failure curves use the saved candidate and saved baseline, not reselected runs. No claim of proven causation is made.
''')
    print('Validated 140 unique runs / 28 groups / 5 repeats each.')
    print('Generated ONLY report inserts in: '+str(out))
    for p in sorted(out.iterdir()): print(p.name)

if __name__=='__main__': main()
