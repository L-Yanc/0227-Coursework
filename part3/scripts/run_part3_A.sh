
cd /cs/student/projects3/2023/rrajanah/comp0227/COMP0227_26-27/pyslam
export CW1_SAVE_MAP=1
DS=/cs/student/projects3/2023/rrajanah/comp0227/datasets
LOG=../../cw1/results/logs

run() {  
    name=$1; runs=$2; shift 2
    echo "$(date '+%F %T') $name: $runs runs on $(hostname)" | tee -a $LOG/part3.log
    pixi run slam-evaluation --features ORB2 "$@" --runs $runs >> $LOG/$name.log 2>&1
    folder=$(ls -d results/eval_* | tail -1)
    echo "$name $folder" >> ../../cw1/results/part3_folders.txt
    echo "$(date '+%F %T') $name: done -> $folder" | tee -a $LOG/part3.log
}

echo "$(date '+%F %T') start on $(hostname), pySLAM $(git rev-parse --short HEAD)" | tee -a $LOG/part3.log
run fr3_A   10 --tum $DS/rgbd_dataset_freiburg3_long_office_household --settings settings/TUM3.yaml --predicted-depth associations_dav2.txt
run room0_A 10 --tum $DS/replica_room0_tum --settings settings/REPLICA.yaml --predicted-depth associations_dav2.txt
echo "$(date '+%F %T') all done" | tee -a $LOG/part3.log
