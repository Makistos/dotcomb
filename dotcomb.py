#!/usr/bin/python3

import sys
import glob
import re
#import pprint
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
cluster = 0


def read_params(args):
    """ Handle command-line parameters."""
    p = argparse.ArgumentParser()
    p.add_argument('--filter', '-f', help='Filter graph.', action='store_true',
            default=True)
    p.add_argument('--level', '-l', help='Graph level', type=int, default=4)
    p.add_argument('--bidir', '-b', help='Non-directional graph',
            action='store_true', default=True)
    p.add_argument('--cluster', '-c', help='Cluster packages together.',
            action='store_true', default=False)
    p.add_argument('--directory', '-d', help='Work directory. Output is '
            'to stdout.',
            default='/home/mep/src/Cardiac-Navigator/workspace/cardiscope-framework/)');
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
        if node_label.replace('"', '') in settings['FILTERED_EXACT_NODES']:
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


def print_node(key, node, edges):
    """
    Prints a single node.
    """
    if has_edges(key, edges):
        print("\t{}\n\t\t[{}];\n".format(key, ',\n\t\t'.join([key+'='+v for
            key,v in sorted(node[1].items())])))


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
    arrow = '->'
    # Remove quotes and convert to lower case for a more logical order
    sorted_edges = sorted(edges.items(), key=lambda k: (k[0][0]+k[0][1]).replace('"', '').lower())
    for k, v in sorted_edges:
        sorted_values = sorted(v.items())
        print("\t{} {} {}\n\t\t[{}];\n".format(k[0], arrow, k[1], ',\n\t\t'.join([k+'='+v2 for
            k,v2 in sorted_values])))


def print_legend(components):
    print('\t{ rank=same; 0 [style=invis] }'
                '\n\tedge [style=invis];'
                '\n\tfontcolor=black;\n')
    nodes = '->'.join(sorted(components)).replace('.', '')
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

    logging.basicConfig(filename='dotcomb.log', filemode='w', level=logging.INFO)

    params = read_params(argv)

    with open(settings_file, 'r') as f:
        settings = yaml.load(f)

    #input_path = params['directory'] + '/**/*__coll*.dot'
    input_path = params['directory'] + '/**/*_cgraph*.dot'
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
        #logging.debug("%s", pprint.pformat(printer.edges))
        printer.next_file()

    cleaned_edges = {}
    cleaned_nodes = {}
    # Remove edges that have no nodes
    #cleaned_edges = {(n1, n2):v for ((n1, n2),v) in edges.items() if (n1 in nodes) and (n2 in nodes)}
    for (n1, n2), edge in edges.items():
        if show_node(n1) and show_node(n2):
            if (n1 in nodes) and (n2 in nodes):
                cleaned_edges[(n1, n2)] = edge
    for key, node in nodes.items():
        if has_edges(key, cleaned_edges):
            cleaned_nodes[key] = node

    node_names = []
    for k,v in cleaned_nodes.items():
        node_names.append(k)
    logging.info('Node list: %s', '\n'.join(node_names))
    logging.info('Filter list: %s', settings['FILTERED_EXACT_NODES'])
    logging.info('Nodes: %s, edges: %s', len(cleaned_nodes), len(cleaned_edges))
    print("{}".format(settings['HEADER']))
    print_nodes(cleaned_nodes, edges)
    print_edges(cleaned_edges)
    if params['cluster'] is False and 'PACKAGE_COLORS' in settings:
        print_legend(settings['PACKAGE_COLORS'])
    print("{}".format(settings['FOOTER']))


if __name__ == '__main__':
    main(sys.argv[1:])
