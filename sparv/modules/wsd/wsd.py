"""Word sense disambiguation based on SALDO annotation."""

import logging

import sparv.util as util
from sparv import Annotation, Binary, Document, Model, Output, annotator

log = logging.getLogger(__name__)

SENT_SEP = "$SENT$"


@annotator("Word sense disambiguation")
def run_wsd(doc: str = Document,
            wsdjar: str = Binary("[wsd.jar=wsd/saldowsd.jar]"),
            sense_model: str = Model("[wsd.sense_model=wsd/ALL_512_128_w10_A2_140403_ctx1.bin]"),
            context_model: str = Model("[wsd.context_model=wsd/lem_cbow0_s512_w10_NEW2_ctx.bin]"),
            out: str = Output("<token>:wsd.sense", cls="token:sense", description="Sense disambiguated SALDO identifiers"),
            sentence: str = Annotation("<sentence>"),
            word: str = Annotation("<token:word>"),
            ref: str = Annotation("<token>:misc.number_rel_<sentence>"),
            lemgram: str = Annotation("<token>:saldo.lemgram"),
            saldo: str = Annotation("<token>:saldo.sense"),
            pos: str = Annotation("<token:pos>"),
            token: str = Annotation("<token>"),
            sensefmt: str = util.SCORESEP + "%.3f",
            default_prob: float = -1.0,
            encoding: str = util.UTF8):
    """Run the word sense disambiguation tool (saldowsd.jar) to add probabilities to the saldo annotation.

    Unanalyzed senses (e.g. multiword expressions) receive the probability value given by default_prob.
      - wsdjar is the name of the java programme to be used for the wsd
      - sense_model and context_model are the models to be used with wsdjar
      - out is the resulting annotation file
      - sentence is an existing annotation for sentences and their children (words)
      - word is an existing annotations for wordforms
      - ref is an existing annotation for word references
      - lemgram and saldo are existing annotations for inflection tables and meanings
      - pos is an existing annotations for part-of-speech
      - sensefmt is a format string for how to print the sense and its probability
      - default_prob is the default value for unanalyzed senses
    """
    word_annotation = list(util.read_annotation(doc, word))
    ref_annotation = list(util.read_annotation(doc, ref))
    lemgram_annotation = list(util.read_annotation(doc, lemgram))
    saldo_annotation = list(util.read_annotation(doc, saldo))
    pos_annotation = list(util.read_annotation(doc, pos))

    sentences, orphans = util.get_children(doc, sentence, token)
    sentences.append(orphans)

    # Start WSD process
    process = wsd_start(wsdjar, sense_model, context_model, encoding)

    # Construct input and send to WSD
    stdin = build_input(sentences, word_annotation, ref_annotation, lemgram_annotation, saldo_annotation,
                        pos_annotation)

    if encoding:
        stdin = stdin.encode(encoding)

    stdout, stderr = process.communicate(stdin)
    # TODO: Solve hack line below!
    # Problem is that regular messages "Reading sense vectors.." are also piped to stderr.
    if len(stderr) > 52:
        util.system.kill_process(process)
        log.error(str(stderr))
        return

    if encoding:
        stdout = stdout.decode(encoding)

    process_output(doc, word, out, stdout, sentences, saldo_annotation, sensefmt, default_prob)

    # Kill running subprocess
    util.system.kill_process(process)
    return


def wsd_start(wsdjar, sense_model, context_model, encoding):
    """Start a wsd process and return it."""
    java_opts = ["-Xmx6G"]
    wsd_args = [("-appName", "se.gu.spraakbanken.wsd.VectorWSD"),
                ("-format", "tab"),
                ("-svFile", sense_model),
                ("-cvFile", context_model),
                ("-s1Prior", "1"),
                ("-decay", "true"),
                ("-contextWidth", "10"),
                ("-verbose", "false")]

    process = util.system.call_java(wsdjar, wsd_args, options=java_opts,
                                    stdin="", encoding=encoding,
                                    return_command=True)
    return process


def build_input(sentences, word_annotation, ref_annotation, lemgram_annotation, saldo_annotation, pos_annotation):
    """Construct tab-separated input for WSD."""
    rows = []
    for sentence in sentences:
        for token_index in sentence:
            mwe = False
            word = word_annotation[token_index]
            ref = ref_annotation[token_index]
            pos = pos_annotation[token_index].lower()
            saldo = saldo_annotation[token_index].strip(util.AFFIX) if saldo_annotation[
                token_index] != util.AFFIX else "_"
            if "_" in saldo and len(saldo) > 1:
                mwe = True

            lemgram, simple_lemgram = make_lemgram(lemgram_annotation[token_index], word, pos)

            if mwe:
                lemgram = remove_mwe(lemgram)
                simple_lemgram = remove_mwe(simple_lemgram)
                saldo = remove_mwe(saldo)
            row = "\t".join([ref, word, "_", lemgram, simple_lemgram, saldo])
            rows.append(row)
        # Append empty row as sentence seperator
        rows.append("\t".join(["_", "_", "_", "_", SENT_SEP, "_"]))
    return "\n".join(rows)


def process_output(doc, word, out, stdout, in_sentences, saldo_annotation, sensefmt, default_prob):
    """Parse WSD output and write annotation."""
    out_annotation = util.create_empty_attribute(doc, word)

    # Split output into sentences
    out_sentences = stdout.strip()
    out_sentences = out_sentences.split("\t".join(["_", "_", "_", "_", SENT_SEP, "_", "_"]))
    out_sentences = [i for i in out_sentences if i]

    # Split output into tokens
    for out_sent, in_sent in zip(out_sentences, in_sentences):
        out_tokens = [t for t in out_sent.split("\n") if t]
        for (out_tok, in_tok) in zip(out_tokens, in_sent):
            out_prob = out_tok.split("\t")[6]
            out_prob = [i for i in out_prob.split("|") if i != "_"]
            out_meanings = [i for i in out_tok.split("\t")[5].split("|") if i != "_"]
            saldo = [i for i in saldo_annotation[in_tok].strip(util.AFFIX).split(util.DELIM) if i]

            new_saldo = []
            if out_prob:
                for meaning in saldo:
                    if meaning in out_meanings:
                        i = out_meanings.index(meaning)
                        new_saldo.append(meaning + sensefmt % float(out_prob[i]))
                    else:
                        new_saldo.append(meaning + sensefmt % default_prob)
            else:
                new_saldo = [meaning + sensefmt % default_prob for meaning in saldo]

            # Sort by probability
            new_saldo = sorted(new_saldo, key=lambda x: float(x.split(":")[-1]), reverse=True)
            out_annotation[in_tok] = util.cwbset(new_saldo)

    util.write_annotation(doc, out, out_annotation)


def make_lemgram(lemgram, word, pos):
    """Construct lemgram and simple_lemgram format."""
    lemgram = lemgram.strip(util.AFFIX) if lemgram != util.AFFIX else "_"
    simple_lemgram = util.DELIM.join(set((l[:l.rfind(".")] for l in lemgram.split(util.DELIM))))

    # Fix simple lemgram for tokens without lemgram (word + pos)
    if not simple_lemgram:
        simple_lemgram = word + ".." + pos
    return lemgram, simple_lemgram


def remove_mwe(annotation):
    """For MWEs: strip unnecessary information."""
    annotation = annotation.split(util.DELIM)
    annotation = [i for i in annotation if "_" not in i]
    if annotation:
        return util.DELIM.join(annotation)
    else:
        return "_"
