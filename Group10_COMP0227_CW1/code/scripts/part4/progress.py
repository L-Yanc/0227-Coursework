"""Console-only progress instrumentation installed at CLI startup.

Kept outside scientific stage fingerprints: adding console reporting must not
invalidate completed experiments. This module never kills or restarts workers.
"""
import csv
import functools
import threading
import time
from pathlib import Path
from datetime import datetime, timezone
from common import ROOT, read


def duration(seconds):
    seconds=max(0,int(seconds));hours,seconds=divmod(seconds,3600);minutes,seconds=divmod(seconds,60)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d}'


def planned_attempts(c,command,smoke=False):
    if smoke or command=='smoke-selected': return 0
    m=c['methods'];room=1+len(m['policies'])
    if m.get('selected'):
        room+=len(m.get('selected_policies',['every']))+bool(m.get('temporal_consistency',{}).get('enabled'))
    standard=3*7  # Three native datasets, seven configurations in run_standard.
    groups=room if command=='run' else standard if command=='run-standard' else room+standard if command=='run-all' else 0
    return groups*m['runs']


class Heartbeat:
    def __init__(self,callback,interval=300.):
        self.callback=callback;self.interval=interval;self.stop_event=threading.Event();self.thread=None
    def __enter__(self):
        def loop():
            while not self.stop_event.wait(self.interval):
                try:self.callback()
                except Exception:pass  # Console diagnostics cannot fail a scientific worker.
        self.thread=threading.Thread(target=loop,name='part4-progress',daemon=True);self.thread.start();return self
    def __exit__(self,*args):
        self.stop_event.set();self.thread.join(timeout=1.)


def worker_progress(path,started_wall):
    """Read only files created/updated by this invocation, ignoring stale retries."""
    path=Path(path);now=time.time();parts=[]
    result=path/'run.json';frames=path/'frame_status.csv'
    if result.exists() and result.stat().st_mtime>=started_wall:
        info=read(result)
        if info.get('backend_quiescent'):
            parts.append('results exported; waiting for worker exit')
    if frames.exists() and frames.stat().st_mtime>=started_wall:
        with frames.open('rb') as f:
            header=f.readline().decode().strip().split(',');f.seek(0,2);size=f.tell();f.seek(max(0,size-16384));tail=f.read()
        lines=tail.decode(errors='replace').splitlines()
        records=[r for r in csv.reader(lines) if len(r)==len(header) and r[0].isdigit()]
        if records:
            last=dict(zip(header,records[-1]));processed=int(last['frame_id'])+1
            spec=read(path/'spec.json');prep=ROOT/spec['prepare']
            with (prep/'frames.csv').open() as f:total=max(0,sum(1 for _ in f)-1)
            if spec.get('max_frames') is not None:total=min(total,spec['max_frames'])
            parts.append(f'frames {processed}/{total}; state {last.get("state","unknown")}')
            parts.append(f'last frame update {duration(now-frames.stat().st_mtime)} ago')
    if not parts:parts.append('worker starting or processing; no frame update saved yet')
    logs=[p for pattern in ['command_*.stdout.log','command_*.stderr.log'] for p in path.glob(pattern)]
    if logs:
        newest=max(p.stat().st_mtime for p in logs)
        parts.append(f'last worker log update {duration(now-newest)} ago')
    return ' | '.join(parts)


class Reporter:
    def __init__(self,c,command,smoke=False,emit=None,heartbeat_interval=300.):
        self.total=planned_attempts(c,command,smoke);self.index=0;self.current=None;self.current_cached=False
        self.started=time.monotonic();self.interval=heartbeat_interval
        self.emit=emit or (lambda text:print(f'[{datetime.now(timezone.utc).isoformat(timespec="seconds")}] {text}',flush=True))
    def wrap_attempt(self,original):
        @functools.wraps(original)
        def wrapped(c,work,method,policy,run_number,smoke=False,temporal=False):
            if not smoke:self.index+=1
            label='SMOKE' if smoke else f'Attempt {self.index}/{self.total}' if self.total else 'CHECK'
            label+=f" | {c['sequence']} | {method}/{policy} | repetition {run_number}/{c['methods']['runs']}"
            previous=self.current;previous_cached=self.current_cached;self.current=label;self.current_cached=False
            started=time.monotonic();self.emit(f'{label} | START')
            try:
                result=original(c,work,method,policy,run_number,smoke=smoke,temporal=temporal)
                stage=read(result/'stage.json');info=read(result/'run.json') if (result/'run.json').exists() else {}
                if self.current_cached:
                    suffix=f" | saved worker runtime {duration(info['elapsed_s'])}" if info.get('elapsed_s') is not None else ''
                    self.emit(f'{label} | CACHED: reused completed output (saved status: {info.get("status","unknown")}){suffix} | cache check {duration(time.monotonic()-started)}')
                else:
                    status='DONE' if stage.get('status')=='complete' and info.get('status')=='complete' else 'FAILED'
                    self.emit(f'{label} | {status} | runtime {duration(time.monotonic()-started)} | batch elapsed {duration(time.monotonic()-self.started)}')
                return result
            except BaseException as e:
                status='INTERRUPTED' if isinstance(e,KeyboardInterrupt) else 'ERROR'
                self.emit(f'{label} | {status} | elapsed {duration(time.monotonic()-started)} | {type(e).__name__}: {e}')
                raise
            finally:self.current=previous;self.current_cached=previous_cached
        return wrapped
    def wrap_cached(self,original):
        @functools.wraps(original)
        def wrapped(stage):
            cached=original(stage)
            if cached and self.current and stage.meta['stage']=='slam':self.current_cached=True
            return cached
        return wrapped
    def wrap_stage_run(self,original):
        @functools.wraps(original)
        def wrapped(stage,*args,**kwargs):
            label=self.current or f"Stage {stage.meta['stage']}"
            started=time.monotonic();started_wall=time.time()
            if not self.current:self.emit(f'{label} | START worker | {stage.path.relative_to(ROOT)}')
            def heartbeat():
                self.emit(f'{label} | HEARTBEAT | elapsed {duration(time.monotonic()-started)} | {worker_progress(stage.path,started_wall)}')
            with Heartbeat(heartbeat,self.interval):
                if stage.meta['stage']=='slam' and args:
                    from supervision import run_supervised
                    result=run_supervised(stage,*args,**kwargs)
                else:
                    result=original(stage,*args,**kwargs)
            if not self.current:self.emit(f'{label} | worker finished | runtime {duration(time.monotonic()-started)}')
            return result
        return wrapped


def acquire_batch_lock(work):
    import fcntl
    import os
    from common import Blocked
    work=Path(work);work.mkdir(parents=True,exist_ok=True);handle=(work/'.batch.lock').open('a+')
    try:fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        handle.seek(0);owner=handle.read().strip();handle.close()
        raise Blocked(f'Another batch owns {work}/.batch.lock ({owner}). Do not start a second copy.')
    handle.seek(0);handle.truncate();handle.write(f'pid={os.getpid()} started={datetime.now(timezone.utc).isoformat()}');handle.flush()
    return handle


_batch_lock=None
_installed=False

def install(c,command,smoke=False):
    global _installed,_batch_lock
    if _installed:return
    if command in ('run','run-all','run-standard','check-standard','depth','reference','repair-reference','smoke-selected'):
        _batch_lock=acquire_batch_lock(ROOT/c['output_dir'])
    _installed=True
    from common import Stage
    import experiments
    reporter=Reporter(c,command,smoke)
    experiments.slam_run=reporter.wrap_attempt(experiments.slam_run)
    Stage.run=reporter.wrap_stage_run(Stage.run)
    Stage.cached=reporter.wrap_cached(Stage.cached)
    if reporter.total:
        reporter.emit(f'Batch plan: {reporter.total} attempts (including completed attempts reused from cache). Heartbeat every 5 minutes while a worker is running.')
    return reporter
