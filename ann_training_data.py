import os
import json
from pathlib import Path

import numpy as np
import pandas as pd
from tabulate import tabulate

from experiments_lib import (
    run_code_experiment,
    run_python_experiment,
    run_parallel_experiment,
    get_config,
)

(
    config,
    shared_arguments,
    _,
    ann_arguments,
    PARENT_OUTPUT_DIRECTORY,
    train_base_param_string,
    _,
) = get_config()

OUTPUT_FILE = PARENT_OUTPUT_DIRECTORY + train_base_param_string
run_parallel_experiment(
    "Creating dataset",
    OUTPUT_FILE=PARENT_OUTPUT_DIRECTORY
    + train_base_param_string
    + "/dataset_creation.csv",
    CLI_COMMAND="python imit_training.py",
    CLI_ARGUMENTS={
        "DATASETS_PATH": "../datasets",
        "CLASSIFIER": config.TRAIN_CLASSIFIER,
        "OUTPUT_DIRECTORY": PARENT_OUTPUT_DIRECTORY + train_base_param_string,
        "DATASET_NAME": "synthetic",
        "SAMPLING": "trained_nn",
        "AMOUNT_OF_PEAKED_OBJECTS": config.TRAIN_AMOUNT_OF_PEAKED_SAMPLES,
        "MAX_AMOUNT_OF_WS_PEAKS": 0,
        "AMOUNT_OF_LEARN_ITERATIONS": 1,
        "AMOUNT_OF_FEATURES": config.TRAIN_AMOUNT_OF_FEATURES,
        "VARIABLE_DATASET": config.TRAIN_VARIABLE_DATASET,
        "NEW_SYNTHETIC_PARAMS": config.TRAIN_NEW_SYNTHETIC_PARAMS,
        "HYPERCUBE": config.TRAIN_HYPERCUBE,
        "STOP_AFTER_MAXIMUM_ACCURACY_REACHED": config.TRAIN_STOP_AFTER_MAXIMUM_ACCURACY_REACHED,
        "GENERATE_NOISE": config.TRAIN_GENERATE_NOISE,
        **ann_arguments,
        **shared_arguments,
    },
    PARALLEL_OFFSET=config.TRAIN_PARALLEL_OFFSET,
    PARALLEL_AMOUNT=config.TRAIN_NR_LEARNING_SAMPLES,
    OUTPUT_FILE_LENGTH=config.TRAIN_NR_LEARNING_SAMPLES,
    RESTART_IF_NOT_ENOUGH_SAMPLES=False,
)