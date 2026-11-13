"""Render Part 4 Table VII and Figures 2-3 from saved evidence."""
from _cli import CODE,arguments,run
import shutil
a=arguments(__doc__);out=a.out;p4=out/'_part4';p4.mkdir(exist_ok=True)
run('scripts/report/_part4_renderer.py','--repo',CODE,'--out',p4)
shutil.copyfile(p4/'part4_results.tex',out/'table7.tex')
for n,stem in [(2,'part4_agreement'),(3,'part4_failure')]:
 shutil.copyfile(p4/(stem+'.png'),out/f'figure{n}.png')
 (out/f'figure{n}.tex').write_text((p4/(stem+'.tex')).read_text().replace(stem+'.png',f'figure{n}.png'))
