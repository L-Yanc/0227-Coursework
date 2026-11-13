#!/usr/bin/env python3
"""COMP0227 Part 4: local, resumable experiments. Paths are relative to coursework root."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from common import ROOT, SOURCE, SLAM, TEAM, AUX, Blocked, Stage, artifact, atomic, command, digest, dump, local, read, resolve, utc, path_label, executable, env_python

def example():
    return {'schema_version':1,'sequence':'own_living_room','experiment_id':'living_room_20261112',
            'video':'part4/input/LivingRoom.MOV','output_dir':'part4/work/living_room_20261112',
            'phone':{'model':'iPhone 15','matching_recording_settings_confirmed':True,'lens':'user confirmed same lens; numeric zoom unspecified'},
            'prediction':{'text':None,'provenance':'user will complete report; no timing claim','recorded_before_filming':None},
            'calibration':{'videos':['part4/calibration1.MOV','part4/calibration2.MOV'],'board_cols':8,'board_rows':6,
                           'square_size_m':.115/9,'sample_fps':2,'diversity_distance':.055},
            'frames':{'target_fps':10,'max_dimension':1280,'trim_start_s':None,'trim_end_s':None,'rotation':'metadata_once'},
            'depth':{'model':'DEPTH_ANYTHING_V2','size':'base','scene':'indoor','png_factor':5000.,'device':'cpu','input_size':518},
            'markers':[{'id':'wall_100','endpoints':['a','b'],'distance_m':1.005,'uncertainty_m':.005,'role':'scale'},
                       {'id':'wall_50','endpoints':['a','b'],'distance_m':.5,'uncertainty_m':.005,'role':'check'}],
            'reference':{'threads':4,'min_registered_fraction':.7,'matcher':'sequential_plus_sparse_loops','overlap':12,
                         'loop_stride':30,'max_features':4096,'min_ray_angle_deg':1.,'max_marker_residual_px':4.,'annotation_sigma_px':1.},
            'methods':{'runs':5,'features':'ORB2','backend':'cpp','playback_speed':1.,'policies':['every','stride5'],
                       'selected':None,'selected_deferred_by_user':True,'temporal_policy_development_fraction':.5},
            'evaluation':{'interval_s':1.,'timestamp_tolerance_s':.025,'pair_tolerance_s':.12,'max_gap_s':.25},
            'standard':[]}

def load_config(path):
    c=read(resolve(path))
    if c.get('schema_version')!=1: raise ValueError('Unsupported config schema')
    work=local(c['output_dir']); work.mkdir(parents=True,exist_ok=True)
    return c,work

def init(args):
    path=local(args.config)
    if not path.exists(): dump(path,example())
    inp=ROOT/'part4/input'; inp.mkdir(exist_ok=True)
    doc=inp/'README.md'
    if not doc.exists(): atomic(doc,'# Part 4 private inputs\n\nKeep original videos unedited. Calibration: 8 x 6 inner corners, square size 0.115/9 metres. The 11.5 cm measurement excludes margins. Keep display size fixed. Scene and board camera settings confirmed identical by user. Wall pairs: 1 m scale and 0.5 m held-out check, each +/-0.005 m. No floor markers. Prediction left for report; timing unspecified.\n\nDo not publish original room media. Marker centres require review in at least 3 translated registered views each; 4-6 preferred.\n')
    print(path)

def patch_state(patch):
    def check(reverse):
        return subprocess.run(['git','apply',*(['--reverse'] if reverse else []),'--check',str(patch)],cwd=SLAM,capture_output=True,text=True)
    a,b=check(False),check(True)
    return {'state':'unapplied' if a.returncode==0 else 'applied' if b.returncode==0 else 'conflict',
            'forward_check':a.stderr,'reverse_check':b.stderr}

def doctor(c,work):
    import importlib.util
    report={'checked_utc':utc(),'available':[],'missing':[],'untested':[],
            'disk_free_gb':shutil.disk_usage(ROOT).free/1e9,'git':{},'patches':{}}
    for p in [*[Path(executable(name)) for name in ['ffmpeg','ffprobe','colmap']],env_python()[0],env_python('depth')[0],resolve(c['video']),*[resolve(v) for v in c['calibration']['videos']]]:
        report['available' if p.exists() else 'missing'].append(path_label(p))
    for mod in ['cv2','numpy','scipy','matplotlib','yaml']:
        report['available' if importlib.util.find_spec(mod) else 'missing'].append('python:'+mod)
    for label,p in [('team',TEAM),('pyslam',SLAM)]:
        if p.exists():
            try: report['git'][label]={'revision':command(['git','rev-parse','HEAD'],p).strip(),'status':command(['git','status','--short'],p)}
            except RuntimeError as e: report['untested'].append(f'{label} git metadata unavailable: {e}')
        else: report['missing'].append(f'{label} checkout: {p}')
    if SLAM.is_dir():
        for patch in sorted((TEAM/'patches').glob('coursework_changes.patch')): report['patches'][patch.name]=patch_state(patch)
    weights=SLAM/'thirdparty/depth_anything_v2/metric_depth/checkpoints/depth_anything_v2_metric_hypersim_vitb.pth'
    report['available' if weights.exists() else 'missing'].append(path_label(weights))
    if c['methods'].get('selected') is None: report['missing'].append('Selected Part 3 method adapter (deferred by user)')
    tracking=SLAM/'pyslam/slam/tracking.py'
    guard=tracking.is_file() and '# Part 4 sparse-depth playback:' in tracking.read_text()
    report['available' if guard else 'missing'].append('Part 4 sparse-depth tracking guard')
    for key in ['calibration','prepare','reference','marker_scale','depth']:
        try: report['available'].append(f'{key}: {artifact(work,key).relative_to(ROOT)}')
        except Blocked: report['untested'].append(key)
    from standard_sequences import SEQUENCES
    for name,settings in SEQUENCES.items():
        report['available' if (ROOT/settings['path']).exists() else 'missing'].append('Standard dataset: '+name)
    if not (work/'standard_reruns/status.json').exists(): report['untested'].append('Full standard-sequence comparison batches (run-standard)')
    if (work/'annotations.json').exists() and (work/'reference.json').exists():
        from readiness import marker_report
        review=marker_report(c,work,write=False)
        report['marker_readiness']={key:review[key] for key in ['saved_selections','selections_sufficient','metric_reference_ready','blockers']}
    print(json.dumps(report,indent=2))
    return report

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command',choices=['init','doctor','calibrate','prepare','reference','annotate','run','evaluate','analyse-standard','analyse-own','package','depth','test','merge','board','preflight','repair-reference','smoke-selected','run-standard','import-part3','run-all','check-standard'])
    ap.add_argument('--config',default='scripts/part4/config_recording2_fast.json')
    ap.add_argument('--video',action='append',help='Repeat for multiple calibration clips; one for prepare')
    ap.add_argument('--board-cols',type=int); ap.add_argument('--board-rows',type=int); ap.add_argument('--square-size-m',type=float)
    ap.add_argument('--port',type=int,default=8765); ap.add_argument('--smoke',action='store_true')
    ap.add_argument('--code-only',action='store_true',help='Package portable code before scored results are available')
    ap.add_argument('--unscored',action='store_true',help='Package actual raw runs/analyses with metric errors unavailable')
    ap.add_argument('--reuse-prepared',action='store_true',help='Validate/reuse existing media preparation instead of recalibrating/extracting')
    ap.add_argument('--repair-reference',action='store_true',help='Explicitly run the declared reference repair before the full batch; stop if QA fails')
    ap.add_argument('--csv',action='append'); ap.add_argument('--out')
    a=ap.parse_args()
    try:
        if a.command=='init': init(a); return
        if a.command=='board':
            import cv2
            import numpy as np
            cols,rows_=(a.board_cols or 8)+1,(a.board_rows or 6)+1
            cell=160; margin=160
            img=np.full((rows_*cell+2*margin,cols*cell+2*margin),255,np.uint8)
            for y in range(rows_):
                for x in range(cols):
                    if (x+y)%2==0: img[margin+y*cell:margin+(y+1)*cell,margin+x*cell:margin+(x+1)*cell]=0
            out=local(a.out or 'part4/input/checkerboard_9x7.png')
            if out.exists(): raise ValueError('Board output exists; choose a new output path')
            out.parent.mkdir(parents=True,exist_ok=True)
            if not cv2.imwrite(str(out),img): raise RuntimeError('Board write failed')
            print(f'{out}: measure displayed/printed squares; pixel dimensions are not physical square size.'); return
        if a.command=='test':
            result=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(SOURCE/'tests'),'-v'],cwd=SOURCE)
            raise SystemExit(result.returncode)
        if a.command=='merge':
            from scoring import merge
            merge([resolve(p) for p in a.csv or []],local(a.out)); return
        c,work=load_config(a.config)
        if a.command in ('run','run-all','run-standard','smoke-selected','depth','reference','repair-reference','check-standard'):
            from progress import install
            install(c,a.command,smoke=a.smoke)
        if a.command=='doctor': doctor(c,work); return
        dump(work/'config.json',c)
        if a.command=='calibrate':
            from media import calibrate
            calibrate(c,work,[resolve(v) for v in a.video] if a.video else None,a.board_cols,a.board_rows,a.square_size_m)
        elif a.command=='prepare':
            from media import prepare
            prepare(c,work,resolve(a.video[0]) if a.video else None)
        elif a.command=='reference':
            from reference import reference
            reference(c,work)
        elif a.command=='preflight':
            from readiness import preflight
            preflight(c,work)
        elif a.command=='repair-reference':
            from repair_reference import repair_reference
            repair_reference(c,work)
        elif a.command=='annotate':
            from reference import annotate
            annotate(c,work,a.port)
        elif a.command=='depth':
            from experiments import depth
            depth(c,work,smoke=a.smoke)
        elif a.command=='import-part3':
            from part3_results import import_results
            print(import_results(c,work))
        elif a.command=='run-all':
            from overnight import require_ready
            require_ready(c,work)
            if a.smoke: raise Blocked('Use run --smoke, smoke-selected and run-standard --smoke separately')
            from readiness import preflight
            preflight(c,work)
            from experiments import run
            run(c,work,reuse_prepared=a.reuse_prepared)
            from standard_sequences import run_standard
            run_standard(c,work)
            from scoring import package
            package(c,work)
        elif a.command=='check-standard':
            from overnight import check_standard
            check_standard(c,work)
        elif a.command=='run-standard':
            if not a.smoke:
                from overnight import require_ready
                require_ready(c,work)
            from standard_sequences import run_standard
            run_standard(c,work,smoke=a.smoke)
        elif a.command=='smoke-selected':
            from experiments import slam_run
            for method,policy,temporal in [('selected','every',False),('selected','stride5',False),('selected','keyframes',False),('selected_temporal','keyframes',True)]:
                result=slam_run(c,work,method,policy,1,smoke=True,temporal=temporal)
                if not (result/'run.json').exists() or read(result/'run.json')['status']!='complete':
                    raise Blocked(f'Selected-method smoke failed: {result}')
                report=read(result/'part3_runtime.json')
                if not report['unique_depth_requests'] or not report.get('initialization_events'):
                    raise Blocked(f'Part 3 did not consume learned depth/initialise metric scale: {result}')
                print(f'{method}/{policy} smoke passed: {result}')
        elif a.command=='run':
            from experiments import run
            run(c,work,smoke=a.smoke,reuse_prepared=a.reuse_prepared,repair_reference_first=a.repair_reference)
        elif a.command=='evaluate':
            from reference import scale_markers
            scale_markers(c,work)
            from scoring import evaluate
            evaluate(c,work)
        elif a.command=='analyse-standard':
            from analysis import analyse_standard
            analyse_standard(c,work)
        elif a.command=='analyse-own':
            from analysis import analyse_own
            analyse_own(c,work)
        elif a.command=='package':
            from scoring import package, package_code, package_unscored
            if a.code_only: package_code(c,work)
            elif a.unscored: package_unscored(c,work)
            else: package(c,work)
    except (Blocked,ValueError,RuntimeError,FileNotFoundError) as e:
        print(f'BLOCKED: {e}',file=sys.stderr); raise SystemExit(2)

if __name__=='__main__': main()
