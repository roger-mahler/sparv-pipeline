# -*- coding: utf-8 -*-

import util
import sqlite3 as sqlite
from util.mysql_wrapper import MySQL

def relations(out, word, pos, lemgram, dephead, deprel, sentence, sentenceid, encoding=util.UTF8):
    """ Finds every dependency between words. """

    SENTID = util.read_annotation(sentenceid)
    sentences = [(SENTID[key], sent.split()) for key, sent in util.read_annotation_iteritems(sentence)]
    WORD = util.read_annotation(word)
    POS = util.read_annotation(pos)
    LEM = util.read_annotation(lemgram)
    DEPHEAD = util.read_annotation(dephead)
    DEPREL = util.read_annotation(deprel)
    
    triples = []
    
    for sentid, sent in sentences:
        
        incomplete = {}
        previous = {}
        
        for token_id in sent:
            token_pos = POS[token_id]
            token_lem = LEM[token_id]
            token_dh  = DEPHEAD[token_id]
            token_dr  = DEPREL[token_id]
            
            if token_lem == "|":
                token_lem = WORD[token_id].lower() + "_" + token_pos
            
            previous[token_id] = (token_lem, token_pos)
            
            if not token_dh == "-":
                triple = [None, token_dr, (token_lem, token_pos), sentid]
                if token_dh in previous:
                    triple[0] = (previous[token_dh])
                    triples.append(tuple(triple))
                else:
                    incomplete.setdefault(token_dh, []).append(triple)
            
            if token_id in incomplete:
                for t in incomplete[token_id]:
                    t[0] = (token_lem, token_pos)
                    triples.append(tuple(t))
                del incomplete[token_id]
    
    print "Incomplete:", len(incomplete)
    
    OUT = [(str(i), "\t".join(("^".join(head), rel, "^".join(w), sid))) for (i, (head, rel, w, sid)) in enumerate(triples)]
    util.write_annotation(out, OUT)


def frequency(source, corpus, db_name, sqlfile):
    """ Calculates statistics of the dependencies and saves to an SQL file. """
    
    pos_filter = (u"VB", u"NN", u"JJ")
    rel_filter = (u"SS", u"OO", u"IO", u"AT", u"ET" u"DT", u"OA", u"RA", u"TA") # http://stp.ling.uu.se/~nivre/swedish_treebank/dep.html
    min_count = 2
    
    source = source.split()
    
    freq = {}
    
    for s in source:
        REL = util.read_annotation(s)

        for _, triple in REL.iteritems():
            head, rel, w, sid = triple.split(u"\t")
            #print "%50s %5s   %-50s" % (head, rel, w)
            freq.setdefault(head, {}).setdefault(rel, {}).setdefault(w, [0, []])
            freq[head][rel][w][0] += 1
            freq[head][rel][w][1].append(sid)
        
    #phead = prel = None
    
    mysql = MySQL(db_name, encoding=util.UTF8, output=sqlfile)
    mysql.create_table(MYSQL_TABLE, drop=False, **MYSQL_RELATIONS)
    mysql.lock([MYSQL_TABLE])
    
    #conn = sqlite.connect(out)
    #c = conn.cursor()
    #c.execute("DROP TABLE IF EXISTS relations")
    #c.execute("CREATE TABLE relations (head TEXT, rel TEXT, dep TEXT, freq INTEGER, sources TEXT, corpus TEXT)")

    #with open("relationer.txt", "w") as F:
    for head, rels in freq.iteritems():
        for rel, w in rels.iteritems():
            for w, count_and_sid in sorted(w.iteritems(), key=lambda x: -x[1][0]):
                count, sids = count_and_sid
                sids = ";".join(sids)
                head_lem, head_pos = head.split(u"^")
                w_lem, w_pos = w.split(u"^")
                if count >= min_count and head_pos in pos_filter and w_pos in pos_filter and rel in rel_filter:
                    #printhead = u"." if head == phead else head_lem
                    #printrel  = u"." if head == phead and rel == prel else rel
                    #phead = head
                    #prel  = rel
                    #print >>F, ("%50s %5s   %-50s %5d %s" % (printhead, printrel, w_lem, count, sids)).encode("UTF-8")
                    #c.execute("""INSERT INTO relations VALUES ("%s", "%s", "%s", "%d", "%s", "%s")""" % (head_lem, rel, w_lem, count, sids, corpus.upper()))
                    row= {"head": head_lem,
                          "rel": rel,
                          "dep": w_lem,
                          "freq": count,
                          "corpus": corpus.upper()
                          }
                    mysql.add_row(MYSQL_TABLE, row)
    mysql.unlock()
    #conn.commit()
    #c.close()

################################################################################

MYSQL_TABLE = "relations"

MYSQL_RELATIONS = {'columns': [("head",   "varchar(1024)", "", "NOT NULL"),
                               ("rel",    "char(2)", "", "NOT NULL"),
                               ("dep",    "varchar(1024)", "", "NOT NULL"),
                               ("freq",   int, None, ""),
                               ("corpus", str, "", "NOT NULL")],
               'keys': [],
               'default charset': 'utf8',
               }

################################################################################    

if __name__ == '__main__':
    util.run.main(relations, frequency=frequency)
