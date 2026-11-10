#!/usr/bin/env bash
# Part 3 extra: E1 trust setting (sigma 50 and 80) with a fresh mono per sequence, and A on KITTI (pseudo rgbd from associations_dav2.txt)
cd /cs/student/projects3/2023/rrajanah/comp0227/COMP0227_26-27/pyslam
DS=/cs/student/projects3/2023/rrajanah/comp0227/datasets
CW=/cs/student/projects3/2023/rrajanah/comp0227/cw1
LOG=$CW/results/logs
N=5
export CW1_SAVE_MAP=1

cfg() { export CW1_METHOD=$1 CW1_SIGMA_PCT=$2 CW1_DEPTH_UNTIL=$3; }

run() {  # run <name> <slam-evaluation arguments>
    name=$1; shift
    before=$(ls -d results/eval_* | tail -1)
    echo "$(date '+%F %T') $name: $N runs on $(hostname) [method=$CW1_METHOD sigma=$CW1_SIGMA_PCT until=$CW1_DEPTH_UNTIL]" | tee -a $LOG/part3.log
    CW1_LOG_POINTS=$CW/results/pointlogs/$name pixi run slam-evaluation --features ORB2 "$@" --runs $N >> $LOG/$name.log 2>&1
    folder=$(ls -d results/eval_* | tail -1)
    if [ "$folder" = "$before" ]; then echo "$(date '+%F %T') $name: FAILED, no new folder" | tee -a $LOG/part3.log; return; fi
    echo "$name $folder" >> $CW/results/part3_folders.txt
    echo "$(date '+%F %T') $name: done -> $folder" | tee -a $LOG/part3.log
}

do_seq() {  # do_seq <short name> <depth factor> <folder> <settings>
    s=$1; export CW1_DEPTH_FACTOR=$2 CW1_PRED_DEPTH=$3/associations_dav2.txt
    D="--tum $3 --settings $4 --sensor mono"
    cfg ""  100 0; run ${s}_mono_x  $D
    cfg E1  50  0; run ${s}_E1s50   $D
    cfg E1  80  0; run ${s}_E1s80   $D
}

echo "$(date '+%F %T') extra batch, start on $(hostname)" | tee -a $LOG/part3.log
do_seq fr3   5000   $DS/rgbd_dataset_freiburg3_long_office_household settings/TUM3.yaml
do_seq room0 6553.5 $DS/replica_room0_tum                            settings/REPLICA.yaml
do_seq kitti 256    $DS/kitti06_tum                                  $CW/configs/KITTI06_depth.yaml
cfg "" 100 0; unset CW1_PRED_DEPTH
run kitti_A --tum $DS/kitti06_tum --settings $CW/configs/KITTI06_depth.yaml --associations associations_dav2.txt --sensor rgbd
echo "$(date '+%F %T') all done" | tee -a $LOG/part3.log
