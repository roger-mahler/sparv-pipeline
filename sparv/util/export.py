"""Util functions for corpus export."""

from collections import defaultdict
from itertools import combinations
from sparv.util import corpus, parent


def gather_annotations(doc, annotations):
    """Calculate the span hierarchy and the annotation_dict containing all annotation elements and attributes."""
    annotation_dict = defaultdict(dict)
    spans_list = []
    for annotation_pointer in annotations:
        span_name, attr = corpus.split_annotation(annotation_pointer)
        if span_name not in annotation_dict:
            # This is necessary, span_name needs to be in the dictionary
            annotation_dict[span_name]["@span"] = None
            for i, s in enumerate(corpus.read_annotation_spans(doc, span_name, decimals=False)):
                # TODO: sub positions need to be considered...
                # start_pos, end_pos = s
                # start_pos = float(".".join(str(ele) for ele in s[0]))
                # end_pos = float(".".join(str(ele) for ele in s[1]))
                # spans_list.append(((start_pos, end_pos), span_name, i))
                spans_list.append((s, span_name, i))
        if attr and not annotation_dict[span_name].get(attr):
            a = list(corpus.read_annotation(doc, annotation_pointer))
            annotation_dict[span_name][attr] = a

    elem_hierarchy = calculate_element_hierarchy(doc, spans_list)

    def sort_spans(span):
        """Create a sorting key from a span.

        Sort spans according to their position and hierarchy. Sort by:
        1. start position (smaller indices first)
        2. end position (larger indices first)
        3. the calculated element hierarchy
        """
        pos, name, _i = span
        hierarchy_index = elem_hierarchy.index(name) if name in elem_hierarchy else -1
        return (pos[0], - pos[1], hierarchy_index)

    sorted_spans = sorted(spans_list, key=sort_spans)
    return sorted_spans, annotation_dict


def calculate_element_hierarchy(doc, spans_list):
    """Calculate the hierarchy for spans with identical start and end positions.

    If two spans A and B have identical start and end positions, go through all occurences of A and B
    and check which element is most often parent to the other. That one will be first.
    """
    # Find elements with identical spans
    span_duplicates = defaultdict(set)
    for span in spans_list:
        span_duplicates[span[0]].add(span[1])
    span_duplicates = [v for k, v in span_duplicates.items() if len(v) > 1]

    # Flatten structure
    unclear_spans = set([elem for elem_set in span_duplicates for elem in elem_set])

    # Read all annotation spans for quicker access later
    read_items = {}
    for span in unclear_spans:
        read_items[span] = sorted(enumerate(corpus.read_annotation_spans(doc, span, decimals=True)), key=lambda x: x[1])

    # Get pairs of relations that need to be ordered
    relation_pairs = list(combinations(unclear_spans, r=2))
    # Order each pair into [parent, children]
    ordered_pairs = set()
    for a, b in relation_pairs:
        a_parent = len([i for i in (parent.get_parents(doc, read_items[a], read_items[b])) if i is not None])
        b_parent = len([i for i in (parent.get_parents(doc, read_items[b], read_items[a])) if i is not None])
        if a_parent > b_parent:
            ordered_pairs.add((a, b))
        else:
            ordered_pairs.add((b, a))

    hierarchy = []
    error_msg = "Something seems to go wrong when sorting annotation elements. Could there be circular relations?"
    # Loop until all unclear_spans are processed
    while unclear_spans:
        size = len(unclear_spans)
        for span in unclear_spans.copy():
            # Span is never a child in ordered_pairs, then it is first in the hierarchy
            if not any([b == span for _a, b in ordered_pairs]):
                hierarchy.append(span)
                unclear_spans.remove(span)
                # Remove pairs from ordered_pairs where span is the parent
                for pair in ordered_pairs.copy():
                    if pair[0] == span:
                        ordered_pairs.remove(pair)
        # Check that unclear_spans is getting smaller, otherwise there might be circularity
        assert len(unclear_spans) == size - 1, error_msg
    return hierarchy