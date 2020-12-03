#!/bin/bash
python ann_training_data.py --TRAIN_STATE_DISTANCES --TRAIN_STATE_UNCERTAINTIES --TRAIN_STATE_PREDICTED_UNITY --BATCH_MODE --INITIAL_BATCH_SAMPLING_METHOD hybrid --BASE_PARAM_STRING batch_hybrid --INITIAL_BATCH_SAMPLING_ARG 200 --OUTPUT_DIRECTORY ../datasets/short_test --USER_QUERY_BUDGET_LIMIT 10 --TRAIN_NR_LEARNING_SAMPLES 10 --TRAIN_PARALLEL_OFFSET 0
python train_ann.py --OUTPUT_DIRECTORY ../datasets/short_test/ --BASE_PARAM_STRING batch_hybrid
python ann_eval_data.py --TRAIN_STATE_DISTANCES --TRAIN_STATE_UNCERTAINTIES --TRAIN_STATE_PREDICTED_UNITY --BATCH_MODE --INITIAL_BATCH_SAMPLING_METHOD hybrid --BASE_PARAM_STRING batch_hybrid --INITIAL_BATCH_SAMPLING_ARG 200 --OUTPUT_DIRECTORY ../datasets/short_test/ --USER_QUERY_BUDGET_LIMIT 10 --TEST_NR_LEARNING_SAMPLES 10 --TEST_PARALLEL_OFFSET 0
python classics.py --OUTPUT_DIRECTORY ../datasets/short_test/ --USER_QUERY_BUDGET_LIMIT 10 --TEST_NR_LEARNING_SAMPLES 10 --TEST_COMPARISONS random uncertainty_max_margin uncertainty_lc uncertainty_entropy --TEST_PARALLEL_OFFSET 0
python plots.py --OUTPUT_DIRECTORY ../datasets/short_test --USER_QUERY_BUDGET_LIMIT 10 --TEST_NR_LEARNING_SAMPLES 10 --TEST_COMPARISONS random uncertainty_max_margin uncertainty_lc uncertainty_entropy --BASE_PARAM_STRING batch_hybrid --FINAL_PICTURE ../datasets/short_test/plots_batch_hybrid/ --PLOT_METRIC acc_auc
