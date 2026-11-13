"""Import teammate artifacts by immutable git revision, without changing branches."""
import csv
import gzip
import io
import shutil
from pathlib import Path
import subprocess
import zipfile
import numpy as np
from common import ROOT,TEAM,SOURCE,Stage,Blocked,atomic,dump,rows,table,publish_pointer,read
from geometry import read_tum

REVISION='94c47e1'
def git(*args):
    return subprocess.check_output(['git',*args],cwd=TEAM)

def import_results(c,work):
    bundled=TEAM/'Results/part3'
    if (bundled/'runs.csv').is_file():
        return import_bundled_results(work,bundled)
    tree=git('ls-tree','-r',REVISION,'iteration2').decode().splitlines()
    identities={line.split('\t')[1]:line.split()[2] for line in tree}
    stage=Stage(work,'part3_import',{'revision':REVISION,'git_blob_ids':identities},[SOURCE/'part3_source/runs.csv',SOURCE/'part3_source/summary.csv'])
    if stage.cached():publish_pointer(work,'part3_import',stage);return stage.path
    out=stage.begin()
    for name in ['runs.csv','summary.csv','part3_folders.txt']:
        atomic(out/name,git('show',f'{REVISION}:iteration2/part3/{name}').decode())
    counts=[];failures=[]
    with zipfile.ZipFile(io.BytesIO(git('show',f'{REVISION}:iteration2/part3/trajectories_tum.zip'))) as z:
        for item in z.infolist():
            path=Path(item.filename)
            if path.is_absolute() or '..' in path.parts:raise ValueError('Unsafe teammate trajectory path')
            if item.is_dir():continue
            dest=out/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(item))
            try:
                a=read_tum(dest);counts.append({'trajectory':str(path),'poses':len(a),'first_timestamp':a[0,0],'last_timestamp':a[-1,0]})
            except ValueError as e:failures.append({'trajectory':str(path),'reason':str(e)})
    table(out/'trajectory_inventory.csv',counts)
    # Keep each historical run distinct. Do not merge 1m RPE/wall-time with own 1s RPE/track-call time.
    history=rows(out/'runs.csv');summary=[]
    for config,mode,seq in sorted(set((r['config'],r['mode'],r['seq']) for r in history)):
        group=[r for r in history if (r['config'],r['mode'],r['seq'])==(config,mode,seq)]
        for metric in ['ate_se3_m','ate_sim3_m','scale','rpe_1m_m','wall_s_per_frame']:
            values=np.array([float(r[metric]) for r in group]);values=values[np.isfinite(values)]
            summary.append({'config':config,'mode':mode,'sequence':seq,'metric':metric,'n':len(values),
                            'mean':float(np.mean(values)) if len(values) else None,'sd':float(np.std(values,ddof=1)) if len(values)>1 else None})
    table(out/'historical_mean_sd.csv',summary)
    # These are match-level records, not persistent point tracks. Aggregate by run/bin;
    # never present their row count as independent map-point evidence.
    bins=[];logcounts=[]
    for path in sorted(p for p in identities if p.startswith('iteration2/part3/pointlogs/') and p.endswith('.gz')):
        groups={};total=added=0
        with gzip.open(io.BytesIO(git('show',f'{REVISION}:{path}')),'rt') as f:
            for row in csv.DictReader(f):
                total+=1;added+=int(row['b_added'])
                if row['tri_added']!='1':continue
                z,d=float(row['z_tri_m']),float(row['d_hat_m']);angle=float(row['parallax_deg'])
                if min(z,d)<=0 or not np.isfinite([z,d,angle]).all():continue
                label='<1' if angle<1 else '1-3' if angle<3 else '3-10' if angle<10 else '>=10'
                groups.setdefault(label,[]).append((abs(z-d),d/z))
        logcounts.append({'source':path,'matches':total,'b_points_added':added})
        for label,values in groups.items():
            a=np.array(values);bins.append({'source':path,'parallax_bin_deg':label,'matched_observations':len(a),
                                           'median_abs_network_map_difference_m':float(np.median(a[:,0])),
                                           'median_network_map_ratio':float(np.median(a[:,1]))})
    table(out/'point_log_counts.csv',logcounts);table(out/'point_log_parallax.csv',bins)
    status={'revision':REVISION,'historical_runs':len(history),'valid_trajectory_files':len(counts),'trajectory_failures':failures,
            'point_logs':len(logcounts),'standard_detailed_analysis_complete':False,
            'limitations':['Teammate timestamps were reconstructed by matching GT positions; source image/time association is not independently certified by this syntax check.',
                           'Historical RPE is over 1 metre, not 1 second; historical time includes playback and is not tracking-call compute.',
                           'Point logs contain pair-match records without persistent point IDs or world geometry. They cannot establish temporal same-point consistency.',
                           'Point-log map metres use a learned-depth-derived scale; agreement is not independent metric validation. No phone/sensor true-depth claim is made.',
                           'Use run-standard for fresh full map geometry, persistent IDs, true-depth comparisons on TUM/Replica, temporal intervention and consistent 1-second RPE.']}
    dump(out/'status.json',status)
    stage.finish(['runs.csv','summary.csv','part3_folders.txt','historical_mean_sd.csv','trajectory_inventory.csv','point_log_counts.csv','point_log_parallax.csv','status.json'])
    publish_pointer(work,'part3_import',stage);return out


def import_bundled_results(work,source):
    """A submission clone has the source data; no hidden branch is required."""
    names=['runs.csv','summary.csv','part3_folders.txt','historical_mean_sd.csv',
           'point_log_counts.csv','point_log_parallax.csv']
    history=rows(source/'runs.csv')
    trajectories=TEAM/'trajectories_tum/part3'
    paths=[trajectories/f"{r['config']}_{r['mode']}_{r['seq']}_{r['run']}.txt" for r in history]
    stage=Stage(work,'part3_import',{'revision':REVISION,'source':'packaged historical artifacts'},
                [*[source/n for n in names],*paths])
    if stage.cached():publish_pointer(work,'part3_import',stage);return stage.path
    out=stage.begin();(out/'trajectories').mkdir(exist_ok=True)
    inventory=[]
    for path in paths:
        a=read_tum(path);shutil.copyfile(path,out/'trajectories'/path.name)
        inventory.append({'trajectory':'trajectories/'+path.name,'poses':len(a),
                          'first_timestamp':a[0,0],'last_timestamp':a[-1,0]})
    for name in names:shutil.copyfile(source/name,out/name)
    table(out/'trajectory_inventory.csv',inventory)
    status=read(source/'import_status.json')
    status.update(historical_runs=len(history),valid_trajectory_files=len(paths),
                  import_source='packaged data; original revision '+REVISION)
    dump(out/'status.json',status)
    stage.finish([*names,'trajectory_inventory.csv','status.json',*['trajectories/'+p.name for p in paths]])
    publish_pointer(work,'part3_import',stage);return out
