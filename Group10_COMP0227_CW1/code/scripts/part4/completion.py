"""Completion counts distinguish attempted experiments from successful accuracy scores."""
import json
from common import rows,read

def completion_report(c,work,evaluated):
    expected=[('mono','every'),*[( 'pseudo_rgbd',p) for p in c['methods']['policies']]]
    if c['methods'].get('selected'):
        expected += [('selected',p) for p in c['methods'].get('selected_policies',['every'])]
        if c['methods'].get('temporal_consistency',{}).get('enabled'):expected.append(('selected_temporal','keyframes'))
    groups=[]
    for method,policy in expected:
        repetitions=set();scored=set()
        for row in evaluated:
            spec=json.loads(row['settings'])
            if (spec.get('method'),spec.get('policy'))!=(method,policy):continue
            if method.startswith('selected') and spec.get('selected')!=c['methods']['selected']:continue
            repetitions.add(int(spec['run_number']))
            if row['ate_scaled_m']!='':scored.add(int(spec['run_number']))
        needed=set(range(1,c['methods']['runs']+1))
        groups.append({'method':method,'policy':policy,'attempts':len(repetitions&needed),'scored_runs':len(scored&needed),'complete':needed<=repetitions})
    own=all(r['complete'] for r in groups)
    status=work/'standard_reruns/status.json'
    standard=read(status) if status.exists() else None
    standards_done=bool(standard and standard.get('full_standard_part4_completed'))
    return {'own_attempts_completed':own,'own_configurations':groups,'standard_attempts_completed':standards_done,
            'full_experiment_completed':own and standards_done,'completion_means':'All requested repeated attempts executed; failed/unscored attempts remain explicit and are not counted as successful accuracy scores.'}
