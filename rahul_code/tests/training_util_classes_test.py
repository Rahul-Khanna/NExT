import sys
sys.path.append("../training/")
from util_classes import PreTrainingFindModuleDataset
import torch

tokens = [
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        [1, 34, 45, 17, 5, 6],
        [1, 432, 343, 953, 349, 3940, 3993, 33, 22, 111, 2349, 3490],
        [1, 98, 23489, 18883, 9993, 884, 91294, 39193, 949, 999, 344, 3940, 404],
        [1, 123, 45, 545, 3939, 29, 29, 49, 59, 39, 28, 93, 96, 98, 9, 2, 3, 4, 5],
        [1, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44, 46, 48, 50],
        [1, 23, 32, 24, 42, 25, 52, 26, 62, 27, 72, 28, 82, 29, 92, 20, 2],
        [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33, 35, 37]
]

queries = [
        [6, 7],
        [34, 45, 17],
        [3993],
        [18883, 9993, 884, 91294, 39193],
        [3939, 29, 29, 49],
        [22, 24, 26],
        [62, 27],
        [25]
]

labels = [
    [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0],
    [0.0, 1.0, 1.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
]

def test_variable_length_batch_as_tensors():
    padded_tokens = PreTrainingFindModuleDataset.variable_length_batch_as_tensors(tokens, 0)
    assert padded_tokens.shape[0] == 8
    assert padded_tokens.shape[1] == 26
    
    padded_queries = PreTrainingFindModuleDataset.variable_length_batch_as_tensors(queries, 0)
    assert padded_queries.shape[0] == 8
    assert padded_queries.shape[1] == 5

    padded_labels = PreTrainingFindModuleDataset.variable_length_batch_as_tensors(labels, 0.0, torch.float)
    assert padded_labels.shape[0] == 8
    assert padded_labels.shape[1] == 26


def test_as_batches_shuffle():
    dataset = PreTrainingFindModuleDataset(tokens, queries, labels, 0)

    token_lengths = [19, 26, 13, 19]
    query_lengths = [4, 3, 5, 2]
    for i, batch in enumerate(dataset.as_batches(batch_size=2)):
        b_tokens, b_queries, b_labels = batch

        assert b_tokens.shape[0] == 2
        assert b_tokens.shape[1] == token_lengths[i]

        assert b_queries.shape[0] == 2
        assert b_queries.shape[1] == query_lengths[i]

        assert b_labels.shape[0] == 2
        assert b_labels.shape[1] == token_lengths[i]

def test_as_batches_no_shuffle():
    dataset = PreTrainingFindModuleDataset(tokens, queries, labels, 0)

    token_lengths = [10, 13, 26, 19]
    query_lengths = [3, 5, 4, 2]
    for i, batch in enumerate(dataset.as_batches(batch_size=2, seed=0, shuffle=False)):
        b_tokens, b_queries, b_labels = batch

        assert b_tokens.shape[0] == 2
        assert b_tokens.shape[1] == token_lengths[i]

        assert b_queries.shape[0] == 2
        assert b_queries.shape[1] == query_lengths[i]

        assert b_labels.shape[0] == 2
        assert b_labels.shape[1] == token_lengths[i]