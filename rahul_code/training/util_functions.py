from torchtext.data import Field, Example, Dataset
import spacy
import json
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score
import torch
import random
import pickle
from util_classes import PreTrainingFindModuleDataset
from tqdm import tqdm
import re

nlp = spacy.load("en_core_web_sm")

possible_embeddings = ['charngram.100d', 'fasttext.en.300d', 'fasttext.simple.300d', 'glove.42B.300d',
'glove.840B.300d', 'glove.twitter.27B.25d', 'glove.twitter.27B.50d', 'glove.twitter.27B.100d',
'glove.twitter.27B.200d', 'glove.6B.50d', 'glove.6B.100d', 'glove.6B.200d', 'glove.6B.300d']

def tokenize(sentence, tokenizer=nlp):
    """
        Simple tokenizer function that is needed to build a vocabulary
        Uses spaCy's en model to tokenize

        Arguments:
            sentence          (str) : input to be tokenized
            tokenizer (spaCy Model) : spaCy model to use for tokenization purposes

        Returns:
            arr : list of tokens
    """
    sentence = sentence.strip()
    sentence = sentence.lower()
    sentence = sentence.replace('\n', '')
    return [tok.text for tok in tokenizer.tokenizer(sentence)]

def build_vocab(train, embedding_name, random_state, save=True):
    """
        Note: Using the Field class will be deprecated soon by TorchText, however at the time of writing the
              new methodology for creating a vocabulary has not been released.
        
        Function that takes in training data and builds a TorchText Vocabulary object, which couples two
        important datastructures:
            1. Mapping from text token to token_id
            2. Mapping from token_id to vector

        Function expects a pre-computed set of vectors to be used in the mapping from token_id to vector

        Arguments:
            train          (arr) : array of text sequences that make up one's training data
            embedding_name (str) : name of pre-trained embedding to use 
                                   (possible names can be found in possible_embeddings)
            random_state   (int) : random state used to split data into train, dev, test
                                   (used only for naming purposes)
        Returns:
            torchtext.vocab : vocab object
    """
    text_field = Field(tokenize=tokenize, init_token = '<bos>', eos_token='<eos>')
    fields = [("text", text_field)]
    train_examples = []
    for text in train:
        train_examples.append(Example.fromlist([text], fields))
    
    train_dataset = Dataset(train_examples, fields=fields)
    
    text_field.build_vocab(train_dataset, vectors=embedding_name)
    vocab = text_field.vocab

    print("Finished building vocab of size {}".format(str(len(vocab))))

    if save:
        file_name = "../data/pre_train_data/vocab_{}_{}.p".format(embedding_name, str(random_state))

        with open(file_name, "wb") as f:
            pickle.dump(vocab, f)

    return vocab

def convert_text_to_tokens(data, vocab, tokenize_fn):
    """
        Converts sequences of text to sequences of token ids per the provided vocabulary

        Arguments:
            data              (arr) : sequences of text
            vocab (torchtext.vocab) : vocabulary object
            tokenize_fun (function) : function to use to break up text into tokens

        Returns:
            arr : array of arrays, each inner array is a token_id representation of the text passed in

    """
    word_seqs = [tokenize_fn(seq) for seq in data]
    token_seqs = [[vocab[word] for word in word_seq] for word_seq in word_seqs]

    return token_seqs

def build_pretraining_triples(data, vocab, tokenize_fn):
    """
        As per the NExT paper, we build a pre-training dataset from a dataset of unlabeled text.
        The process is as follows per sequence of text (Seq):
            1. Tokenize the text
            2. Convert tokens into token_ids
            3. Select a random number (N) between 1 and 5 for the number of tokens that make up a query (Q)
            4. Select a starting position in the sequence (S)
            5. Extract the tokens [S:S+N], this is our query sequence Q
            6. Label each token in Seq with a 1 or 0, indicating whether the token is in Q or not

        As a result of this process we build the triple (Seq, Q, labels) that will be used in pre-training

        Arguments:
            data              (arr) : sequences of text
            vocab (torchtext.vocab) : vocabulary object
            tokenize_fun (function) : function to use to break up text into tokens
        
        Returns:
            tokenized seqs, queries, labels : triplet where each element is a list of equal length
                                              containing the information described above
    """
    token_seqs = convert_text_to_tokens(data, vocab, tokenize_fn)
    token_seqs = [token_seq for token_seq in token_seqs if len(token_seq) > 3]
    queries = []
    labels = []
    for i, token_seq in enumerate(token_seqs):
        num_tokens = random.randint(1, min(len(token_seq), 5))
        starting_position = random.randint(0, len(token_seq)-num_tokens)
        end_position = starting_position + num_tokens
        queries.append(token_seq[starting_position:end_position])
        token_seqs[i] = [vocab["<bos>"]] + token_seq + [vocab["<eos>"]]
        label_seq = [0.0]
        for i in range(len(token_seq)):
            if i >= starting_position and i < end_position:
                label_seq.append(1.0)
            else:
                label_seq.append(0.0)
        label_seq.append(0.0)
        labels.append(label_seq)
    
    return token_seqs, queries, labels

def build_variable_length_text_dataset(data, vocab, split_name, embedding_name, random_state):
    """
        Given a split of data (train, dev, test) this function builds a PreTrainingFindModuleDataset and saves
        it to disk. A VariableLegnthTextDataset object handles batching sequences together and ensuring
        every input is of the same length (the length of the max sequence length in a batch).

        Arguments:
            data              (arr) : split of data that needs to be processed
            vocab (torchtext.vocab) : vocab object used for conversion between text token and token_id
            split_name        (str) : name of split (used for naming)
            embedding_name    (str) : name of pre-trained embeddings being used in vocab (used for naming)
            random_state      (int) : random seed used for splitting data (used for naming)
    """
    pad_idx = vocab["<pad>"]
    token_seqs, queries, labels = build_pretraining_triples(data, vocab, tokenize)
    dataset = PreTrainingFindModuleDataset(token_seqs, queries, labels, pad_idx)

    print("Finished building {} dataset of size: {}".format(split_name, str(len(token_seqs))))

    file_name = "../data/pre_train_data/{}_data_{}_{}.p".format(split_name, embedding_name, str(random_state))

    with open(file_name, "wb") as f:
        pickle.dump(dataset, f)

def extract_queries_from_explanations(explanation):
    """
        Checks for the existence of a quoted phrase within an explanation
        Three types of quotes are accepted
        
        Arguments:
            explanation (str) : explanation text for a labeling decision
        
        Returns:
            arr : an array of quoted phrases or an empty array
    """
    possible_queries = re.findall('"[^"]+"', explanation)
    if len(possible_queries):
        return possible_queries
    
    possible_queries = re.findall("'[^']+'", explanation)
    if len(possible_queries):
        return possible_queries

    possible_queries = re.findall("`[^`]+`", explanation)
    if len(possible_queries):
        return possible_queries

    return []


def build_query_dataset(explanation_data, vocab, label_filter, embedding_name, random_state):
    """
        Given a list of explanations for labeling decisions, we find those explanations that include phrases
        that must exist in a text-sequence for a label to be applied to the text sequence.

            Ex: The text contains the phrase "xyz"

        We then tokenize and convert the phrases within quotes (queries) into sequence of token_ids that will
        be used at training time to try and push embeddings of queries associated with the same label closer
        together.

        Arguments:
            explanation_data  (arr) : array of natural language explanations for labeling decisions
            vocab (torchtext.vocab) : vocab object used for conversion between text token and token_id
            label_filter      (arr) : labels to consider when extracting queries from explanations
                                      (allows user to ignore explanations associated with certain labels)
            embedding_name    (str) : name of pre-trained embeddings being used in vocab (used for naming)
            random_state      (int) : random seed used for unlabeled splitting data (used for naming)
    """
    queries = []
    labels = []
    for entry in explanation_data:
        explanation = entry["explanation"]
        label = entry["label"]
        if label_filter is None or label in label_filter:
            possible_queries = extract_queries_from_explanations(explanation)
            for query in possible_queries:
                queries.append(query[1:len(text)-1])
                labels.append(label)
    
    tokenized_queries = convert_text_to_tokens(queries, vocab, tokenize)

    print("Finished tokenizing actual queries, count: {}".format(str(len(tokenized_queries))))

    file_name = "../data/pre_train_data/sim_data_{}_{}.p".format(embedding_name, str(random_state))

    with open(file_name, "wb") as f:
        pickle.dump({"queries" : tokenized_queries, "labels" : labels}, f)


def build_pre_train_find_datasets(file_path, explanation_path, embedding_name="glove.840B.300d",
                                  random_state=42, label_filter=None, sample_rate=0.1):
    """
        As per the NExT paper, we build train, dev and test datasets to allow for the pre-training and
        evaluation of the FIND module.

        Steps taken:
            1. Load unlabeled data
            2. If only a sample of the data is to be used, we sample the data
            3. Split data into train, dev, and test splits
            4. Build a vocabulary object using the train split
            5. Build needed datasets for computing L_find loss (for each split)
            6. Build needed datasets for computing L_sim loss
        
        Arguments:
            file_path        (str) : path to unlabeled data
            explanation_path (str) : path to explanation data
            embedding_name   (str) : name of pre-trained embeddings being used in vocab
            random_state     (int) : random seed to use when splitting data into train, dev, test splits
            label_filter     (arr) : labels to consider when extracting queries from explanations
                                     (allows user to ignore explanations associated with certain labels)
            sample_rate    (float) : percentage of unlabeled data to use when building datasets for L_find
    """
    if not embedding_name in possible_embeddings:
        print("Not Valid Embedding Option")
        return
    
    with open(file_path) as f:
        text_data = json.load(f)
    
    if sample_rate > 0:
        sample_number = int(len(text_data) * sample_rate)
        text_data = random.sample(text_data, sample_number)
    
    train, dev = train_test_split(text_data, train_size=0.8, random_state=random_state)
    dev, test = train_test_split(dev, train_size=0.5, random_state=random_state)

    vocab = build_vocab(train, embedding_name, random_state)

    build_variable_length_text_dataset(train, vocab, "train", embedding_name, random_state)

    build_variable_length_text_dataset(dev, vocab, "dev", embedding_name, random_state)

    build_variable_length_text_dataset(test, vocab, "test", embedding_name, random_state)

    with open(explanation_path) as f:
        explanation_data = json.load(f)

    build_query_dataset(explanation_data, vocab, label_filter, embedding_name, random_state)

def build_pre_train_find_datasets_from_splits(train_path, dev_path, test_path, explanation_path,
                                              embedding_name="glove.840B.300d", label_filter=None):
    """
        Provided pre-split data, follow the steps taken in build_pre_train_find_datasets

        Splits are assumed to be json file, where the only element is an array of text

        Arguments:
            train_path       (str) : path to training split of data
            dev_path         (str) : path to dev split of data
            test_path        (str) : path to test split of data
            explanation_path (str) : path to explanation data
            embedding_name   (str) : name of pre-trained embeddings being used in vocab
            label_filter     (arr) : labels to consider when extracting queries from explanations
                                     (allows user to ignore explanations associated with certain labels)
    """

    with open(train_path) as f:
        train = json.load(f)
    
    vocab = build_vocab(train, embedding_name, random_state=-1)

    build_variable_legnth_text_dataset(train, vocab, "train", embedding_name, random_state=-1)

    with open(dev_path) as f:
        dev = json.load(f)

    build_variable_length_text_dataset(dev, vocab, "dev", embedding_name, random_state=-1)

    with open(test_path) as f:
        test = json.load(f)
    
    build_variable_length_text_dataset(test, vocab, "test", embedding_name, random_state=-1)

    with open(explanation_path) as f:
        explanation_data = json.load(f)

    build_query_dataset(explanation_data, vocab, label_filter, embedding_name, random_state=-1)

def similarity_loss_function(pos_scores, neg_scores):
    """
        L_sim in the NExT Paper

        Arguments:
            pos_scores (torch.tensor) : per query the max value of (tau - cos(q_li_j, q_li_k))^2
                                        dims: (n,)
            neg_scores (torch.tensor) : per query the max value of (cos(q_li_j, q_lk_m))^2
                                        dims: (n,)
        
        Returns:
            torch.tensor : average of the sum of scores per query, dims: (1,)
    """
    return torch.mean(pos_scores + neg_scores)

def evaluate_find_module(data_path, act_queries, query_labels, model, find_loss_fn, sim_loss_fn,
                         batch_size=128, gamma=0.5):
    """
        Evaluates a Find Module model against a dataset

        Arguments:
            data_path            (str) : path to PreTrainingFindModuleDataset that the model should be
                                         evaluated against
            act_queries (torch.tensor) : queries to be used for computing L_sim, dim: (n, max_len)
            query_labels         (arr) : labels associated with queries
            model        (Find_Module) : model to use in evaluation
            find_loss_fn        (func) : loss function for L_find
            sim_loss_fn         (func) : loss function for L_sim
            batch_size           (int) : size of batch to use when computing L_find
            gamma              (float) : weight associated with L_sim
        
        Returns:
            avg_loss, avg_find_loss, avg_sim_loss, avg_f1_score : average of metrics computed per batch
    """
    with open(data_path, "rb") as f:
        eval_dataset = pickle.load(f)
    
    # deactivate dropout layers
    model.eval()
    
    if torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
    
    total_loss, total_find_loss, total_sim_loss, total_f1_score = 0, 0, 0, 0
    batch_count = 0

    # iterate over batches
    for step, batch in enumerate(tqdm(eval_dataset.as_batches(batch_size=batch_size, shuffle=False))):
        # push the batch to gpu
        batch = [r.to(device) for r in batch]

        tokens, queries, labels = batch

        # deactivate autograd
        with torch.no_grad():

            # model predictions
            token_scores = model.find_forward(tokens, queries)
            pos_scores, neg_scores = model.sim_forward(act_queries, query_labels)

            # compute the validation loss between actual and predicted values
            find_loss = find_loss_fn(token_scores, labels)
            sim_loss = sim_loss_fn(pos_scores, neg_scores)
            string_loss = find_loss + gamma * sim_loss
            
            scores = token_scores.detach().cpu().numpy().flatten()
            scores = [1 if score > 0.5  else 0 for score in scores]
            f1_labels = labels.detach().cpu().numpy().flatten()

            total_loss = total_loss + string_loss.item()
            total_find_loss = total_find_loss + find_loss.item()
            total_sim_loss = total_sim_loss + sim_loss.item()
            total_f1_score = total_f1_score + f1_score(f1_labels, scores)
            batch_count += 1

    # compute the validation loss of the epoch
    avg_loss = total_loss / batch_count
    avg_find_loss = total_find_loss / batch_count
    avg_sim_loss = total_sim_loss / batch_count
    avg_f1_score = total_f1_score / batch_count

    return avg_loss, avg_find_loss, avg_sim_loss, avg_f1_score

def evaluate_find_loss(data_path, model, find_loss_fn, batch_size=128):
    """
        Evaluates a Find Module model against a dataset, where the Find Module is only trained using L_find

        Arguments:
            data_path            (str) : path to PreTrainingFindModuleDataset that the model should be
                                         evaluated against
            model        (Find_Module) : model to use in evaluation
            find_loss_fn        (func) : loss function for L_find
            batch_size           (int) : size of batch to use when computing L_find
        
        Returns:
            avg_find_loss, avg_f1_score : average of metrics computed per batch
    """
    with open(data_path, "rb") as f:
        eval_dataset = pickle.load(f)
    
    # deactivate dropout layers
    model.eval()
    
    if torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
    
    total_find_loss = 0
    total_f1_score = 0
    batch_count = 0

    # iterate over batches
    for step, batch in enumerate(tqdm(eval_dataset.as_batches(batch_size=batch_size, shuffle=False))):
        # push the batch to gpu
        batch = [r.to(device) for r in batch]

        tokens, queries, labels = batch

        # deactivate autograd
        with torch.no_grad():

            # model predictions
            token_scores = model.find_forward(tokens, queries)

            # compute the validation loss between actual and predicted values
            find_loss = find_loss_fn(token_scores, labels)

            scores = token_scores.detach().cpu().numpy().flatten()
            scores = [1 if score > 0.5  else 0 for score in scores]
            f1_labels = labels.detach().cpu().numpy().flatten()

            total_f1_score = total_f1_score + f1_score(f1_labels, scores)
            total_find_loss = total_find_loss + find_loss.item()
            batch_count += 1

    # compute the validation loss of the epoch
    avg_find_loss = total_find_loss / batch_count
    avg_f1_score = total_f1_score / batch_count

    return avg_find_loss, avg_f1_score