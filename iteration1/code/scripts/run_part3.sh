#!/usr/bin/env bash
# CW1 Part 3: mono, E1, B (sigma 50/80/100), B80+E1, B80 for the first 10 keyframes; 5 runs each on fr3, room0, kitti; then A on kitti
cd /cs/student/projects3/2023/rrajanah/comp0227/COMP0227_26-27/pyslam
DS=/cs/student/projects3/2023/rrajanah/comp0227/datasets
CW=/cs/student/projects3/2023/rrajanah/comp0227/cw1
LOG=$CW/results/logs
N=5
export CW1_SAVE_MAP=1

cfg() { export CW1_METHOD=$1 CW1_SIGMA_PCT=$2 CW1_DEPTH_UNTIL=$3; }

run() {  # run <name> <slam-evaluation arguments>
    name=$1; shift
    echo "$(date '+%F %T') $name: $N runs on $(hostname) [method=$CW1_METHOD sigma=$CW1_SIGMA_PCT until=$CW1_DEPTH_UNTIL]" | tee -a $LOG/part3.log
    CW1_LOG_POINTS=$CW/results/pointlogs/$name pixi run slam-evaluation --features ORB2 "$@" --runs $N >> $LOG/$name.log 2>&1
    folder=$(ls -d results/eval_* | tail -1)
    echo "$name $folder" >> $CW/results/part3_folders.txt
    echo "$(date '+%F %T') $name: done -> $folder" | tee -a $LOG/part3.log
}

do_seq() {  # do_seq <short name> <depth factor> <folder> <settings>
    s=$1; export CW1_DEPTH_FACTOR=$2 CW1_PRED_DEPTH=$3/associations_dav2.txt
    D="--tum $3 --settings $4 --sensor mono"
    cfg ""   100 0;  run ${s}_mono   $D
    cfg E1   100 0;  run ${s}_E1     $D
    cfg B    50  0;  run ${s}_B50    $D
    cfg B    80  0;  run ${s}_B80    $D
    cfg B    100 0;  run ${s}_B100   $D
    cfg B+E1 80  0;  run ${s}_B80E1  $D
    cfg B    80  10; run ${s}_B80u10 $D
}

echo "$(date '+%F %T') start on $(hostname), pySLAM $(git rev-parse --short HEAD) + our changes" | tee -a $LOG/part3.log
do_seq fr3   5000   $DS/rgbd_dataset_freiburg3_long_office_household settings/TUM3.yaml
do_seq room0 6553.5 $DS/replica_room0_tum                            settings/REPLICA.yaml
do_seq kitti 256    $DS/kitti06_tum                                  $CW/configs/KITTI06_depth.yaml
cfg "" 100 0; unset CW1_PRED_DEPTH
run kitti_A --tum $DS/kitti06_tum --settings $CW/configs/KITTI06_depth.yaml --predicted-depth associations_dav2.txt
echo "$(date '+%F %T') all done" | tee -a $LOG/part3.log
