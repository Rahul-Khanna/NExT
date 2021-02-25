import torch
import torch.nn as nn
import torch.nn.functional as f

class BiLSTM_Att_Clf(nn.Module):
    def __init__(self, emb_weight, padding_idx, emb_dim, hidden_dim, cuda, number_of_classes, tuneable_vector_count,
                 n_layers=2, encoding_dropout=0.4, padding_score=-1e30):
        """
            Arguments:
                emb_weight (torch.tensor) : created vocabulary's vector representation for each token, where
                                            vector_i corresponds to token_i
                                            dims : (vocab_size, emb_dim)
                padding_idx         (int) : index of pad token in vocabulary
                emb_dim             (int) : legnth of each vector representing a token in the vocabulary
                hidden_dim          (int) : size of hidden representation emitted by lstm
                                            (we are using a bi-lstm, final hidden_dim will be 2*hidden_dim)
                cuda               (bool) : is a gpu available for usage
                number_of_classes   (int) : number of classes to predict over
                n_layers            (int) : number of layers for the bi-lstm that encodes n-gram representations
                                            of a token 
                encoding_dropout  (float) : percentage of vector's representation to be randomly zeroed
                                            out before pooling
                padding_score     (float) : score of padding tokens during attention calculation
        """
        super(BiLSTM_Att_Clf, self).__init__()

        self.padding_idx = padding_idx
        self.padding_score = padding_score
        self.emb_dim = emb_dim
        self.hidden_dim = hidden_dim
        self.encoding_dim = 2*hidden_dim
        self.number_of_classes = number_of_classes
        self.tuneable_vector_count = tuneable_vector_count

        tuneable_weights = emb_weight[:self.tuneable_vector_count]
        frozen_weights = torch.cat([emb_weight[0].unsqueeze(0), emb_weight[self.tuneable_vector_count:]])

        self.tuneable_embeddings = nn.Embedding.from_pretrained(tuneable_weights, freeze=False)
        self.frozen_embeddings = nn.Embedding.from_pretrained(frozen_weights, freeze=True)

        self.embeddings = nn.Embedding.from_pretrained(emb_weight, freeze=False, padding_idx=self.padding_idx)
        self.encoding_bilstm = nn.LSTM(self.emb_dim, self.hidden_dim, num_layers=n_layers,
                                       bidirectional=True, batch_first=True)
        
        self.attention_matrix = nn.Linear(self.encoding_dim, self.encoding_dim)
        nn.init.xavier_uniform_(self.attention_matrix.weight)
        self.attention_activation = nn.Tanh()
        self.attention_vector = nn.Linear(self.encoding_dim, 1, bias=False)
        nn.init.kaiming_uniform_(self.attention_vector.weight, mode='fan_in')
        self.attn_softmax = nn.Softmax(dim=2)

        self.weight_linear_layer_1 = nn.Linear(self.encoding_dim, 256)
        nn.init.kaiming_uniform_(self.weight_linear_layer_1.weight, a=0.01, mode='fan_in')

        self.weight_linear_layer_2 = nn.Linear(256, 128)
        nn.init.kaiming_uniform_(self.weight_linear_layer_2.weight, a=0.01, mode='fan_in')
        
        self.weight_linear_layer_3 = nn.Linear(128, 64)
        nn.init.kaiming_uniform_(self.weight_linear_layer_3.weight, a=0.01, mode='fan_in')

        self.weight_final_layer = nn.Linear(64, self.number_of_classes)
        nn.init.kaiming_uniform_(self.weight_final_layer.weight, a=0.01, mode='fan_in')

        self.weight_activation_function = nn.LeakyReLU()

        self.embedding_dropout = nn.Dropout(p=0.2)
        self.encoding_dropout = nn.Dropout(p=encoding_dropout)
        self.mlp_dropout = nn.Dropout(p=0.1)
    
    def get_attention_weights(self, hidden_states, padding_indexes=None):
        """
            Calculates attention weights for each token in each sequence passed in
                * heavily discounts the importance of padding_tokens, when indices representing which
                  tokens are padding and which aren't
            Arguments:
                hidden_states   (torch.tensor) : N x seq_len x encoding_dim
                padding_indexes (torch.tensor) : N x seq_len
            Returns:
                (torch.tensor) : N x 1 x seq_len
        """
        linear_transform = self.attention_matrix(hidden_states) # linear_transform = N x seq_len x encoding_dim
        tanh_tensor = self.attention_activation(linear_transform) # element wise tanh
        batch_dot_products = self.attention_vector(tanh_tensor) # batch_dot_product = batch x seq_len x 1
        if padding_indexes != None:
            padding_scores = self.padding_score * padding_indexes # N x seq_len
            batch_dot_products = batch_dot_products + padding_scores.unsqueeze(2) # making sure score of padding_idx tokens is incredibly low
        updated_batch_dot_products = batch_dot_products.permute(0,2,1) # batch x 1 x seq_len
        batch_soft_max = self.attn_softmax(updated_batch_dot_products) #apply softmax along row

        return batch_soft_max

    def attention_pooling(self, hidden_states, padding_indexes):
        """
            Pools hidden states together using a trainable attention matrix and query vector
            
            Arguments:
                hidden_states   (torch.tensor) : N x seq_len x encoding_dim
                padding_indexes (torch.tensor) : N x seq_len
            
            Returns:
                (torch.tensor) : N x 1 x encoding_dim
        """
        batch_soft_max = self.get_attention_weights(hidden_states, padding_indexes) # batch_soft_max = batch x 1 x seq_len
        pooled_rep = torch.bmm(batch_soft_max, hidden_states) # pooled_rep = batch x 1 x encoding_dim

        return pooled_rep
    
    def get_embeddings(self, seqs):
        """
            Convert tokens into vectors. Also figures out what tokens are padding.
            Arguments:
                seqs (torch.tensor) : N x seq_len
            
            Returns:
                seq_embs, padding_indexes : N x seq_len x embedding_dim, N x seq_len
        """
        padding_indexes = seqs == self.padding_idx # N x seq_len
        padding_indexes = padding_indexes.float()

        mask = seqs < self.tuneable_vector_count

        # You may want to optimize it, you could probably get away without copy, though
        # I'm not currently sure how
        seqs_copy = seqs.clone().detach()
        # Subtracting token ids by constant
        seqs_copy -= (self.tuneable_vector_count - 1)
        seqs_copy[mask] = 0

        frozen_embs = self.frozen_embeddings(seqs_copy)
    
        seqs[~mask] = 0
        seq_embs = self.tuneable_embeddings(seqs)

        # And finally change appropriate tokens from placeholder embedding created by
        # pretrained into trainable embeddings.
        seq_embs[~mask] = frozen_embs[~mask] # seq_embs = N x seq_len x embedding_dim
                
        return seq_embs, padding_indexes
    
    def encode_tokens(self, seqs):
        """
            Create raw encodings for a sequence of tokens
            Arguments:
                seqs (torch.tensor) : N x seq_len
            
            Returns:
                seq_embs, padding_indexes : N x seq_len x encoding_dim, N x seq_len
        """
        seq_embs, padding_indexes = self.get_embeddings(seqs) # N x seq_len x embedding_dim, N, seq_len
        seq_embs = self.embedding_dropout(seq_embs)
        seq_encodings, _ = self.encoding_bilstm(seq_embs) # N x seq_len, encoding_dim
        seq_encodings = self.encoding_dropout(seq_encodings)
        
        return seq_encodings, padding_indexes
    
    def classification_head(self, pooled_vectors):
        """
            MLP head on top of encoded representation to be classified
            Arguments:
                pooled_vectors (torch.tensor) : N x encoding_dim
            
            Returns:
                (torch.tensor) : N x number_of_classes
        """
        compressed_vector = self.mlp_dropout(pooled_vectors)

        compressed_vector = self.weight_linear_layer_1(compressed_vector)
        compressed_vector = self.weight_activation_function(compressed_vector)
        
        compressed_vector = self.mlp_dropout(compressed_vector)

        compressed_vector = self.weight_linear_layer_2(compressed_vector)
        compressed_vector = self.weight_activation_function(compressed_vector)

        compressed_vector = self.mlp_dropout(compressed_vector)

        compressed_vector = self.weight_linear_layer_3(compressed_vector) # N x 64
        compressed_vector = self.weight_activation_function(compressed_vector)

        compressed_vector = self.mlp_dropout(compressed_vector)
            
        classification_scores = self.weight_final_layer(compressed_vector) # N x number_of_classes

        return classification_scores

    def forward(self, seqs):
        seq_encodings, padding_indexes = self.encode_tokens(seqs) # N x seq_len x encoding_dim, N x seq_len
        pooled_encodings = self.attention_pooling(seq_encodings, padding_indexes).squeeze(1) # N x encoding_dim
        classification_scores = self.classification_head(pooled_encodings)

        return classification_scores # N x number_of_classes
