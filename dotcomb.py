#!/usr/bin/python3

import sys
import glob
import re
import pprint
from collections import namedtuple
import argparse
import itertools
import yaml
from DOTReader import *
from DOTLexer import DOTLexer
from DOTParser import DOTParser
import logging

params = {}

file_mappings = {}
settings_file = 'settings.yaml'
settings = {}
printer = None


def pkg_name(x):
    """
    Returns matching clustering value or empty string is string doesn't
    match pattern.
    """
    p = re.findall(settings['GROUP_RE_PATTERN'], x)
    if p:
        return p[0]
    else:
        return ''


def read_params(args):
    """ Handle command-line parameters."""
    p = argparse.ArgumentParser()
    p.add_argument('--filter', '-f', help='Filter graph.', action='store_true',
            default=False)
    p.add_argument('--cluster', '-c', help='Cluster packages together.',
            action='store_true', default=False)
    p.add_argument('--directory', '-d', help='Work directory. Output is '
            'to stdout.', default='./');
    return vars(p.parse_args(args))


def show_node(node_label):
    """
    Checks whether given node should be shown in the graph. Nodes are filtered
    with FILTERED_RE_NODES (regular expression matching) and
    FILTERED_EXACT_NODES (exact string match).
    """
    if params['filter'] is True:
        if len([x for x in settings['FILTERED_RE_NODES'] if node_label.find(x) != -1]) > 0:
            return False
        if node_label in settings['FILTERED_EXACT_NODES']:
            return False
        return True
    else:
        return True


def set_params(node):
    """
    Set some node parameters. This will set the color and group (if node fits
    into one).
    """
    found = False
    pkg = pkg_name(node['label'])
    if not settings['PACKAGE_COLORS'] is None:
        if pkg in settings['PACKAGE_COLORS']:
            node['color'] = settings['PACKAGE_COLORS'][pkg]
            found = True
    if not settings['PROBLEM_NODES'] is None:
        if len([x for x in settings['PACKAGE_COLORS'] if node['label'].find(x)]) > 0:
            node['color'] = settings['PACKAGE_COLORS']['problem']
            found = True
    if found == False:
        node['color'] = settings['PACKAGE_COLORS']['other']
    group = pkg_name(node['label'])
    if group != '':
        node['group'] = group.replace('.', '')


def has_edges(node_label, edges):
    """
    Checks if given node name has any edges. Nodes with no edges are not added
    to the graph.
    """
    return len([
        k for k in edges.keys() if k[0] == node_label or k[1] == node_label]) > 0


def create_node(node):
    """
    Creates the nodes as a data structure where key is the node label
    and value is a dictionary holding all the other values. This function
    also updates the file specific file_mappings dictionary that is used to convert NodeXX
    to node label (these are different for each file).
    """
    d = {}
    v = ''
    k = ''
    items = node.group(2).split(',\n')
    for item in items:
        parts = item.split('=')
        k = parts[0].lstrip()
        v = parts[1].lstrip()
        if k not in settings['FILTERED_FIELDS']:
            d[k] = v
    if 'fillcolor' in d:
        del d['fillcolor']
    set_params(d)
    if not node.group(1) in file_mappings:
        file_mappings[node.group(1)] = d['label']
    if not d['label'] in nodes and show_node(d['label']):
        nodes[d['label']] = d


edge_exists = lambda node1, node2: (node1, node2) in edges or (node2,
    node1) in edges


def create_edge(edge):
    """
    Creates the edges as a data structure where the key is a tuple
    consisting of the two nodes (converted to their real names instead of
    NodeXX) and a dictionary holding the other values.

    Also makes sure edges are only added once and that each edge has a
    starting point and ending point in the graph.
    """
    d = {}
    v = ''
    k = ''
    items = edge.group(3).split(',\n')
    for item in items:
        parts = item.split('=')
        k = parts[0].lstrip()
        v = parts[1].lstrip()
        d[k] = v
    if edge.group(1) in file_mappings and edge.group(2) in file_mappings:
        n1 = file_mappings[edge.group(1)]
        n2 = file_mappings[edge.group(2)]
        if (not (edge_exists(n1, n2))) and show_node(n1) and show_node(n2):
            edges[(n1, n2)] = d


def print_node(key, node, edges):
    """
    Prints a single node.
    """
    if has_edges(key, edges):
        print("\t{}\n\t\t[{}];\n".format(key, ',\n\t\t'.join([key+'='+v for
            key,v in sorted(node[1].items())])))


cluster = 0


def print_subgraph(k, g, edges):
    """
    Prints subgraph info if -c command-line parameter was supplied, otherwise
    just prints each node in a group at once.
    """
    global cluster
    if params['cluster']:
        print('\tsubgraph cluster_{} {{'.format(cluster))
        if len(k) > 0:
            print('\t\tlabel={};'.format(k))
            print('\t\tfontsize=48;')
        else:
            print('\t\tlabel=\"\";')
    for node in g:
        print_node(node[0], node, edges)
    if params['cluster']:
        print('\t}')
        cluster = cluster + 1


def sort_func(x):
    """
    Return package name if clustering is defined, otherwise label name in lower case
    """
    if params['cluster'] is True:
        return pkg_name(x[0].lower())
    else:
        return x[0].lower()


def print_nodes(nodes, edges):
    """
    Prints all nodes sorted by group.
    """
    sorted_nodes = [d for d in nodes.items()]
    sorted_nodes.sort(key=sort_func)
    for k,v in itertools.groupby(sorted_nodes, sort_func):
        print_subgraph(k,list(v), edges)


def print_edges(edges):
    """
    Prints all edges.
    """
    # Remove quotes and convert to lower case for a more logical order
    sorted_edges = sorted(edges.items(), key=lambda k: (k[0][0]+k[0][1]).replace('"', '').lower())
    logging.info(sorted_edges)
    for k, v in sorted_edges:
        sorted_values = sorted(v.items())
        print("\t{} -> {}\n\t\t[{}];\n".format(k[0], k[1], ',\n\t\t'.join([k+'='+v2 for
            k,v2 in sorted_values])))


def print_legend(components):
    print('\t{ rank=same; 0 [style=invis] }'
                '\n\tedge [style=invis];'
                '\n\tfontcolor=black;\n')
    nodes = ' -> '.join(sorted(components)).replace('.', '')
    print('\t{};'.format(nodes))
    for c in sorted(components):
        component = c.replace('.', '')
        print('\t{} [label={}, color={}, style=filled, fontsize=24];'
                .format(component, component, components[c]))


def main(argv):
    global params
    global settings
    nodes = {}
    edges = {}

    logging.basicConfig(filename='dotcomb.log', filemode='w', level=logging.DEBUG)

    params = read_params(argv)

    with open(settings_file, 'r') as f:
        settings = yaml.load(f)

    input_path = params['directory'] + '/**/*__coll*.dot'
    files = glob.glob(input_path, recursive=True)
    for fname in files:
        inp = FileStream(fname)
        lexer = DOTLexer(inp)
        stream = CommonTokenStream(lexer)
        parser = DOTParser(stream)
        tree = parser.graph()
        printer = DOTReader(settings, params)
        walker = ParseTreeWalker()
        walker.walk(printer, tree)
        nodes = {**nodes, **printer.nodes}
        edges = {**edges, **printer.edges}
        logging.info('%s: nodes %s, edges %s',
                fname, len(printer.nodes), len(printer.edges))
        logging.debug("%s", pprint.pformat(printer.edges))
        printer.next_file()

    cleaned_edges = {}
    cleaned_nodes = {}
    # Remove edges that have no nodes
    #cleaned_edges = {(n1, n2):v for ((n1, n2),v) in edges.items() if (n1 in nodes) and (n2 in nodes)}
    for (n1, n2), edge in edges.items():
        if (n1 in nodes) and (n2 in nodes):
            cleaned_edges[(n1, n2)] = edge
    for key, node in nodes.items():
        if has_edges(key, cleaned_edges):
            cleaned_nodes[key] = node

    logging.info('Nodes: %s, edges: %s', len(nodes), len(edges))
    print("{}".format(settings['HEADER']))
    print_nodes(cleaned_nodes, edges)
    print_edges(cleaned_edges)
    if params['cluster'] == False and 'PACKAGE_COLORS' in settings:
        print_legend(settings['PACKAGE_COLORS'])
    print("{}".format(settings['FOOTER']))


if __name__ == '__main__':
    main(sys.argv[1:])
