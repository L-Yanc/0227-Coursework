#!/usr/bin/env bash
# COMP0227 CW1 Part 1: 10 runs of each configuration with the C++ core (map saved for map vs depth),
# then 3 runs with the Python core on Replica mono. Progress in cw1/results/logs/part1.log.
cd /cs/student/projects3/2023/rrajanah/comp0227/COMP0227_26-27/pyslam
export CW1_SAVE_MAP=1
LOG=../../cw1/results/logs
FR3="--tum ../../datasets/rgbd_dataset_freiburg3_long_office_household --settings settings/TUM3.yaml"
ROOM0="--tum ../../datasets/replica_room0_tum --settings settings/REPLICA.yaml"

run() {  # run <name> <runs> <slam-evaluation arguments>
    name=$1; runs=$2; shift 2
    echo "$(date '+%F %T') $name: $runs runs" | tee -a $LOG/part1.log
    pixi run slam-evaluation --features ORB2 "$@" --runs $runs >> $LOG/$name.log 2>&1
    folder=$(ls -d results/eval_* | tail -1)
    echo "$name $folder" >> ../../cw1/results/part1_folders.txt
    echo "$(date '+%F %T') $name: done -> $folder" | tee -a $LOG/part1.log
}

echo "$(date '+%F %T') start on $(hostname), pySLAM $(git rev-parse --short HEAD)" | tee -a $LOG/part1.log
run room0_rgbd 10 $ROOM0 --sensor rgbd
run room0_mono 10 $ROOM0 --sensor mono
run fr3_rgbd   10 $FR3 --sensor rgbd
run fr3_mono   10 $FR3 --sensor mono
run kitti      10
export PYSLAM_USE_CPP=false
run py_room0_mono 3 $ROOM0 --sensor mono
unset PYSLAM_USE_CPP
echo "$(date '+%F %T') all done" | tee -a $LOG/part1.log
