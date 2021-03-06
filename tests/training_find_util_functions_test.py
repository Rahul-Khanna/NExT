import sys
sys.path.append("../training/")
import random
import find_util_functions as func

random_state = 42
random.seed(random_state)

def test_build_synthetic_pretraining_triples():
    train = ["Here are some strings", 
             "Some not so interesting strings!", 
             "Let's make ThEm MORe Intersting?",
             "Yes you can :)",
             "Coolio <::>"]
    
    embedding_name = "glove.6B.50d"

    vocab = func.build_vocab(train, embedding_name, save=False)

    sample_data = ["Let's make ThEm MORe Intersting?",
                   "Some not so interesting strings!", 
                   "Are you sure, I'd like to be coolio!?"]

    act_tokenized_data = [[17, 6, 18, 22, 19, 16, 10],
                          [3, 20, 21, 15, 4, 5],
                          [11, 24, 0, 0, 0, 0, 0, 0, 0, 13, 5, 10]]
    
    act_queries = [[17], [20, 21, 15], [0, 0]]

    act_labels = [[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                  [0.0, 1.0, 1.0, 1.0, 0.0, 0.0],
                  [0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]]

    token_seqs, queries, labels = func.build_synthetic_pretraining_triples(sample_data, vocab, func.tokenize)

    assert act_tokenized_data == token_seqs
    assert act_queries == queries
    assert act_labels == labels

def test_build_real_pretraining_triples():
    train = ["Here are some strings", 
             "Some not so interesting strings!", 
             "Let's make ThEm MORe Intersting?",
             "Yes you can :)",
             "Coolio <::>"]
    
    embedding_name = "glove.6B.50d"

    vocab = func.build_vocab(train, embedding_name, save=False)

    sample_data = ["Let's make ThEm MORe Intersting?",
                   "Some not so interesting strings!", 
                   "Are you sure, I'd like to be coolio!?",
                   "Yes you can :)"]
    
    sample_queries = ["ThEm MORe",
                      "so interesting strings!",
                      "to be coolio!?",
                      "this won't show up"]

    act_tokenized_data = [[17, 6, 18, 22, 19, 16, 10],
                          [3, 20, 21, 15, 4, 5],
                          [11, 24, 0, 0, 0, 0, 0, 0, 0, 13, 5, 10]]
    
    act_queries = [[22, 19], [21, 15, 4, 5], [0, 0, 13, 5, 10]]

    act_labels = [[0, 0, 0, 1, 1, 0, 0],
                  [0, 0, 1, 1, 1, 1],
                  [0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1]]

    token_seqs, queries, labels = func.build_real_pretraining_triples(sample_data, sample_queries, vocab, func.tokenize)

    assert act_tokenized_data == token_seqs
    assert act_queries == queries
    assert act_labels == labels