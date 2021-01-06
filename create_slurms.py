import glob
import stat
from jinja2 import Template
import argparse
import datetime
import os
import random
import sys
import threading
import warnings

import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("--TITLE")
parser.add_argument("--TEST_NR_LEARNING_SAMPLES", default=1000, type=int)
parser.add_argument("--TRAIN_NR_LEARNING_SAMPLES", default=1000, type=int)
parser.add_argument("--ITERATIONS_PER_BATCH", default=10, type=int)
parser.add_argument("--OUT_DIR", default="slurms2")
parser.add_argument("--WS_DIR", default="/lustre/ssd/ws/s5968580-IL_TD2")
parser.add_argument(
    "--DATASET_DIR", default="/lustre/ssd/ws/s5968580-IL_TD2/single_vs_batch"
)
parser.add_argument("--WITH_HYPER_SEARCH", action="store_true")
parser.add_argument("--WITH_CLASSICS", action="store_true")
parser.add_argument("--WITH_PLOTS", action="store_true")
parser.add_argument("--WITH_EVAL", action="store_true")
parser.add_argument("--SLURM", action="store_true")
parser.add_argument("--INITIAL_BATCH_SAMPLING_ARG", type=int, default=200)
parser.add_argument("--INITIAL_BATCH_SAMPLING_HYBRID_UNCERT", type=float, default=0.2)
parser.add_argument("--INITIAL_BATCH_SAMPLING_HYBRID_FURTHEST", type=float, default=0.2)
parser.add_argument(
    "--INITIAL_BATCH_SAMPLING_HYBRID_FURTHEST_LAB", type=float, default=0.2
)
parser.add_argument(
    "--INITIAL_BATCH_SAMPLING_HYBRID_PRED_UNITY", type=float, default=0.2
)
parser.add_argument("--TRAIN_STATE_DISTANCES", action="store_true")
parser.add_argument("--TRAIN_STATE_UNCERTAINTIES", action="store_true")
parser.add_argument("--TRAIN_STATE_PREDICTED_UNITY", action="store_true")
parser.add_argument("--TRAIN_STATE_DISTANCES_LAB", action="store_true")
parser.add_argument("--STATE_INCLUDE_NR_FEATURES", action="store_true")
parser.add_argument("--DISTANCE_METRIC", default="euclidean")

#  wenn HYBRID -> HYBRID namen so ändern, dass die Werte von oben an den titel angefügt werden :)

config = parser.parse_args()

if len(sys.argv[:-1]) == 0:
    parser.print_help()
    parser.exit()


INITIAL_BATCH_SAMPLING_METHOD = config.TITLE
if config.TITLE == "hybrid":
    config.TITLE = (
        "hybrid-"
        + str(config.INITIAL_BATCH_SAMPLING_ARG)
        + "#"
        + str(config.INITIAL_BATCH_SAMPLING_HYBRID_FURTHEST)
        + "_"
        + str(config.INITIAL_BATCH_SAMPLING_HYBRID_FURTHEST_LAB)
        + "_"
        + str(config.INITIAL_BATCH_SAMPLING_HYBRID_PRED_UNITY)
        + "_"
        + str(config.INITIAL_BATCH_SAMPLING_HYBRID_UNCERT)
    )

if config.TITLE == "single":
    BATCH_MODE = ""
    INITIAL_BATCH_SAMPLING_METHOD = "furthest"
    ADDITIONAL_TRAINING_STATE_ARGS = ""
elif config.TITLE == "single_full":
    BATCH_MODE = ""
    INITIAL_BATCH_SAMPLING_METHOD = "furthest"
    ADDITIONAL_TRAINING_STATE_ARGS = " --TRAIN_STATE_ARGSECOND_PROBAS --TRAIN_STATE_ARGTHIRD_PROBAS --TRAIN_STATE_DISTANCES_LAB --TRAIN_STATE_DISTANCES_UNLAB "
    config.INITIAL_BATCH_SAMPLING_ARG = 10
elif config.TITLE == "single_full_f1":
    BATCH_MODE = ""
    INITIAL_BATCH_SAMPLING_METHOD = "furthest"
    ADDITIONAL_TRAINING_STATE_ARGS = " --TRAIN_STATE_ARGSECOND_PROBAS --TRAIN_STATE_ARGTHIRD_PROBAS --TRAIN_STATE_DISTANCES_LAB --TRAIN_STATE_DISTANCES_UNLAB "
elif config.TITLE == "single_full_10":
    BATCH_MODE = ""
    INITIAL_BATCH_SAMPLING_METHOD = "furthest"
    config.INITIAL_BATCH_SAMPLING_ARG = 10
    ADDITIONAL_TRAINING_STATE_ARGS = " --TRAIN_STATE_ARGSECOND_PROBAS --TRAIN_STATE_ARGTHIRD_PROBAS --TRAIN_STATE_DISTANCES_LAB --TRAIN_STATE_DISTANCES_UNLAB "
elif config.TITLE == "single_full_lab":
    BATCH_MODE = ""
    INITIAL_BATCH_SAMPLING_METHOD = "furthest"
    ADDITIONAL_TRAINING_STATE_ARGS = (
        " --TRAIN_STATE_ARGSECOND_PROBAS --TRAIN_STATE_DISTANCES_LAB "
    )
elif config.TITLE == "single_full_unlab":
    BATCH_MODE = ""
    INITIAL_BATCH_SAMPLING_METHOD = "furthest"
    ADDITIONAL_TRAINING_STATE_ARGS = (
        " --TRAIN_STATE_ARGSECOND_PROBAS --TRAIN_STATE_DISTANCES_UNLAB "
    )
else:
    BATCH_MODE = "--BATCH_MODE"
    ADDITIONAL_TRAINING_STATE_ARGS = ""
    if config.TRAIN_STATE_DISTANCES:
        ADDITIONAL_TRAINING_STATE_ARGS += " --TRAIN_STATE_DISTANCES"
        config.TITLE += "_D"
    if config.TRAIN_STATE_UNCERTAINTIES:
        ADDITIONAL_TRAINING_STATE_ARGS += " --TRAIN_STATE_UNCERTAINTIES"
        config.TITLE += "_U"
    if config.TRAIN_STATE_PREDICTED_UNITY:
        ADDITIONAL_TRAINING_STATE_ARGS += " --TRAIN_STATE_PREDICTED_UNITY"
        config.TITLE += "_P"
    if config.TRAIN_STATE_DISTANCES_LAB:
        ADDITIONAL_TRAINING_STATE_ARGS += " --TRAIN_STATE_DISTANCES_LAB"
        config.TITLE += "_DL"

if config.STATE_INCLUDE_NR_FEATURES:
    ADDITIONAL_TRAINING_STATE_ARGS += " --STATE_INCLUDE_NR_FEATURES"

if config.DISTANCE_METRIC == "cosine":
    config.TITLE += "_cos"
if config.STATE_INCLUDE_NR_FEATURES:
    config.TITLE += "_nrf"

config.OUT_DIR = config.OUT_DIR + "/" + config.TITLE

if config.SLURM:
    slurm_common = Template(
        """#!/bin/bash{% if array %}{% set THREADS = 1 %}{% set MEMORY = 2583 %}{% endif %}
#SBATCH --time=23:59:59   # walltime
#SBATCH --nodes=1  
#SBATCH --ntasks=1      
#SBATCH --tasks-per-node=1
#SBATCH --cpus-per-task={{ THREADS }} 
#SBATCH --mem-per-cpu={{ MEMORY }}M   # memory per CPU core
#SBATCH --mail-user=julius.gonsior@tu-dresden.de   
#SBATCH --mail-type=BEGIN,END,FAIL,REQUEUE,TIME_LIMIT
#SBATCH -A p_ml_il
#SBATCH --output {{WS_DIR}}/slurm_{{TITLE}}_{{PYTHON_FILE}}_out.txt
#SBATCH --error {{WS_DIR}}/slurm_{{TITLE}}_{{PYTHON_FILE}}_error.txt
{% if array %}#SBATCH --array {{START}}-{{END}}{% endif %}

# Set the max number of threads to use for programs using OpenMP. Should be <= ppn. Does nothing if the program doesn't use OpenMP.
export OMP_NUM_THREADS=$SLURM_CPUS_ON_NODE

{% if array %}i=$(( {{OFFSET}} + $SLURM_ARRAY_TASK_ID * {{ITERATIONS_PER_BATCH}} )){% endif %}

MPLCONFIGDIR={{WS_DIR}}/cache python3 -m pipenv run python {{WS_DIR}}/imitating-weakal/{{PYTHON_FILE}}.py {{ CLI_ARGS }}
exit 0
    """
    )
else:
    config.OUT_DIR = "fake_slurms"
    os.makedirs(config.OUT_DIR, exist_ok=True)
    slurm_common = Template("{{PYTHON_FILE}}.py {{ CLI_ARGS }}")


submit_jobs = Template(
    """#!/bin/bash
ann_training_data_id=$(sbatch --parsable {{WS_DIR}}/imitating-weakal/{{OUT_DIR}}/ann_training_data.slurm)
train_ann_id=$(sbatch --parsable --dependency=afterok:$ann_training_data_id {{WS_DIR}}/imitating-weakal/{{OUT_DIR}}/train_ann.slurm)
{%if WITH_HYPER_SEARCH %}hyper_search_id=$(sbatch --parsable --dependency=afterok:$train_ann_id {{WS_DIR}}/imitating-weakal/{{OUT_DIR}}/hyper_search.slurm){% endif %}
{%if WITH_EVAL %}create_ann_eval_id=$(sbatch --parsable --dependency=afterok:$ann_training_data_id:$train_ann_id{%if WITH_HYPER_SEARCH %}:$hyper_search_id{% endif %} {{WS_DIR}}/imitating-weakal//{{OUT_DIR}}/ann_eval_data.slurm){% endif %}
{%if WITH_CLASSICS %}classics_id=$(sbatch --parsable {{WS_DIR}}/imitating-weakal//{{OUT_DIR}}/classics.slurm){% endif %}
{%if WITH_PLOTS %}plots_id=$(sbatch --parsable --dependency=afterok:$ann_training_data_id{%if WITH_EVAL %}:$create_ann_eval_id{% endif %}{%if WITH_CLASSICS %}:$classics_id{% endif %} {{WS_DIR}}/imitating-weakal//{{OUT_DIR}}/plots.slurm){% endif %}
exit 0
"""
)

if not os.path.exists(config.OUT_DIR):
    os.makedirs(config.OUT_DIR)

with open(config.OUT_DIR + "/ann_training_data.slurm", "w") as f:
    START = 0
    END = int(config.TRAIN_NR_LEARNING_SAMPLES / config.ITERATIONS_PER_BATCH) - 1
    f.write(
        slurm_common.render(
            WS_DIR=config.WS_DIR,
            TITLE=config.TITLE,
            PYTHON_FILE="ann_training_data",
            array=True,
            START=START,
            END=END,
            ITERATIONS_PER_BATCH=config.ITERATIONS_PER_BATCH,
            OFFSET=0,
            CLI_ARGS=" "
            + str(BATCH_MODE)
            + " --INITIAL_BATCH_SAMPLING_METHOD "
            + str(INITIAL_BATCH_SAMPLING_METHOD)
            + " --BASE_PARAM_STRING batch_"
            + config.TITLE
            + " --INITIAL_BATCH_SAMPLING_ARG "
            + str(config.INITIAL_BATCH_SAMPLING_ARG)
            + " --OUTPUT_DIRECTORY "
            + config.DATASET_DIR
            + " --USER_QUERY_BUDGET_LIMIT 50 --TRAIN_NR_LEARNING_SAMPLES "
            + str(config.ITERATIONS_PER_BATCH)
            + " --INITIAL_BATCH_SAMPLING_HYBRID_UNCERT "
            + str(config.INITIAL_BATCH_SAMPLING_HYBRID_UNCERT)
            + " --INITIAL_BATCH_SAMPLING_HYBRID_PRED_UNITY "
            + str(config.INITIAL_BATCH_SAMPLING_HYBRID_PRED_UNITY)
            + " --INITIAL_BATCH_SAMPLING_HYBRID_FURTHEST "
            + str(config.INITIAL_BATCH_SAMPLING_HYBRID_FURTHEST)
            + " --INITIAL_BATCH_SAMPLING_HYBRID_FURTHEST_LAB "
            + str(config.INITIAL_BATCH_SAMPLING_HYBRID_FURTHEST_LAB)
            + ADDITIONAL_TRAINING_STATE_ARGS
            + " --TRAIN_PARALLEL_OFFSET $i"
            + " --DISTANCE_METRIC "
            + str(config.DISTANCE_METRIC),
        )
    )

if config.WITH_HYPER_SEARCH:
    with open(config.OUT_DIR + "/hyper_search.slurm", "w") as f:
        f.write(
            slurm_common.render(
                WS_DIR=config.WS_DIR,
                TITLE=config.TITLE,
                PYTHON_FILE="train_lstm",
                array=False,
                THREADS=24,
                MEMORY=5250,
                CLI_ARGS="--DATA_PATH "
                + config.DATASET_DIR
                + "/batch_"
                + config.TITLE
                + " --STATE_ENCODING listwise --TARGET_ENCODING binary --HYPER_SEARCH --N_ITER 300 ",
            )
        )


with open(config.OUT_DIR + "/train_ann.slurm", "w") as f:
    if config.WITH_HYPER_SEARCH:
        hypered_appendix = " --HYPER_SEARCHED"
    else:
        hypered_appendix = ""
    f.write(
        slurm_common.render(
            WS_DIR=config.WS_DIR,
            TITLE=config.TITLE,
            PYTHON_FILE="train_ann",
            array=False,
            THREADS=8,
            MEMORY=5250,
            CLI_ARGS="--OUTPUT_DIRECTORY "
            + config.DATASET_DIR
            + "/ --BASE_PARAM_STRING batch_"
            + config.TITLE
            + hypered_appendix,
        )
    )

if config.WITH_EVAL:
    with open(config.OUT_DIR + "/ann_eval_data.slurm", "w") as f:
        START = 0
        END = int(config.TEST_NR_LEARNING_SAMPLES / config.ITERATIONS_PER_BATCH) - 1
        f.write(
            slurm_common.render(
                WS_DIR=config.WS_DIR,
                TITLE=config.TITLE,
                PYTHON_FILE="ann_eval_data",
                array=True,
                START=START,
                END=END,
                OFFSET=100000,
                ITERATIONS_PER_BATCH=config.ITERATIONS_PER_BATCH,
                CLI_ARGS=" "
                + BATCH_MODE
                + " --INITIAL_BATCH_SAMPLING_METHOD "
                + INITIAL_BATCH_SAMPLING_METHOD
                + " --BASE_PARAM_STRING batch_"
                + config.TITLE
                + " --INITIAL_BATCH_SAMPLING_ARG "
                + str(config.INITIAL_BATCH_SAMPLING_ARG)
                + " --OUTPUT_DIRECTORY "
                + config.DATASET_DIR
                + "/ --USER_QUERY_BUDGET_LIMIT 50 --TEST_NR_LEARNING_SAMPLES "
                + str(config.ITERATIONS_PER_BATCH)
                + " --INITIAL_BATCH_SAMPLING_HYBRID_UNCERT "
                + str(config.INITIAL_BATCH_SAMPLING_HYBRID_UNCERT)
                + " --INITIAL_BATCH_SAMPLING_HYBRID_PRED_UNITY "
                + str(config.INITIAL_BATCH_SAMPLING_HYBRID_PRED_UNITY)
                + " --INITIAL_BATCH_SAMPLING_HYBRID_FURTHEST "
                + str(config.INITIAL_BATCH_SAMPLING_HYBRID_FURTHEST)
                + " --INITIAL_BATCH_SAMPLING_HYBRID_FURTHEST_LAB "
                + str(config.INITIAL_BATCH_SAMPLING_HYBRID_FURTHEST_LAB)
                + ADDITIONAL_TRAINING_STATE_ARGS
                + " --TEST_PARALLEL_OFFSET $i"
                + " --DISTANCE_METRIC "
                + str(config.DISTANCE_METRIC),
            )
        )

if config.WITH_CLASSICS:
    with open(config.OUT_DIR + "/classics.slurm", "w") as f:
        START = 0
        END = int(config.TEST_NR_LEARNING_SAMPLES / config.ITERATIONS_PER_BATCH) - 1
        f.write(
            slurm_common.render(
                WS_DIR=config.WS_DIR,
                TITLE=config.TITLE,
                PYTHON_FILE="classics",
                array=True,
                START=START,
                END=END,
                OFFSET=100000,
                ITERATIONS_PER_BATCH=config.ITERATIONS_PER_BATCH,
                CLI_ARGS="--OUTPUT_DIRECTORY "
                + config.DATASET_DIR
                + "/ --USER_QUERY_BUDGET_LIMIT 50 --TEST_NR_LEARNING_SAMPLES "
                + str(config.ITERATIONS_PER_BATCH)
                + " --TEST_COMPARISONS random uncertainty_max_margin uncertainty_lc uncertainty_entropy --TEST_PARALLEL_OFFSET $i",
            )
        )

if config.WITH_PLOTS:
    with open(config.OUT_DIR + "/plots.slurm", "w") as f:
        f.write(
            slurm_common.render(
                WS_DIR=config.WS_DIR,
                TITLE=config.TITLE,
                PYTHON_FILE="plots",
                array=False,
                THREADS=2,
                MEMORY=5250,
                TEST_NR_LEARNING_SAMPLES=config.TEST_NR_LEARNING_SAMPLES,
                CLI_ARGS="--OUTPUT_DIRECTORY "
                + config.DATASET_DIR
                + " --USER_QUERY_BUDGET_LIMIT 50 --TEST_NR_LEARNING_SAMPLES "
                + str(config.TEST_NR_LEARNING_SAMPLES)
                + " --TEST_COMPARISONS random uncertainty_max_margin uncertainty_lc uncertainty_entropy --BASE_PARAM_STRING batch_"
                + config.TITLE
                + " --FINAL_PICTURE "
                + config.DATASET_DIR
                + "/plots_batch_"
                + config.TITLE
                + "/ --PLOT_METRIC acc_auc",
            )
        )

if config.SLURM:
    with open(config.OUT_DIR + "/submit_jobs.sh", "w") as f:
        f.write(
            submit_jobs.render(
                WS_DIR=config.WS_DIR,
                OUT_DIR=config.OUT_DIR,
                TITLE=config.TITLE,
                WITH_HYPER_SEARCH=config.WITH_HYPER_SEARCH,
                WITH_CLASSICS=config.WITH_CLASSICS,
                WITH_PLOTS=config.WITH_PLOTS,
                WITH_EVAL=config.WITH_EVAL,
            )
        )
else:
    # open all fake slurms and concat them into a single bash file
    submit_content = "#!/bin/bash\n"
    sort_order = {
        "ann_training_data.slurm": 0,
        "hyper_search.slurm": 1,
        "train_ann.slurm": 2,
        "ann_eval_data.slurm": 3,
        "classics.slurm": 4,
        "plots.slurm": 5,
    }
    for csv_file in sorted(
        list(glob.glob(config.OUT_DIR + "/*.slurm")),
        key=lambda v: sort_order[v.split("/")[-1]],
    ):
        with open(csv_file, "r") as f:
            content = f.read()
            content = content.replace("$i", "0")
            submit_content += "python " + content + "\n"
        os.remove(csv_file)
    with open(config.OUT_DIR + "/submit_jobs.sh", "w") as f:
        f.write(submit_content)
st = os.stat(config.OUT_DIR + "/submit_jobs.sh")
os.chmod(config.OUT_DIR + "/submit_jobs.sh", st.st_mode | stat.S_IEXEC)
