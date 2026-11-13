"""Bounded CLI worker supervision, separate from numerical experiment code."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
from common import ROOT,read,dump,digest,rows,utc
from geometry import read_tum


def completed_payload(path,started_wall):
    path=Path(path);f=path/'run.json'
    if not f.exists() or f.stat().st_mtime<started_wall:return None
    try:
        r=read(f);s=read(path/'spec.json')
        if not r.get('backend_quiescent') or r.get('status') not in ('complete','failed'):return None
        source=rows(ROOT/s['prepare']/'frames.csv')
        if s.get('max_frames') is not None:source=source[:s['max_frames']]
        states=rows(path/'frame_status.csv')
        if len(states)!=len(source) or r['frames']!=len(source):return None
        if [(x['frame_id'],x['timestamp']) for x in states]!=[(x['frame_id'],x['timestamp']) for x in source]:return None
        names=['run.json','frame_status.csv','map_observations.csv']
        if r['status']=='complete':
            if len(read_tum(path/'trajectory.tum'))!=r['trajectory_poses']:return None
            names.append('trajectory.tum')
        import csv
        with (path/'map_observations.csv').open() as handle:
            reader=csv.DictReader(handle)
            if not {'frame_id','point_id','map_depth'}<=set(reader.fieldnames or []):return None
            if sum(1 for _ in reader)!=r['map_observations']:return None
        if s.get('selected'):
            read(path/'part3_runtime.json');names.append('part3_runtime.json')
        return {name:digest(path/name) for name in names}
    except (ValueError,KeyError,OSError,TypeError):return None


def terminate_group(process):
    try:os.killpg(process.pid,signal.SIGTERM)
    except ProcessLookupError:pass
    try:return process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        return process.wait()


def run_supervised(stage,args,cwd=ROOT,env=None,poll_s=5.,exit_grace_s=60.,timeout_s=1800.):
    args=[str(x) for x in args];idx=len(list(stage.path.glob('command_*.json')));base=stage.path/f'command_{idx:03d}'
    rec={'argv':args,'cwd':str(cwd),'started_utc':utc()};dump(base.with_suffix('.json'),rec)
    start=time.monotonic();started_wall=time.time();ready_since=None;proof=None;recovered=False;timed_out=False;process=None
    try:
        with base.with_suffix('.stdout.log').open('w') as out,base.with_suffix('.stderr.log').open('w') as err:
            process=subprocess.Popen(args,cwd=cwd,env=env,stdout=out,stderr=err,start_new_session=True)
            try:
                while True:
                    try:
                        code=process.wait(timeout=poll_s);break
                    except subprocess.TimeoutExpired:
                        if proof is None:
                            proof=completed_payload(stage.path,started_wall)
                            if proof is not None:ready_since=time.monotonic()
                        if proof is not None and time.monotonic()-ready_since>=exit_grace_s:
                            if completed_payload(stage.path,started_wall)==proof:
                                print(f'Worker supervision: validated results saved; ending stuck exit after {exit_grace_s:.0f}s grace. No tracking rerun.',flush=True)
                                code=terminate_group(process);recovered=True;break
                            proof=None;ready_since=None
                        if time.monotonic()-start>=timeout_s:
                            print(f'Worker supervision: attempt exceeded {timeout_s/60:.0f} minutes; stopping this worker and preserving its partial logs.',flush=True)
                            code=terminate_group(process);timed_out=True;break
            except BaseException:
                terminate_group(process);raise
        rec.update(exit_code=code,elapsed_s=time.monotonic()-start,ended_utc=utc(),successful_payload_recovered=recovered,attempt_timeout=timed_out)
        dump(base.with_suffix('.json'),rec);stage.meta['commands'].append(rec)
        if recovered:
            archive=stage.path/'supervision_recovery';archive.mkdir(exist_ok=True)
            shutil.copyfile(stage.path/'run.json',archive/'run_before_recovery.json')
            result=read(stage.path/'run.json');result.update(shutdown_recovered=True,shutdown_recovery_note='CLI supervisor validated all exported result files with a quiescent backend, then terminated only the stuck worker process group after a 60-second exit grace. Numeric outputs were not rerun.')
            dump(stage.path/'run.json',result)
            dump(stage.path/'worker_supervision.json',{'verified_original_payload_hashes':proof,'command':rec,'numerical_outputs_rerun':False})
        elif code or completed_payload(stage.path,started_wall) is None:
            # Do not let stale/partial run.json from an interrupted attempt be
            # misread as a successful result by downstream exporters.
            result=stage.path/'run.json'
            if result.exists():
                archive=stage.path/'incomplete_payloads';archive.mkdir(exist_ok=True)
                shutil.move(result,archive/f'run_{idx:03d}.json')
            raise RuntimeError(f'Worker {"timed out" if timed_out else "failed or exported incomplete results"} (exit {code}); see {base.with_suffix(".stderr.log")}')
    except BaseException as e:
        dump(stage.path/'stage.json',{**stage.meta,'status':'failed','reason':str(e)})
        raise
