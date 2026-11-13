"""Render Part 3 Table VI and Figure 1."""
from _cli import CODE,arguments,run
import shutil
a=arguments(__doc__);out=a.out;p3=out/'_part3';p3.mkdir(exist_ok=True)
run('scripts/part3/part3_table.py',CODE/'inputs/part3/runs.csv',CODE/'inputs/part3/measures.csv',p3)
body=(p3/'table_p3.tex').read_text()
(out/'table6.tex').write_text('\n'.join([r'\begin{table*}[t]',r'\centering',r'\caption{Part 3 median results, using the original KITTI tracking filter and batch definitions.}',r'\scriptsize',
    r'\resizebox{\textwidth}{!}{%',r'\begin{tabular}{lrrrrrrrrrrrrrrr}',r'\toprule',r'Method & \multicolumn{5}{c}{TUM fr3} & \multicolumn{5}{c}{Replica room0} & \multicolumn{5}{c}{KITTI 06} \\',
    r' & SE(3) & Sim(3) & s & MAE & t & SE(3) & Sim(3) & s & MAE & t & SE(3) & Sim(3) & s & full & t \\',r'\midrule',body,r'\bottomrule',r'\end{tabular}',r'}',r'\end{table*}','']))
run('scripts/part3/part3_plots.py',CODE/'inputs/part3/runs.csv',p3,a.group)
shutil.copyfile(p3/'part3_traj_fr3.png',out/'figure1.png')
(out/'figure1.tex').write_text('\n'.join([r'\begin{figure}[t]',r'\centering',r'\includegraphics[width=\columnwidth]{figure1.png}',
 r'\caption{TUM, median run of mono, E1 and B80+E1 against ground truth. Left: SE(3); right: Sim(3).}',r'\end{figure}','']))
