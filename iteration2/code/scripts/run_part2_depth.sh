#!/usr/bin/env bash
# COMP0227 CW1 Part 2: Depth Anything V2 (indoor, large) on every frame of fr3 and room0. Progress in cw1/results/logs/part2.log
cd /cs/student/projects3/2023/rrajanah/comp0227/COMP0227_26-27/pyslam
DS=/cs/student/projects3/2023/rrajanah/comp0227/datasets
LOG=../../cw1/results/logs
pred() {  # pred <name> <depth-prediction arguments>
    name=$1; shift
    echo "$(date '+%F %T') $name: start on $(hostname)" | tee -a $LOG/part2.log
    pixi run -e depth depth-prediction --method DEPTH_ANYTHING_V2 "$@" --save dav2 --headless 2>&1 | tee $LOG/$name.log
    rc=${PIPESTATUS[0]}
    echo "$(date '+%F %T') $name: done (exit $rc)" | tee -a $LOG/part2.log
}
pred fr3_dav2   --tum $DS/rgbd_dataset_freiburg3_long_office_household --settings settings/TUM3.yaml
pred room0_dav2 --tum $DS/replica_room0_tum --settings settings/REPLICA.yaml
echo "$(date '+%F %T') all done" | tee -a $LOG/part2.log
