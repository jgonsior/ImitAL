#!/bin/bash
ann_training_data_id=$(sbatch --parsable /lustre/ssd/ws/s5968580-IL_TD2/imitating-weakal/slurms2/single_full_unlab/ann_training_data.slurm)
train_ann_id=$(sbatch --parsable --dependency=afterok:$ann_training_data_id /lustre/ssd/ws/s5968580-IL_TD2/imitating-weakal/slurms2/single_full_unlab/train_ann.slurm)

create_ann_eval_id=$(sbatch --parsable --dependency=afterok:$ann_training_data_id:$train_ann_id /lustre/ssd/ws/s5968580-IL_TD2/imitating-weakal//slurms2/single_full_unlab/ann_eval_data.slurm)

plots_id=$(sbatch --parsable --dependency=afterok:$ann_training_data_id:$create_ann_eval_id /lustre/ssd/ws/s5968580-IL_TD2/imitating-weakal//slurms2/single_full_unlab/plots.slurm)
exit 0