import collections
import pickle
import re
from tqdm import tqdm
import numpy as np
import math
from pprint import pprint
from keras.preprocessing.sequence import pad_sequences

np.random.seed(12345)
data_index = 0
walk_index = 0


class Utils(object):
    def __init__(self, walks, window_size):
        # self.phrase_dic = clean_dictionary(pickle.load(
        #      open('C:/Users/sotir/PycharmProjects/thesis/relation_utilities/isa/isa_reversed_dic.p', 'rb')))
        # self.phrase_dic = clean_dictionary(pickle.load(open('drive/My Drive/node2vec_average_embeddings/relation_utilities/part_of/part_of_reversed_dic.p', 'rb')))
        self.phrase_dic = clean_dictionary(pickle.load(
            open('/home/paperspace/sotiris/thesis/relation_utilities/part_of/part_of_reversed_dic.p', 'rb')))
        self.stop = True
        self.window_size = window_size
        self.walks = walks
        data, self.frequencies, self.word2idx, self.idx2word = self.build_dataset(self.walks)
        self.vocabulary_size = len(self.word2idx)
        print("Total words: ", self.vocabulary_size)
        self.train_data = data
        # the sample_table it is used for negative sampling as they do in the original word2vec
        self.sample_table = self.create_sample_table()

    def build_word_vocab(self, walks):
        data_vocabulary = []  # in node2vec the words are nodeids and each walk represents a sentence
        word2idx = {}
        word2idx['PAD'] = 0
        word2idx['UNKN'] = len(word2idx)
        for walk in tqdm(walks):
            for nodeid in walk:
                data_vocabulary.append(nodeid)
                phrase = self.phrase_dic[int(nodeid)]
                phrase = phrase.split()
                for word in phrase:
                    try:
                        gb = word2idx[word]
                    except KeyError:
                        word2idx[word] = len(word2idx)
        data_size_sample_table = len(data_vocabulary)
        idx2word = dict(zip(word2idx.values(), word2idx.keys()))
        return data_size_sample_table, data_vocabulary, word2idx, idx2word

    def build_dataset(self, walks):
        print('Building dataset..')
        data_size_sample_table, vocabulary, word2idx, idx2word = self.build_word_vocab(walks)
        count = []
        count.extend(collections.Counter(vocabulary).most_common(data_size_sample_table))
        return vocabulary, count, word2idx, idx2word

    def create_sample_table(self):
        print('Creating sample table..')
        count = [element[1] for element in self.frequencies]
        pow_frequency = np.array(count) ** 0.75
        power = sum(pow_frequency)
        ratio = pow_frequency / power
        table_size = 1e8
        count = np.round(ratio * table_size)
        sample_table = []
        for idx, x in enumerate(count):
            sample = self.frequencies[idx]
            sample_table += [int(sample[0])] * int(x)
        return np.array(sample_table)

    def get_neg_sample_batch(self, pos_pairs, num_neg_samples):
        neg_v = np.random.choice(self.sample_table, size=(len(pos_pairs), num_neg_samples)).tolist()
        return neg_v

    def get_walk(self):
        global walk_index
        try:
            walk = self.walks[walk_index]
            walk_index += 1
            return walk
        except:
            print('No more walks..')
            self.stop = False

    def generate_batch(self, window_size, batch_size, neg_samples):
        global data_index
        span = 2 * window_size + 1
        # context = np.ndarray(shape=(batch_size, 2 * window_size), dtype=np.int64)
        context = []
        labels = np.ndarray(shape=(batch_size), dtype=np.int64)
        if data_index + span > len(self.current_walk):
            data_index = 0
        buffer = self.current_walk[data_index:data_index + span]
        pos_u = []
        pos_v = []
        batch_len = 0
        for i in range(batch_size):
            print(i)
            data_index += 1
            if len(context) == 0 or i > len(context):
                context = (buffer[:window_size] + buffer[window_size + 1:])
            # print(context)
            labels[i] = buffer[window_size]
            if data_index + span > len(self.current_walk):
                data_index = 0
                self.current_walk = self.get_walk()
                if self.stop:
                    buffer[:] = self.current_walk[:span]
            else:
                buffer = self.current_walk[data_index:data_index + span]
            if self.stop:
                batch_len += 1
                pos_u.append(labels[i])
                print(context[i])
                pos_v.append(context[i])
            else:
                batch_len += 1
                pos_u.append(labels[i])
                pos_v.append(context[i])
                break
        neg_v = np.random.choice(self.sample_table, size=(batch_len * neg_samples)).tolist()
        return pos_u, pos_v, neg_v, batch_len

    def node2vec_yielder(self, window_size):
        with open('dataset.txt', 'w') as dataset:
            for walk in tqdm(self.walks):
                for idx, phr in enumerate(walk):
                    # for each window position
                    pos_context = []
                    for w in range(-window_size, window_size + 1):
                        context_word_pos = idx + w
                        # make sure not jump out sentence
                        if context_word_pos < 0:
                            break
                        elif idx + window_size >= len(walk):
                            break
                        elif idx == context_word_pos:
                            continue
                        context_word_idx = walk[context_word_pos]
                        pos_context.append(context_word_idx)
                    if len(pos_context) != 0:
                        # neg_v = np.random.choice(self.sample_table, size=neg_samples).tolist()
                        for pos in pos_context:
                            dataset.write(phr + ' ' + pos + '\n')

    def node2vec_batch_yielder(self, window_size, neg_samples, batch_size):
        batch, max_phr_len, max_pos_len, max_neg_len = [], 0, 0, 0
        for walk in tqdm(self.walks):
            for idx, phr in enumerate(walk):
                # for each window position
                pos_context = []
                for w in range(-window_size, window_size + 1):
                    context_word_pos = idx + w
                    # make sure not jump out sentence
                    if context_word_pos < 0:
                        break
                    elif idx + window_size >= len(walk):
                        break
                    elif idx == context_word_pos:
                        continue
                    context_word_idx = walk[context_word_pos]
                    pos_context.append(context_word_idx)
                if len(pos_context) != 0:
                    neg_v = np.random.choice(self.sample_table, size=neg_samples).tolist()
                    phr = phr2idx(self.phrase_dic[int(phr)], self.word2idx)
                    pos_context = [phr2idx(self.phrase_dic[int(item)], self.word2idx) for item in pos_context]
                    neg_v = [phr2idx(self.phrase_dic[int(item)], self.word2idx) for item in neg_v]
                    max_phr_len = max([max_phr_len, len(phr)])
                    max_pos_len = max([max_pos_len] + [len(pos_ind) for pos_ind in pos_context])
                    max_neg_len = max([max_neg_len] + [len(neg_ind) for neg_ind in neg_v])

                    batch.append((phr, pos_context, neg_v))
                    if len(batch) % batch_size == 0:
                        batch_phr_inds = pad_sequences(sequences=[b[0] for b in batch], maxlen=max_phr_len)
                        batch_pos_inds = np.stack([pad_sequences(sequences=b[1], maxlen=max_pos_len) for b in batch])
                        batch_neg_inds = np.stack([pad_sequences(sequences=b[2], maxlen=max_neg_len) for b in batch])
                        batch = []
                        yield batch_phr_inds, batch_pos_inds, batch_neg_inds

    def get_num_batches(self, batch_size):
        num_batches = len(self.walks) * 80 / batch_size
        num_batches = int(math.ceil(num_batches))
        return num_batches


bioclean = lambda t: ' '.join(re.sub('[.,?;*!%^&_+():-\[\]{}]', '',
                                     t.replace('"', '').replace('/', '').replace('\\', '').replace("'",
                                                                                                   '').strip().lower()).split()).strip()


def get_index(w, vocab):
    try:
        return vocab[w]
    except KeyError:
        return vocab['UNKN']


def phr2idx(phr, word_vocab):
    p = [get_index(t, word_vocab) for t in phr.split()]
    return p


def clean_dictionary(phrase_dic):
    for nodeid, phrase in phrase_dic.items():
        phrase_dic[nodeid] = tokenize(phrase)
    return phrase_dic


def tokenize(x):
    return bioclean(x)


if __name__ == "__main__":
    walks = [['1', '23345', '3356', '4446', '5354', '6123', '74657', '8445', '97890', '1022', '1133'],
             ['6914', '1022', '97890', '8445', '74657', '6123', '5354', '4446', '3356', '23345', '1'],
             ['6914', '1022', '97890', '8445', '74657', '6123', '5354', '4446', '3356', '23345', '1']]
    utils = Utils(walks, 2)
    pos_u, pos_v, neg_v, batch_size = utils.generate_batch(window_size=5, batch_size=32, neg_samples=5)
    print(pos_u)
    print(len(pos_u))
    print(pos_v)
    print(len(pos_v))
    # print(batch_size)
    # for batch_phr_inds, batch_pos_inds, batch_neg_inds in utils.node2vec_batch_yielder(window_size=5, neg_samples=3, batch_size=3):
    #     # pos_u = Variable(torch.LongTensor(phr2idx(utils.phrase_dic[int(pos_u)], utils.word2idx)),
    #     #                  requires_grad=False)
    #     # pos_v = [Variable(torch.LongTensor(phr2idx(utils.phrase_dic[int(item)], utils.word2idx)),
    #     #                   requires_grad=False) for item in pos_v]
    #     # neg_v = [Variable(torch.LongTensor(phr2idx(utils.phrase_dic[int(item)], utils.word2idx)),
    #     #                   requires_grad=False) for item in neg_v]
    #     # print('heyyyyyyy')
    #     # print(pos_u)
    #     # print(pos_v)
    #     print(batch_phr_inds.shape)
    #     print(batch_pos_inds)
    #     print(batch_neg_inds.shape)
    # print(neg_v)
    # neg_v = Variable(torch.LongTensor(neg_v))
    # print(neg_v)
    # pos_u = [phr2idx(utils.phrase_dic[item], utils.word2idx) for item in pos_u]
    # print(pos_u)
    # pos_v = [phr2idx(utils.phrase_dic[item], utils.word2idx) for item_list in pos_v for item in item_list]
    # print(pos_v)
    # neg_v = [phr2idx(utils.phrase_dic[item], utils.word2idx) for item in neg_v]
    # print(neg_v)
    # print(pos_u)
    # print(pos_v)
    # print(neg_v)
    # exit()
    # # #print(neg_v)
    # pos = [Variable(torch.LongTensor(pos_ind), requires_grad=False) for pos_ind in pos_u]
    # pos_v = [Variable(torch.LongTensor(pos_ind), requires_grad=False) for pos_ind in pos_v]
    # neg_v = [Variable(torch.LongTensor(item_list), requires_grad=False) for item_list in neg_v]
    # model = SkipGram(utils.vocabulary_size, 128, neg_sample_num=2)
    # # # print(pos)
    # # # print(pos_v)
    # # # print(neg_v)
    # loss = model(pos, pos_v, neg_v, 4)
    # neg_v = [phr2idx(utils.phrase_dic[item], utils.word2idx) for item in neg_v]
    # print(neg_v)
    # print(neg_v.shape)

    # words_neg_sample = []
    # for item_list in neg_v:
    #     for item in item_list:
    #         words_neg_sample.append(phr2idx(utils.phrase_dic[item], utils.word2idx))
    # print('hiii: ',words_neg_sample)
    # for idx,item_list in enumerate(neg_v):
    #     print(idx,item_list)
    #     for idx1, i in enumerate(item_list):
    #         neg_v[idx][idx1] = phr2idx(utils.phrase_dic[i], utils.word2idx)
    # print(neg_v)
    # print(neg_v.shape)
    # neg_v = np.asarray(neg_v)

    # print(neg_v)
    # print(neg_v.shape)
    # print(pos_u)
    # print(pos_v)
    # print('neg_v:' ,neg_v[0][0])
    # print(neg_v.shape)
    # print(utils.word2idx)
    # exit()
    # loss = model(pos_u, pos_v, neg_v, 4)
