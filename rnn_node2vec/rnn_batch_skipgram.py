from pprint import pprint

import torch
from torch.autograd import Variable
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import pdb
from tqdm import tqdm
my_seed = 1997
torch.manual_seed(my_seed)
torch.cuda.manual_seed(my_seed)


class node2vec_rnn(nn.Module):
    def __init__(self, vocab_size, embedding_dim, rnn_size, neg_sample_num, batch_size, window_size, scale=1e-4, max_norm=1):
        super(node2vec_rnn, self).__init__()
        self.u_embeddings = nn.Embedding(vocab_size, embedding_dim, padding_idx=0)
        self.v_embeddings = nn.Embedding(vocab_size, embedding_dim, padding_idx=0)
        self.embedding_dim = embedding_dim
        self.neg_sample_num = neg_sample_num
        self.batch_size = batch_size
        self.window_size = window_size
        self.rnn_size = rnn_size
        print(self.rnn_size)
        self.scale = scale
        self.max_norm = max_norm
        self.h0 = nn.Parameter(torch.randn(1, self.batch_size, self.rnn_size).uniform_(-self.scale, self.scale))
        self.the_rnn = nn.GRU(input_size=self.embedding_dim, hidden_size=self.rnn_size, num_layers=1, bidirectional=False,
                              bias=True, dropout=0, batch_first=True)
        self.init_weights(self.scale)
        self.init_emb()

    def init_emb(self):
        initrange = 0.5 / self.embedding_dim
        self.u_embeddings.weight.data.uniform_(-initrange, initrange)
        self.u_embeddings.weight.data[0] = 0
        self.v_embeddings.weight.data.uniform_(-0, 0)

    def init_weights(self, scale=1e-4):
        for param in self.the_rnn.parameters():
            nn.init.uniform_(param, a=-scale, b=scale)

    def fix_input(self, phr_inds, pos_inds, neg_inds):
        phr = [Variable(torch.LongTensor(phr_ind), requires_grad=False).cuda() for phr_ind in phr_inds]
        pos = [Variable(torch.LongTensor(pos_ind), requires_grad=False).cuda() for pos_ind in pos_inds]
        neg = [Variable(torch.LongTensor(neg_ind), requires_grad=False).cuda() for neg_ind in neg_inds]
        return phr, pos, neg

    def get_words_embeds(self, phr, pos, neg):
        phr = [self.u_embeddings(p) for p in phr]
        phr = torch.stack(phr)
        pos = [self.v_embeddings(p) for p in pos]
        pos = torch.stack(pos)
        neg = [self.u_embeddings(n) for n in neg]
        neg = torch.stack(neg)
        return phr, pos, neg

    def rnn_representation_one(self, inp):
        inp, hn = self.the_rnn(inp, self.h0)
        last_timestep = hn[-1]
        return last_timestep

    def get_rnn_representation(self, phr, pos, neg):
        phr = self.rnn_representation_one(phr)
        pos = self.rnn_representation_one(pos)

        first_neg_batch = neg[:self.batch_size]
        second_neg_batch = neg[self.batch_size:]
        neg = torch.cat([self.rnn_representation_one(n) for n in [first_neg_batch, second_neg_batch]], dim=0)
        neg = neg.view(phr.size(0), -1, self.rnn_size)
        
        return phr, pos, neg

    def get_loss(self, phr_emb, context_emb, neg_emb):
        score = torch.mul(phr_emb, context_emb)
        score = torch.sum(score, dim=1)
        log_target = F.logsigmoid(score)
        neg_score = torch.bmm(neg_emb, phr_emb.unsqueeze(2)).squeeze()
        sum_log_sampled = F.logsigmoid(-1 * neg_score)
        sum_log_sampled = torch.sum(sum_log_sampled, dim=1)
        loss = log_target + sum_log_sampled
        return -1 * torch.mean(loss)

    def forward(self, phr_inds, pos_inds, neg_inds):
        phr, pos, neg = self.fix_input(phr_inds, pos_inds, neg_inds)
        phr, pos, neg = self.get_words_embeds(phr, pos, neg)
        phr, pos, neg = self.get_rnn_representation(phr, pos, neg)
        loss = self.get_loss(phr, pos, neg)
        return loss

    def save_embeddings(self, file_name, idx2word, use_cuda=False):
        wv = {}
        if use_cuda:
            embedding_u = self.u_embeddings.weight.cpu().data.numpy()
            embedding_v = self.v_embeddings.weight.cpu().data.numpy()
        else:
            embedding_u = self.u_embeddings.weight.data.numpy()
            embedding_v = self.v_embeddings.weight.data.numpy()

        fout = open(file_name, 'w')
        fout.write('%d %d\n' % (len(idx2word), self.embedding_dim))
        for wid, w in idx2word.items():
            e_u = embedding_u[wid]
            e_v = embedding_v[wid]
            e = (e_u + e_v) / 2
            wv[w] = e
            e = ' '.join(map(lambda x: str(x), e))
            fout.write('%s %s\n' % (w, e))
        return wv
