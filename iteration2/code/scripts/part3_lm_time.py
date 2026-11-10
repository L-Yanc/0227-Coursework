# median local mapping time per keyframe for each config (logs/local_mapping.log)
import glob, os, re, statistics, sys
for lst in sys.argv[1:]:
    for line in open(lst):
        if not line.strip():
            continue
        config, folder = line.split()[:2]
        per_mode = {}
        for log in glob.glob(os.path.join(folder, "*", "*", "iteration_*", "logs", "local_mapping.log")):
            mode = log.split(os.sep)[-5]
            t = [float(x) for x in re.findall(r"local mapping elapsed time: ([0-9.eE+-]+)", open(log, errors="ignore").read())]
            if t:
                per_mode.setdefault(mode, []).append((statistics.median(t), len(t)))
        for mode, v in per_mode.items():
            print(f"{config:16s} {mode:12s} runs {len(v):2d}  ms per KF {1000*statistics.median(a for a, _ in v):7.1f}  LM calls {statistics.median(b for _, b in v):6.0f}")
