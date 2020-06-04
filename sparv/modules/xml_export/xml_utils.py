"""Util functions for XML export."""

import bz2
import io
import logging
import os
import xml.etree.ElementTree as etree
from collections import defaultdict

import sparv.util as util

log = logging.getLogger(__name__)

INDENTATION = "  "


def make_pretty_xml(span_positions, annotation_dict, export_names, token, word_annotation, docid):
    """Create a pretty formatted XML string from span_positions.

    Used by pretty and sentence_scrambled.
    """
    # Root tag sanity check
    if not valid_root(span_positions[0], span_positions[-1]):
        raise util.SparvErrorMessage("Root tag is missing! If you have manually specified which elements to include, "
                                     "make sure to include an element that encloses all other included elements and "
                                     "text content.")

    # Create root node
    root_span = span_positions[0][2]
    root_span.set_node()
    add_attrs(root_span.node, root_span.name, annotation_dict, export_names, 0)
    node_stack = [root_span]
    overlap_ids = defaultdict(int)  # Keeps track of which overlapping spans belong together
    total_overlaps = 0

    # Go through span_positions and build xml tree
    for _pos, instruction, span in span_positions[1:]:

        # Create child node under the top stack node
        if instruction == "open":
            span.set_node(parent_node=node_stack[-1].node)
            node_stack.append(span)
            add_attrs(span.node, span.name, annotation_dict, export_names, span.index)
            # Add text if this node is a token
            if span.name == token:
                span.node.text = word_annotation[span.index]

        # Close node
        else:
            # Closing node == top stack node: pop stack and move on to next span
            if span == node_stack[-1]:
                node_stack.pop()

            # Handle overlapping spans
            else:
                total_overlaps = handle_overlaps(span, node_stack, docid, overlap_ids, total_overlaps, annotation_dict,
                                                 export_names)

    # Pretty formatting of XML tree
    indent(root_span.node)

    # We use write() instead of tostring() here to be able to get an XML declaration
    stream = io.StringIO()
    etree.ElementTree(root_span.node).write(stream, encoding="unicode", method="xml", xml_declaration=True)
    return stream.getvalue()


def indent(elem, level=0) -> None:
    """Add pretty-print indentation to XML tree.

    From http://effbot.org/zone/element-lib.htm#prettyprint
    """
    i = "\n" + level * INDENTATION
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + INDENTATION
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def valid_root(first_item, last_item):
    """Check the validity of the root tag."""
    return (first_item[1] == "open"
            and last_item[1] == "close"
            and first_item[2].name == last_item[2].name
            and first_item[2].index == last_item[2].index)


def add_attrs(node, annotation, annotation_dict, export_names, index):
    """Add attributes from annotation_dict to node."""
    for name, annot in annotation_dict[annotation].items():
        export_name = export_names.get(":".join([annotation, name]), name)
        node.set(export_name, annot[index])


def handle_overlaps(span, node_stack, docid, overlap_ids, total_overlaps, annotation_dict, export_names):
    """Close and open overlapping spans in correct order and add IDs to them."""
    overlap_stack = []
    # Close all overlapping spans and add and _overlap attribute to them
    while node_stack[-1] != span:
        overlap_elem = node_stack.pop()
        total_overlaps += 1
        overlap_ids[overlap_elem.name] += total_overlaps
        overlap_attr = "{}-{}".format(docid, overlap_ids[overlap_elem.name])
        overlap_elem.node.set("_overlap", overlap_attr)
        overlap_stack.append(overlap_elem)
    node_stack.pop()  # Close current span

    # Re-open overlapping spans and add and _overlap attribute to them
    while overlap_stack:
        overlap_elem = overlap_stack.pop()
        overlap_elem.set_node(parent_node=node_stack[-1].node)
        overlap_attr = "{}-{}".format(docid, overlap_ids[overlap_elem.name])
        overlap_elem.node.set("_overlap", overlap_attr)
        node_stack.append(overlap_elem)
        add_attrs(overlap_elem.node, overlap_elem.name, annotation_dict, export_names, overlap_elem.index)

    return total_overlaps


def combine(corpus, out, docs, xml_input):
    """Combine xml_files into one single file."""
    xml_files = [xml_input.replace("{doc}", doc) for doc in docs]
    xml_files.sort()
    with open(out, "w") as outf:
        print('<corpus id="%s">' % corpus.replace("&", "&amp;").replace('"', "&quot;"), file=outf)
        for infile in xml_files:
            log.info("Read: %s", infile)
            with open(infile) as inf:
                print(inf.read(), file=outf)
        print("</corpus>", file=outf)
        log.info("Exported: %s" % out)


def compress(xmlfile, out):
    """Compress xmlfile to out."""
    with open(xmlfile) as f:
        file_data = f.read()
        compressed_data = bz2.compress(file_data.encode(util.UTF8))
    with open(out, "wb") as f:
        f.write(compressed_data)


def install_compressed_xml(corpus, xmlfile, out, export_path, host):
    """Install xml file on remote server."""
    if not host:
        raise(Exception("No host provided! Export not installed."))
    filename = corpus + ".xml.bz2"
    remote_file_path = os.path.join(export_path, filename)
    util.install_file(host, xmlfile, remote_file_path)
    util.write_common_data(out, "")
