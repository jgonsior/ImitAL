from scipy.stats import spearmanr, kendalltau
from sklearn.preprocessing import MinMaxScaler
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from joblib import Parallel, delayed, parallel_backend
import random
from itertools import chain
import copy
import numpy as np
from scipy.stats import entropy
from sklearn.metrics import accuracy_score, mean_squared_error
from ..activeLearner import ActiveLearner
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import os


def _future_peak(
    unlabeled_sample_indice,
    weak_supervision_label_sources,
    data_storage,
    clf,
    MAX_AMOUNT_OF_WS_PEAKS,
):
    copy_of_data_storage = copy.deepcopy(data_storage)
    copy_of_classifier = copy.deepcopy(clf)

    copy_of_data_storage.label_samples(
        pd.Index([unlabeled_sample_indice]),
        [copy_of_data_storage.train_unlabeled_Y.loc[unlabeled_sample_indice]["label"]],
        "P",
    )
    copy_of_classifier.fit(
        copy_of_data_storage.train_labeled_X,
        copy_of_data_storage.train_labeled_Y["label"].to_list(),
    )
    for labelSource in weak_supervision_label_sources:
        labelSource.data_storage = copy_of_data_storage

    # what would happen if we apply WS after this one?
    for i in range(0, MAX_AMOUNT_OF_WS_PEAKS):
        for labelSource in weak_supervision_label_sources:
            (Y_query, query_indices, source,) = labelSource.get_labeled_samples()

            if Y_query is not None:
                break
        if Y_query is None:
            ws_still_applicable = False
            continue

        copy_of_data_storage.label_samples(query_indices, Y_query, source)

        copy_of_classifier.fit(
            copy_of_data_storage.train_labeled_X,
            copy_of_data_storage.train_labeled_Y["label"].to_list(),
        )

    Y_pred = copy_of_classifier.predict(copy_of_data_storage.train_unlabeled_X)

    accuracy_with_that_label = accuracy_score(
        Y_pred, copy_of_data_storage.train_unlabeled_Y["label"].to_list()
    )

    #  print(
    #      "Testing out : {}, train acc: {}".format(
    #          unlabeled_sample_indice, accuracy_with_that_label
    #      )
    #  )
    return accuracy_with_that_label


class ImitationLearner(ActiveLearner):
    def set_amount_of_peaked_objects(self, amount_of_peaked_objects):
        self.amount_of_peaked_objects = amount_of_peaked_objects

    def init_sampling_classifier(self, DATA_PATH, USE_OPTIMAL_ONLY, TRAIN_ONCE):
        self.USE_OPTIMAL_ONLY = USE_OPTIMAL_ONLY
        self.TRAIN_ONCE = TRAIN_ONCE
        if not USE_OPTIMAL_ONLY:
            os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"  # see issue #152
            os.environ["CUDA_VISIBLE_DEVICES"] = ""

            model = keras.Sequential(
                [
                    layers.Dense(
                        2 * self.amount_of_peaked_objects,
                        input_shape=(2 * self.amount_of_peaked_objects,),
                        activation="relu",
                    ),
                    *[
                        layers.Dense(
                            4 * self.amount_of_peaked_objects, activation="relu"
                        )
                        for _ in range(1, 5)
                    ],
                    layers.Dense(4 * self.amount_of_peaked_objects, activation="relu"),
                    layers.Dense(
                        self.amount_of_peaked_objects, activation="softmax"
                    ),  # muss das softmax sein?!
                ]
            )

            def tau_loss(Y_true, Y_pred):
                return tf.py_function(
                    kendalltau,
                    [tf.cast(Y_pred, tf.float32), tf.cast(Y_true, tf.float32)],
                    Tout=tf.float32,
                )

            def spearman_loss(Y_true, Y_pred):
                return tf.py_function(
                    spearmanr,
                    [tf.cast(Y_pred, tf.float32), tf.cast(Y_true, tf.float32)],
                    Tout=tf.float32,
                )

            model.compile(
                loss=spearman_loss,
                optimizer="adam",
                metrics=["MeanSquaredError", "accuracy", tau_loss],
            )

            #  print(model.summary())
            self.sampling_classifier = model

        # check if states and optimal policies file got provided or if we need to create a new one
        if os.path.isfile(DATA_PATH + "/states.csv"):
            self.states = pd.read_csv(DATA_PATH + "/states.csv")
            self.optimal_policies = pd.read_csv(DATA_PATH + "/opt_pol.csv")
            print(self.states)
            print(self.optimal_policies)

        else:
            self.states = pd.DataFrame(
                data=None,
                columns=[
                    str(i) + "_proba_0" for i in range(0, self.amount_of_peaked_objects)
                ]
                + [
                    str(i) + "_proba_1" for i in range(0, self.amount_of_peaked_objects)
                ],
            )
            self.optimal_policies = pd.DataFrame(
                data=None,
                columns=[
                    str(i) + "_true_peaked_normalised_acc"
                    for i in range(0, self.amount_of_peaked_objects)
                ],
            )

        self.train_nn()

    def train_nn(self):
        self.sampling_classifier.fit(
            x=self.states,
            y=self.optimal_policies,
            use_multiprocessing=True,
            #  epochs=1,
            epochs=10,
            batch_size=128,
        )

    def save_nn_training_data(self, DATA_PATH):
        self.states.to_csv(DATA_PATH + "/states.csv", index=False)
        self.optimal_policies.to_csv(DATA_PATH + "/opt_pol.csv", index=False)

    def move_labeled_queries(self, X_query, Y_query, query_indices):
        # move new queries from unlabeled to labeled dataset
        self.train_labeled_X = self.train_labeled_X.append(X_query)
        self.train_unlabeled_X = self.train_unlabeled_X.drop(query_indices)

        try:
            self.Y_train_strong_labels = self.Y_train_strong_labels.append(
                self.Y_train_unlabeled.loc[query_indices]
            )
        except KeyError:
            # in a non experiment setting an error will be thrown because self.Y_train_unlabeled of course doesn't contains the labels
            for query_index in query_indices:
                self.Y_train_strong_labels.loc[query_index] = [-1]

        self.Y_train_labeled = self.Y_train_labeled.append(Y_query)
        self.Y_train_unlabeled = self.Y_train_unlabeled.drop(
            query_indices, errors="ignore"
        )

        # remove indices from all clusters in unlabeled and add to labeled
        for cluster_id in self.train_unlabeled_X_cluster_indices.keys():
            list_to_be_removed_and_appended = []
            for indice in query_indices:
                if indice in self.train_unlabeled_X_cluster_indices[cluster_id]:
                    list_to_be_removed_and_appended.append(indice)

            # don't change a list you're iterating over!
            for indice in list_to_be_removed_and_appended:
                self.train_unlabeled_X_cluster_indices[cluster_id].remove(indice)
                self.train_labeled_X_cluster_indices[cluster_id].append(indice)

        # remove possible empty clusters
        self.train_unlabeled_X_cluster_indices = {
            k: v
            for k, v in self.train_unlabeled_X_cluster_indices.items()
            if len(v) != 0
        }

    """
    We take a "peak" into the future and annotate exactly those samples where we KNOW that they will benefit us the most
    """

    def calculate_next_query_indices(self, train_unlabeled_X_cluster_indices, *args):
        # merge indices from all clusters together and take the n most uncertain ones from them
        train_unlabeled_X_indices = list(
            chain(*list(train_unlabeled_X_cluster_indices.values()))
        )

        future_peak_acc = []

        random.shuffle(train_unlabeled_X_indices)
        possible_samples_indices = train_unlabeled_X_indices[
            : self.amount_of_peaked_objects
        ]

        # parallelisieren
        with parallel_backend("loky", n_jobs=self.N_JOBS):
            future_peak_acc = Parallel()(
                delayed(_future_peak)(
                    unlabeled_sample_indice,
                    self.weak_supervision_label_sources,
                    self.data_storage,
                    self.clf,
                    self.MAX_AMOUNT_OF_WS_PEAKS,
                )
                for unlabeled_sample_indice in possible_samples_indices
            )

        for labelSource in self.weak_supervision_label_sources:
            labelSource.data_storage = self.data_storage

        possible_samples_probas = self.clf.predict_proba(
            self.data_storage.train_unlabeled_X.loc[possible_samples_indices]
        )

        sorted_probas = -np.sort(-possible_samples_probas, axis=1)
        argmax_probas = sorted_probas[:, 0]
        argsecond_probas = sorted_probas[:, 1]

        X_state = np.array([*argmax_probas, *argsecond_probas])
        # take first and second most examples from possible_samples_probas and append them then to states
        self.states = self.states.append(
            pd.Series(dict(zip(self.states.columns, X_state))), ignore_index=True,
        )

        # the output of the net is one neuron per possible unlabeled sample, and the output should be:
        # a) 0 for label this, do not label that (how to determine how many, how to forbid how many labeled samples are allowed?)
        # b) predict accuracy gain by labeling sample x -> I can compare it directly to the values I could predict -> normalize values as 0 -> smallest possible gain, 1 -> highest possible gain
        future_peak_accs = [[b] for b in future_peak_acc]

        # min max scaling of output
        scaler = MinMaxScaler()
        future_peak_accs = [a[0] for a in scaler.fit_transform(future_peak_accs)]

        # save the indices of the n_best possible states, order doesn't matter
        self.optimal_policies = self.optimal_policies.append(
            pd.Series(dict(zip(self.optimal_policies.columns, future_peak_accs))),
            ignore_index=True,
        )

        X_state = np.reshape(X_state, (1, len(X_state)))
        if not self.USE_OPTIMAL_ONLY:
            Y_pred = self.sampling_classifier.predict(X_state)

            # train using the knowledge

        if not self.TRAIN_ONCE:
            self.train_nn()

        #  print(self.states)
        #  print(self.optimal_policies)
        # @todo print " self calculated mean squared loss on real values
        def order_metric(Y_pred, Y_true):
            print(Y_pred)
            print(Y_true)
            true_ordering = sorted(range(len(Y_true)), key=Y_true.__getitem__)
            pred_ordering = sorted(range(len(Y_pred)), key=Y_pred.__getitem__)

            print(pred_ordering)
            print(true_ordering)

            print("ACC:", accuracy_score(true_ordering, pred_ordering))
            print("MSE:", mean_squared_error(Y_true, Y_pred))
            print("TAU:", kendalltau(true_ordering, pred_ordering))
            print("SPEAR:", spearmanr(true_ordering, pred_ordering))

            #

        # @todo: compare real result with an order_metric result of a random ordering!!!!
        order_metric(Y_pred[0], self.optimal_policies.iloc[-1, :].to_numpy())
        # @todo print self calculated loss purely based on ordering -> use that as the real loss!
        # 1. @todo: restart using different synthetic datasets
        # @todo: discounting factor etc. to not always use the action by the NN but also the "true" result
        # 2. @todo: start big run on server which just generatse training data (peak 40 samples into future), without ann

        # use the results of the ann
        if not self.USE_OPTIMAL_ONLY:
            sorting = Y_pred[0]
        else:
            sorting = self.optimal_policies.iloc[-1, :].to_numpy()

        # use the optimal values
        zero_to_one_values_and_index = list(zip(sorting, possible_samples_indices))
        ordered_list_of_possible_sample_indices = sorted(
            zero_to_one_values_and_index, key=lambda tup: tup[0], reverse=True
        )

        return [
            v
            for k, v in ordered_list_of_possible_sample_indices[
                : self.nr_queries_per_iteration
            ]
        ]

        # hier dann stattdessen die Antwort vom hier trainiertem classifier zurückgeben
        future_peak_acc = sorted(future_peak_acc, key=lambda tup: tup[1], reverse=True)
        return [k for k, v in future_peak_acc[: self.nr_queries_per_iteration]]