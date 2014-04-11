# -*- coding: utf-8 -*-

"""
Add annotations for parent links and/or children links.
"""

from collections import defaultdict
import util


def annotate_parents(text, out, parent, child, ignore_missing_parent=False):
    """Annotate parent links; parent, child are names for existing annotations.
    """
    if isinstance(ignore_missing_parent, basestring):
        ignore_missing_parent = (ignore_missing_parent.lower() == "true")
    parent_chunks, child_spans = read_parents_and_children(text, parent, child)
    OUT = {}
    previous_parent_id = None
    try:
        parent_span, parent_id = parent_chunks.next()
        for child_span, child_id in child_spans:
            while child_span.stop > parent_span.stop:
                if parent_id:
                    previous_parent_id = parent_id
                parent_span, parent_id = parent_chunks.next()
            if not parent_id or parent_span.start > child_span.start:
                if not ignore_missing_parent:
                    util.log.warning("Child '%s' missing parent; closest parent is %s",
                                     child_id, parent_id or previous_parent_id)
                parent_id = ""
            OUT[child_id] = parent_id
    except StopIteration:
        pass
    util.write_annotation(out, OUT)


def annotate_children(text, out, parent, child, ignore_missing_parent=False):
    """Annotate links to children; parent, child are names for existing annotations.
    """
    parent_chunks, child_spans = read_parents_and_children(text, parent, child)
    OUT = defaultdict(list)
    previous_parent_id = None
    try:
        parent_span, parent_id = parent_chunks.next()
        for child_span, child_id in child_spans:
            while child_span.stop > parent_span.stop:
                if parent_id:
                    previous_parent_id = parent_id
                parent_span, parent_id = parent_chunks.next()
            if not parent_id or parent_span.start > child_span.start:
                if not ignore_missing_parent:
                    util.log.warning("Child '%s' missing parent; closest parent is %s",
                                     child_id, parent_id or previous_parent_id)
                parent_id = ""
            OUT[parent_id].append(child_id)
    except StopIteration:
        pass
    util.write_annotation(out, OUT, encode=" ".join)


def read_parents_and_children(text, parent, child):
    corpus_text, anchor2pos, _pos2anchor = util.corpus.read_corpus_text(text)
    mkSpan = lambda edge: slice(anchor2pos[util.edgeStart(edge)], anchor2pos[util.edgeEnd(edge)])
    parent_spans = sorted((mkSpan(p), p) for p in util.read_annotation_iterkeys(parent))
    parent_chunks = extract_chunks(parent_spans, corpus_text)
    child_spans = sorted((mkSpan(c), c) for c in util.read_annotation_iterkeys(child))
    return parent_chunks, child_spans


def extract_chunks(chunks, text):
    pos = 0
    stack = [(len(text), None)]
    END, ID = 0, 1
    for chunk_span, chunk_id in chunks:
        while stack[-1][END] <= chunk_span.start:
            end, edge = stack.pop()
            span = slice(pos, end)
            if text[span].strip():
                yield span, edge
            pos = end
        end = chunk_span.start
        if pos < end:
            span = slice(pos, end)
            if text[span].strip():
                yield span, stack[-1][ID]
            pos = end
        stack.append((chunk_span.stop, chunk_id))
    while stack:
        end, edge = stack.pop()
        if pos < end:
            span = slice(pos, end)
            if text[span].strip():
                yield span, edge
            pos = end


######################################################################

if __name__ == '__main__':
    util.run.main(parents=annotate_parents,
                  children=annotate_children)
