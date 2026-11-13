"""Portable roots and non-destructive generated-file updates."""
import hashlib
from pathlib import Path
import zipfile
CODE = Path(__file__).resolve().parents[2]
GROUP = CODE.parent
AUDIT = GROUP.parent / '_assembly'
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path, data, audit=AUDIT):
    path = Path(path)
    data = data.encode() if isinstance(data, str) else data
    if path.exists():
        old = path.read_bytes()
        if old == data: return
        versions = Path(audit) / 'previous_versions'
        versions.mkdir(parents=True, exist_ok=True)
        snapshot = versions / (path.name + '.' + hashlib.sha256(old).hexdigest() + '.zip')
        if not snapshot.exists():
            with zipfile.ZipFile(snapshot, 'x', zipfile.ZIP_DEFLATED) as z: z.writestr(path.name, old)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
