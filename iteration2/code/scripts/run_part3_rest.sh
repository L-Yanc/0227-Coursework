#!/usr/bin/env bash
# rest of the Part 3 batch (skate-l went down ~20:00 on 9 Nov): room0 mono again, room0 B80+E1 and B80u10, all KITTI configs, A on KITTI
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

echo "$(date '+%F %T') rest of batch, start on $(hostname)" | tee -a $LOG/part3.log

export CW1_DEPTH_FACTOR=6553.5 CW1_PRED_DEPTH=$DS/replica_room0_tum/associations_dav2.txt
D="--tum $DS/replica_room0_tum --settings settings/REPLICA.yaml --sensor mono"
cfg ""   100 0;  run room0_mono_rest $D
cfg B+E1 80  0;  run room0_B80E1     $D
cfg B    80  10; run room0_B80u10    $D

export CW1_DEPTH_FACTOR=256 CW1_PRED_DEPTH=$DS/kitti06_tum/associations_dav2.txt
D="--tum $DS/kitti06_tum --settings $CW/configs/KITTI06_depth.yaml --sensor mono"
cfg ""   100 0;  run kitti_mono   $D
cfg E1   100 0;  run kitti_E1     $D
cfg B    50  0;  run kitti_B50    $D
cfg B    80  0;  run kitti_B80    $D
cfg B    100 0;  run kitti_B100   $D
cfg B+E1 80  0;  run kitti_B80E1  $D
cfg B    80  10; run kitti_B80u10 $D

cfg "" 100 0; unset CW1_PRED_DEPTH
run kitti_A --tum $DS/kitti06_tum --settings $CW/configs/KITTI06_depth.yaml --predicted-depth associations_dav2.txt
echo "$(date '+%F %T') all done" | tee -a $LOG/part3.log
