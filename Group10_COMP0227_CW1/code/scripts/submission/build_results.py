#!/usr/bin/env python3
"""Rebuild the submission CSV from verified source exports; no SLAM."""
import argparse
import collections
import csv
import io
import json
from pathlib import Path
import statistics
import re
from layout import CODE, GROUP, AUDIT, save, sha
FIELDS = 'run_id sequence method settings run_number ate_unscaled_m ate_scaled_m fitted_scale rpe_rmse_m fraction_tracked fraction_lost time_per_frame_ms map_depth_mae_m trajectory_file'.split()
EXTRA = 'source_part source_run_id source_sequence source_configuration rpe_protocol rpe_1m_m source_wall_time_per_frame_ms tracking_fraction_basis trajectory_timestamp_provenance source_csv trajectory_status time_protocol frame_offset'.split()
def read(path):
    with Path(path).open(newline='') as f: return list(csv.DictReader(f))
def encode(rows, fields):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader(); writer.writerows(rows)
    return stream.getvalue()
def canonical_sequence(value):
    value = value.lower()
    if 'kitti' in value: return 'KITTI 06'
    if 'room0' in value or 'replica' in value: return 'Replica room0'
    if 'fr3' in value or 'tum' in value or 'freiburg' in value: return 'TUM fr3'
    return 'own'
def submission_id(part, original, binding):
    seq={'KITTI 06':'kitti06','TUM fr3':'tum_fr3','Replica room0':'replica_room0','own':'own'}[canonical_sequence(original['sequence'])]
    method=original['method'].lower()
    if part=='part1':
        backend=re.search(r'backend=([^;]+)',original['settings']).group(1)
        config=('mono' if method=='monocular' else 'rgbd')+'_'+backend
    elif part=='part2':
        config={'monocular':'mono','rgbd':'rgbd','pseudo_rgbd':'reference'}[method]+'_cpp'
    elif part=='part3':
        tag=binding['configuration'].split('_',1)[1].lower()
        batch=re.search(r'batch=(\d+)',original['settings']).group(1)
        if tag=='a':
            tag='reference' if 'pseudo' in method else 'rgbd' if 'rgb' in method else 'mono'
        config='batch'+batch+'_'+tag
    else:
        config={'mono':'mono_every','pseudo_rgbd':'reference_every','pseudo_rgbd_stride5':'reference_stride5',
                'selected':'b80e1_every','selected_keyframes':'b80e1_keyframes','selected_stride5':'b80e1_stride5',
                'selected_temporal_keyframes':'b80e1_temporal_keyframes'}[method]
    return 'p'+part[-1]+'_'+seq+'_'+config+'_r'+str(int(original['run_number'])).zfill(2)

def build(inputs, group):
    manifest = json.loads((inputs / 'manifest.json').read_text())
    result = []
    for part in ['part1', 'part2', 'part3', 'part4']:
        source = inputs / (part + '.csv')
        if sha(source) != manifest['source_sha256'][source.name]: raise ValueError('Changed source export: ' + str(source))
        for original in read(source):
            row = {k: original.get(k, '') for k in FIELDS + EXTRA}
            binding = manifest['runs'][original['run_id']]
            row.update(run_id=submission_id(part,original,binding), source_part=binding['source_part'], source_run_id=original['run_id'],
                       source_sequence=original['sequence'], source_configuration=binding['configuration'],
                       sequence=canonical_sequence(original['sequence']), trajectory_file=binding['trajectory_file'],
                       source_csv='code/inputs/' + source.name, trajectory_status='present',
                       tracking_fraction_basis=binding['tracking_fraction_basis'],
                       trajectory_timestamp_provenance=binding['timestamp_provenance'],
                       rpe_protocol=binding['rpe_protocol'], time_protocol=binding['time_protocol'],
                       frame_offset=str(binding.get('frame_offset', '')))
            if part == 'part3': row['source_wall_time_per_frame_ms'] = original['wall_time_per_frame_ms']
            path = (group / row['trajectory_file']).resolve()
            if not path.is_relative_to(group.resolve()) or sha(path) != binding['sha256']:
                raise ValueError('Trajectory identity/hash mismatch: ' + row['run_id'])
            result.append(row)
    if len(result) != 397 or len({r['run_id'] for r in result}) != 397: raise ValueError('Expected 397 unique verified runs')
    return sorted(result,key=lambda row:row["run_id"])
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', type=Path, default=GROUP)
    parser.add_argument('--inputs', type=Path, default=CODE / 'inputs')
    parser.add_argument('--audit', type=Path, default=AUDIT)
    args = parser.parse_args()
    rows = build(args.inputs, args.group)
    save(args.group / 'results.csv', encode(rows, FIELDS + EXTRA), args.audit)
    groups = collections.defaultdict(list)
    for row in rows: groups[(row['source_part'], row['sequence'], row['method'], row['source_configuration'])].append(row)
    aggregates = []
    for key, members in sorted(groups.items()):
        for metric in FIELDS[5:13] + ['rpe_1m_m', 'source_wall_time_per_frame_ms']:
            values = [float(r[metric]) for r in members if r[metric] != '']
            aggregates.append(dict(source_part=key[0], sequence=key[1], method=key[2], configuration=key[3],
                metric=metric, n=len(values), mean=statistics.mean(values) if values else '',
                sd=statistics.stdev(values) if len(values)>1 else '', median=statistics.median(values) if values else ''))
    save(args.audit / 'coursework_aggregates.csv', encode(aggregates, list(aggregates[0])), args.audit)
    print(json.dumps({'rows':len(rows), 'counts':dict(collections.Counter(r['source_part'] for r in rows)),
                     'csv':str(args.group / 'results.csv')}, indent=2))
if __name__ == '__main__': main()
