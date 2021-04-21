from active_learning.learner.standard import Learner, get_classifier
from active_learning.weak_supervision.SelfTraining import SelfTraining
import argparse
import numpy as np
import copy
import pandas as pd
import random
from sklearn.metrics import accuracy_score, f1_score
from timeit import default_timer as timer
from typing import List
from active_learning.config import get_active_config
from active_learning.dataStorage import DataStorage
from active_learning.datasets import load_synthetic
from active_learning.logger import init_logger
from active_learning.merge_weak_supervision_label_strategies.MajorityVoteLabelMergeStrategy import (
    MajorityVoteLabelMergeStrategy,
)
from collections import Counter

from active_learning.weak_supervision import SyntheticLabelingFunctions
from active_learning.weak_supervision.BaseWeakSupervision import BaseWeakSupervision

config: argparse.Namespace = get_active_config()  # type: ignore

# python ws_accuracy_experiment.py --OUTPUT_DIRECTORY _experiment_resultss/tmp --DATASET_NAME synthetic --AMOUNT_OF_FEATURES -1 --RANDOM_SEED 0

# -2 means that a true random seed is used, all other numbers use the provided CLI argument random_seed
if config.RANDOM_SEED == -2:
    random_but_not_random = True
else:
    random_but_not_random = False


init_logger(config.LOG_FILE)

if random_but_not_random:
    config.RANDOM_SEED = random.randint(0, 2147483647)
    np.random.seed(config.RANDOM_SEED)
    random.seed(config.RANDOM_SEED)


def evaluate_and_print_prediction(Y_pred, Y_true, title):
    acc = accuracy_score(Y_true, Y_pred)
    f1 = f1_score(Y_true, Y_pred, average="weighted")
    c = Counter(Y_pred)

    print(
        "{:<60} Acc: {:>6.2%} F1: {:>6.2%} MC: {:>3}-{:>4.1%}".format(
            title,
            acc,
            f1,
            c.most_common(1)[0][0],
            c.most_common(1)[0][1] / len(Y_pred),
        )
    )


df, synthetic_creation_args = load_synthetic(
    config.RANDOM_SEED,
    config.NEW_SYNTHETIC_PARAMS,
    config.VARIABLE_DATASET,
    config.AMOUNT_OF_FEATURES,
    config.HYPERCUBE,
    config.GENERATE_NOISE,
)

data_storage: DataStorage = DataStorage(df=df, TEST_FRACTION=config.TEST_FRACTION)


learner = get_classifier("RF", random_state=config.RANDOM_SEED)

mask = data_storage.labeled_mask
learner.fit(data_storage.X[mask], data_storage.Y_merged_final[mask])


ws_list: List[BaseWeakSupervision] = [
    SyntheticLabelingFunctions(X=data_storage.X, Y=data_storage.exp_Y)
    for i in range(0, config.AMOUNT_OF_SYNTHETIC_LABELLING_FUNCTIONS)
]  # type: ignore


# tweak to do more than one iteration of self training!
""" ws_list.append(SelfTraining(0.99, 0.99))
ws_list.append(SelfTraining(0.9, 0.9))
ws_list.append(SelfTraining(0.8, 0.8))
ws_list.append(SelfTraining(0.7, 0.7)) """

# add label propagation

for ws in ws_list:
    # calculate f1 and acc for ws on test AND train dataset
    Y_pred = ws.get_labels(data_storage.test_mask, data_storage, learner)
    evaluate_and_print_prediction(
        data_storage.exp_Y[data_storage.test_mask], Y_pred, ws.identifier
    )


data_storage.set_weak_supervisions(ws_list, MajorityVoteLabelMergeStrategy())
data_storage.generate_weak_labels(learner, mask=data_storage.test_mask)

# Only Majority Vote, no classifier
print()
Y_pred = data_storage.Y_merged_final[data_storage.test_mask]
evaluate_and_print_prediction(
    Y_pred, data_storage.exp_Y[data_storage.test_mask], "Majority Vote"
)


# compute the 50/100/200/500 worst wrongly classified samples -> classify them correctly (aka. fake active learning) -> is there really room for improvement after falsely applyed WS??

# apply it to the train_set

# trained on WS + Minimal AL


def train_and_evaluate(title, original_data_storage, WEIGHTS=0, WS=True):
    data_storage = copy.deepcopy(original_data_storage)
    learner = get_classifier("RF", random_state=config.RANDOM_SEED)
    data_storage.generate_weak_labels(learner)

    if WEIGHTS != 0:
        weights = []
        for indice in data_storage.weakly_combined_mask:
            if indice in data_storage.labeled_mask:
                weights.append(WEIGHTS)
            else:
                weights.append(1)
    else:
        weights = None
    if WS:
        mask = data_storage.weakly_combined_mask
    else:
        mask = data_storage.labeled_mask
    learner.fit(
        data_storage.X[mask],
        data_storage.Y_merged_final[mask],
        sample_weight=weights,
    )
    Y_pred = learner.predict(data_storage.X[data_storage.test_mask])

    Y_true = data_storage.exp_Y[data_storage.test_mask]

    evaluate_and_print_prediction(Y_pred, Y_true, title)


def test_one_labeled_set(original_data_storage, label_strategy="start_set", param=5):
    data_storage = copy.deepcopy(original_data_storage)

    if label_strategy == "random":
        random_sample_ids = np.random.choice(
            data_storage.unlabeled_mask,
            size=param,
            replace=False,
        )

        data_storage.label_samples(
            random_sample_ids, data_storage.exp_Y[random_sample_ids], "AL"
        )
    print()
    print(label_strategy + ": ", len(data_storage.labeled_mask))
    train_and_evaluate("RF No WS", data_storage, WS=False)
    train_and_evaluate("RF No Weights", data_storage)
    train_and_evaluate("RF Weihgt 10", data_storage, WEIGHTS=10)
    train_and_evaluate("RF Weihgt 50", data_storage, WEIGHTS=50)
    train_and_evaluate("RF Weihgt 100", data_storage, WEIGHTS=100)
    train_and_evaluate("RF Weihgt 1000", data_storage, WEIGHTS=1000)


test_one_labeled_set(data_storage, label_strategy="start_set")
test_one_labeled_set(data_storage, label_strategy="random", param=5)
test_one_labeled_set(data_storage, label_strategy="random", param=10)
test_one_labeled_set(data_storage, label_strategy="random", param=25)
test_one_labeled_set(data_storage, label_strategy="random", param=50)
test_one_labeled_set(data_storage, label_strategy="random", param=100)
test_one_labeled_set(data_storage, label_strategy="random", param=200)
# randomly select samples to be labeled

# wrong_mask = np.logical_not(np.array_equal(Y_pred, Y_true))

# print(data_storage.Y_merged_final[wrong_mask])
# print(data_storage.exp_Y[wrong_mask])

# calculate acc/f1 a) mit weakly_labeled b) ohne weakly labeled c) mit gewichten d) mit höheren gewichten e) mit mehr echten labels (best-case AL, siehe unten!)
# calculate acc/f1 now and before ONLY on those without abstain!, but add "coverage" to the WS LF
# a) get those samples, who are least covered by the LF
# b) get those samples, where the classification is wrong by the merged LFs
# c) get those samples, with the greatest disagreement among the LFs