# -*- coding: utf-8 -*-
import codecs
import cPickle as pickle
from nltk import FreqDist, LidstoneProbDist
import util


def make_model(stats_infile, picklefile, smoothingparam=0.001, min_freq=2, protocol=-1):
    """Train a probability model on a korp statistics file and save it as a pickle file.
    The model is a LidstoneProbabDist (NLTK) which has tuples (wordform, MSD-tag) as keys
    and smoothed probabilities as values."""
    fdist = FreqDist()
    with codecs.open(stats_infile, encoding='utf-8') as f:
        for line in f:
            fields = line[:-1].split('\t')
            word = fields[0]
            # skip word forms that only occur once
            if fields[4] == str(min_freq):
                break
            # get rid of all urls
            if word.startswith("http://"):
                continue
            # # words that only occur once may only contain letters and hyphens
            # if fields[4] == '1' and any(not (c.isalpha() or c == "-") for c in word):
            #     continue
            # if len(word) > 100:
            #     continue
            simple_msd = fields[1][:fields[1].find('.')] if '.' in fields[1] else fields[1]
            fdist[(word, simple_msd)] += int(fields[4])

    pd = LidstoneProbDist(fdist, smoothingparam, fdist.B())

    # save probability model as pickle
    with open(picklefile, "w") as p:
        pickle.dump(pd, p, protocol=protocol)

if __name__ == '__main__':
    util.run.main(make_model)
