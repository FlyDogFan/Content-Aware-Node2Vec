import torch
from torch.autograd import Variable
import torch.nn as nn
import torch.nn.functional as F
import numpy as np


class SkipGram(nn.Module):
    def __init__(self, vocab_size, embedding_dim):
        super(SkipGram, self).__init__()
        self.u_embeddings = nn.Embedding(vocab_size, embedding_dim, sparse=True)
        # self.v_embeddings = nn.Embedding(vocab_size, embedding_dim, sparse=True)
        self.embedding_dim = embedding_dim
        self.init_emb()

    def init_emb(self):
        initrange = 0.5 / self.embedding_dim
        self.u_embeddings.weight.data.uniform_(-initrange, initrange)
        # self.v_embeddings.weight.data.uniform_(-0, 0)

    def dot_product_sum(self, node_emb, ex_embeds, exp=False):
        node_emb = node_emb.expand_as(ex_embeds)
        res = node_emb * ex_embeds
        res = res.sum(-1) / float(res.size(0))
        if (exp):
            res = torch.exp(res) * (res > 0.).float()
        # in the paper they use sum not average. it is kind of strange
        # res         = res.sum(-1) / float(res.size(0))
        res = res.sum(-1)
        return res

    def get_loss(self, node_emb, pe_emb, ne_emb):
        # Equation 2 of section 3 : Sum of f(ni) . f(u)
        pos_loss = self.dot_product_sum(node_emb, pe_emb, exp=False)
        # this is called "-log Zu" in the paper
        neg_loss = self.dot_product_sum(node_emb, ne_emb, exp=True)
        neg_loss = - torch.log(1 + neg_loss)
        #
        losss = - (neg_loss + pos_loss)
        return losss

    def forward(self, pos_u, pos_v, neg_v):
        embed_u = self.u_embeddings(pos_u)
        embed_v = self.u_embeddings(pos_v)
        neg_embed_v = self.u_embeddings(neg_v)
        losss = self.get_loss(embed_u, embed_v, neg_embed_v)
        return losss
        # embed_u = self.u_embeddings(pos_u)
        # embed_v = self.v_embeddings(pos_v)
        # neg_embed_v = self.v_embeddings(neg_v)
        # score = torch.mul(embed_u, embed_v)
        # score = torch.sum(score, dim=1)
        # log_target = F.logsigmoid(score)
        # neg_score = torch.bmm(neg_embed_v, embed_u.unsqueeze(2)).squeeze()
        # sum_log_sampled = F.logsigmoid(-1 * neg_score)
        # sum_log_sampled = torch.sum(sum_log_sampled, dim=1)
        # loss = log_target + sum_log_sampled
        # return -1 * loss.sum() / batch_size

    def save_embeddings(self, file_name, idx2word, use_cuda=False):
        wv = {}
        if use_cuda:
            embedding_u = self.u_embeddings.weight.cpu().data.numpy()
            #embedding_v = self.v_embeddings.weight.cpu().data.numpy()
        else:
            embedding_u = self.u_embeddings.weight.data.numpy()
            #embedding_v = self.v_embeddings.weight.data.numpy()

        fout = open(file_name, 'w')
        fout.write('%d %d\n' % (len(idx2word), self.embedding_dim))
        for wid, w in idx2word.items():
            e_u = embedding_u[wid]
            #e_v = embedding_v[wid]
            #e = (e_u + e_v) / 2
            wv[w] = e_u
            e = ' '.join(map(lambda x: str(x), e_u))
            fout.write('%s %s\n' % (w, e))
        return wv
