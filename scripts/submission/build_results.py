#!/usr/bin/env python3
"""Build one coursework CSV from saved results, preserving protocol differences."""
import csv
import json
from pathlib import Path
import statistics
import sys

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'scripts/part4'))
from scoring import FIELDS, configuration_key
from master_results import EXTRA, canonical_sequence

AUDIT=['source_csv','trajectory_status','time_protocol']


def read(path):
    with path.open(newline='') as f:return list(csv.DictReader(f))


def write(path,rows,fields):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def main():
    rows=[]
    sources=[('Results/part1_submission_results_30.csv','part1'),
             ('Results/part2/slam_results.csv','part2'),
             ('Results/part3_part4_combined_results.csv',None)]
    for filename,part in sources:
        for source in read(REPO/filename):
            row=dict.fromkeys(FIELDS+EXTRA+AUDIT,'');row.update(source)
            row['sequence']=canonical_sequence(source['sequence'])
            row['source_csv']=filename
            if part:
                row.update(source_part=part,source_run_id=source['run_id'],
                           source_sequence=source['sequence'],source_configuration=source['settings'],
                           rpe_protocol='approximately 1 second; scale-corrected; contiguous source frame IDs',
                           tracking_fraction_basis='historical saved tracked/lost frame counts / total input frames',
                           trajectory_timestamp_provenance=('missing original trajectory; source timestamps unverified' if part=='part1'
                               else 'saved source frame IDs; identical full-pose prefix and certified trailing suffix; Replica nominal 25 Hz'))
            rel=Path(row['trajectory_file'])
            if rel.is_absolute() or '..' in rel.parts:raise ValueError('Invalid trajectory path')
            row['trajectory_status']='present' if (REPO/rel).is_file() else 'missing'
            row['time_protocol']=('playback-inclusive historical wall time in source_wall_time_per_frame_ms'
                                   if row['source_part']=='part3' else 'synchronous slam.track call milliseconds')
            rows.append(row)
    if len({r['run_id'] for r in rows})!=len(rows):raise ValueError('Duplicate run IDs')
    write(REPO/'Results/coursework_results.csv',rows,FIELDS+EXTRA+AUDIT)
    groups={}
    for r in rows:
        key=(r['source_part'],r['sequence'],r['method'],configuration_key(r))
        groups.setdefault(key,[]).append(r)
    aggregates=[]
    for (part,seq,method,settings),group in sorted(groups.items()):
        for metric in [*FIELDS[5:13],'rpe_1m_m','source_wall_time_per_frame_ms']:
            values=[float(r[metric]) for r in group if r.get(metric) not in ('',None)]
            aggregates.append(dict(source_part=part,sequence=seq,method=method,configuration=settings,metric=metric,
                                   n=len(values),mean=statistics.mean(values) if values else '',
                                   sd=statistics.stdev(values) if len(values)>1 else '',
                                   median=statistics.median(values) if values else '',
                                   missing_trajectories=sum(r['trajectory_status']=='missing' for r in group)))
    write(REPO/'Results/coursework_aggregates.csv',aggregates,list(aggregates[0]))
    missing=[{'run_id':r['run_id'],'trajectory_file':r['trajectory_file']} for r in rows if r['trajectory_status']=='missing']
    write(REPO/'Results/missing_trajectories.csv',missing,['run_id','trajectory_file'])
    print(json.dumps({'rows':len(rows),'by_part':{p:sum(r['source_part']==p for r in rows) for p in sorted({r['source_part'] for r in rows})},
                      'missing_trajectories':len(missing)},indent=2))


if __name__=='__main__':main()
