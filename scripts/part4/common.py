"""Local paths, atomic outputs and auditable, content-addressed stage execution."""
import csv
import hashlib
import io
import json
import os
import signal
import shutil
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone

SOURCE = Path(__file__).resolve().parent
TEAM = Path(os.environ.get('CW1_REPO', SOURCE.parents[1])).resolve()
ROOT = Path(os.environ.get('PART4_ROOT', TEAM)).resolve()
SLAM = Path(os.environ.get('PYSLAM_ROOT', ROOT/'external/pyslam')).resolve()
AUX = Path(os.environ.get('CW1_RECON_BIN', ROOT/'tools/reconstruction/.pixi/envs/default/bin')).resolve()

def path_label(path):
    """Paths inside the work root are relative; external inputs stay explicit."""
    p = Path(path).resolve()
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)

def executable(name):
    override = os.environ.get('CW1_' + name.upper())
    candidate = Path(override) if override else AUX/name
    return str(candidate) if candidate.is_file() else (shutil.which(name) or str(candidate))

class Blocked(RuntimeError):
    pass

def utc():
    return datetime.now(timezone.utc).isoformat()

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()

def atomic(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    tmp.write_text(content)
    tmp.replace(path)

def dump(path, value):
    atomic(path, json.dumps(value, indent=2, allow_nan=False, default=lambda x: x.tolist() if hasattr(x, 'tolist') else str(x)) + '\n')

def read(path):
    return json.loads(Path(path).read_text())

def table(path, rows, fields=None):
    rows = list(rows)
    fields = fields or list(dict.fromkeys(k for r in rows for k in r))
    s = io.StringIO()
    w = csv.DictWriter(s, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
    atomic(path, s.getvalue())

def rows(path):
    with Path(path).open(newline='') as f:
        return list(csv.DictReader(f))

def resolve(path):
    p = Path(path).expanduser()
    return p.resolve() if p.is_absolute() else (ROOT / p).resolve()

def local(path):
    p = resolve(path)
    if not p.is_relative_to(ROOT):
        raise ValueError(f'Outputs must be inside coursework root: {p}')
    return p

def command(args, cwd=ROOT, timeout=None):
    r = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(f'Command failed ({r.returncode}): {args[0]}\n{r.stderr[-3000:]}')
    return r.stdout

def revision():
    return command(['git', 'rev-parse', 'HEAD'], SLAM).strip()

def code_hash(stage=None):
    modules={'calibration':['media','geometry'],'prepare':['media','geometry'],
             'reference':['reference','geometry'],'marker_scale':['reference','geometry'],
             'depth':['depth_worker','geometry'], 'slam':['experiments','slam_worker','geometry']}
    names=['common',*modules.get(stage,[])] if stage in modules else None
    paths=[SOURCE/f'{n}.py' for n in names] if names else sorted(SOURCE.glob('*.py'))
    return fingerprint({p.name: digest(p) for p in paths if p.exists()})

def env_python(name='default'):
    # The parent wrapper provides the isolated cache settings. Child processes retain them.
    env = dict(os.environ)
    selected = os.environ.get('CW1_DEPTH_ENV' if name == 'depth' else 'CW1_SLAM_ENV', name)
    prefix = SLAM / '.pixi/envs' / selected
    env['PATH'] = str(prefix/'bin') + os.pathsep + env.get('PATH', '')
    env['PYTHONPATH'] = os.pathsep.join(filter(None, [str(SLAM), str(SLAM/'thirdparty/gtsam_local/install/python'), env.get('PYTHONPATH')]))
    env['PYSLAM_USE_CPP'] = 'true'
    env['OMP_NUM_THREADS'] = '4'
    env['OPENBLAS_NUM_THREADS'] = '1'
    python = Path(os.environ.get('CW1_DEPTH_PYTHON' if name == 'depth' else 'CW1_SLAM_PYTHON', prefix/'bin/python'))
    return python, env

class Stage:
    """A new immutable directory for every input/settings/code fingerprint.

    Interrupted attempts retain logs; completed cache entries are verified by hashes.
    """
    def __init__(self, work, name, settings, inputs=()):
        self.inputs = {str(Path(p).relative_to(ROOT) if Path(p).is_relative_to(ROOT) else p): digest(p) for p in inputs}
        self.key = fingerprint({'settings': settings, 'inputs': self.inputs, 'code': code_hash(name)})
        self.path = local(Path(work)/name/self.key[:16])
        self.meta = {'stage': name, 'key': self.key, 'settings': settings, 'input_hashes': self.inputs,
                     'software_revision': revision(), 'source_hash': code_hash(name), 'started_utc': utc(), 'commands': []}
        self.start = time.perf_counter()

    def cached(self):
        m = self.path/'stage.json'
        if not m.exists():
            return False
        d = read(m)
        return d.get('status') == 'complete' and d.get('key') == self.key and all((self.path/p).is_file() and digest(self.path/p) == h for p,h in d.get('outputs', {}).items())

    def begin(self):
        self.path.mkdir(parents=True, exist_ok=True)
        dump(self.path/'stage.json', {**self.meta, 'status': 'running'})
        print(f'{self.meta["stage"]}: {self.path.relative_to(ROOT)}', flush=True)
        return self.path

    def run(self, args, cwd=ROOT, env=None):
        args = [str(a) for a in args]
        idx = len(list(self.path.glob('command_*.json')))
        base = self.path/f'command_{idx:03d}'
        rec = {'argv': args, 'cwd': str(cwd), 'started_utc': utc()}
        t = time.perf_counter()
        dump(base.with_suffix('.json'), rec)
        try:
            with base.with_suffix('.stdout.log').open('w') as out, base.with_suffix('.stderr.log').open('w') as err:
                process = subprocess.Popen(args,cwd=cwd,env=env,stdout=out,stderr=err,start_new_session=True)
                try:
                    return_code=process.wait()
                except BaseException:
                    try: os.killpg(process.pid,signal.SIGTERM)
                    except ProcessLookupError: pass
                    try: process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid,signal.SIGKILL); process.wait()
                    raise
                if return_code:
                    # A crashed native worker can leave multiprocessing children alive.
                    # They are confined to this task-owned process group.
                    try: os.killpg(process.pid,signal.SIGTERM)
                    except ProcessLookupError: pass
            rec.update(exit_code=return_code, elapsed_s=time.perf_counter()-t, ended_utc=utc())
            dump(base.with_suffix('.json'), rec)
            self.meta['commands'].append(rec)
            if return_code:
                raise RuntimeError(f'Exit {return_code}; see {base.with_suffix(".stderr.log")}')
        except BaseException as e:
            dump(self.path/'stage.json', {**self.meta, 'status': 'failed', 'reason': str(e)})
            raise

    def finish(self, expected):
        outputs = {}
        for p in expected:
            p = self.path/Path(p)
            if not p.is_file() or p.stat().st_size == 0:
                raise RuntimeError(f'Missing/empty output: {p}')
            outputs[str(p.relative_to(self.path))] = digest(p)
        dump(self.path/'stage.json', {**self.meta, 'status': 'complete', 'ended_utc': utc(),
                                    'elapsed_s': time.perf_counter()-self.start, 'outputs': outputs})

def publish_pointer(work, name, stage):
    dump(Path(work)/f'{name}.json', {'path': str(stage.path.relative_to(ROOT)), 'key': stage.key})

def artifact(work, name):
    p = Path(work)/f'{name}.json'
    if not p.exists():
        raise Blocked(f'{name} is not ready; run its stage first')
    d = resolve(read(p)['path'])
    if read(d/'stage.json').get('status') != 'complete':
        raise Blocked(f'{name} has no validated completed output')
    return d
