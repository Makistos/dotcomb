from antlr4 import *
from DOTLexer import DOTLexer
from DOTListener import DOTListener
from DOTParser import DOTParser
import sys
import re
import logging
import pprint
import re

class DOTReader(DOTListener):

    _settings = {}
    _params = {}
    _curr_node = ''
    _curr_edge = ()

    nodes = {}
    edges = {}
    ignored_nodes = {}
    _file_edges = {}

    _patterns = []
    _ignore_list = []

    _file_mappings = {} # Maps NodeXX with real labels. Files might have different node names for same labels.

    def __init__(self, settings, params):
        self._settings = settings
        self._params = params
        self._patterns = [re.compile(x, re.LOCALE|re.MULTILINE) for x in self._settings['FILTERED_RE_NODES']]
        self._ignore_list = [re.compile(x, re.LOCALE|re.MULTILINE) for x in self._settings['FILTER_IGNORE']]

    def enterNode_stmt(self, ctx:DOTParser.Node_stmtContext):
        node_text = ctx.node_id().getText()
        self._curr_node = node_text
        self._curr_edge = ()

    def enterEdge_stmt(self, ctx:DOTParser.Edge_stmtContext):
        ''' Get the nodes for this edge '''
        self._curr_edge = (ctx.node_id().getText(),
                ctx.edgeRHS().getText()[2:])
        self._curr_node = ''

    def exitA_list(self, ctx:DOTParser.A_listContext):
        if self._curr_node != '':
            self._create_node(ctx)
        elif len(self._curr_edge) > 0:
            self._create_edge(ctx)

    def _node2label(self, x):
        if x in self._file_mappings:
            return self._file_mappings[x]
        else:
            return None

    def inv_keys(self, l, x):
        return l[(x[1], x[0])]

    def exitGraph(self, ctx:DOTParser.GraphContext):
        logging.debug('Exiting graph')
        new_edges = {}
        logging.debug('edges: %s', self._file_edges)
        for key, edge in self._file_edges.items():
            # Remove edges that don't have nodes
            if key[0] in self._file_mappings and key[1] in self._file_mappings:
                label1 = self._file_mappings[key[0]]
                label2 = self._file_mappings[key[1]]
                if self._show_node(label1) and self._show_node(label2):
                    new_edges[(label1, label2)] = edge
            else:
                logging.info('Removed %s -> %s', key[0], key[1])
                logging.info('\t%s', self._file_mappings)
        self._file_edges.clear()
        self._file_mappings.clear()
        for key, edge in new_edges.items():
            is_unique = not (key[1], key[0]) in self.edges
            logging.debug('is_unique: %s %s', is_unique, key)
            if key[0] != key[1]: # No self-referential edges
                if is_unique: # There is no edge going the other way
                    logging.info('Adding new unique edge %s', key)
                    self.edges[key] = edge
                else:
                    if self._params['bidir']:
                        logging.info('Altering existing edge %s', key)
                        self.edges[(key[1], key[0])]['dir'] = "both"
                    else:
                        logging.info('Adding new non-unique edge %s', key)
                        self.edges[key] = edge
            else:
                logging.debug('Removed self-referential link %s', key)

    def next_file(self):
        logging.debug('Next file')
        self._curr_node = ''
        self._curr_edge = ()

    def _create_node(self, ctx:DOTParser.A_listContext):
        logging.debug('Node %s', self._curr_node)
        attrs = {k: v for k,v in
                dict(zip([x.getText() for x in ctx.r_id()],
                         [x.getText() for x in ctx.v_id()])).items()
                if not k in self._settings['FILTERED_FIELDS']}
        self._set_params(attrs)
        if self._params['level'] == 0:
            label = attrs['label']
        else:
            label = '.'.join(attrs['label'].split('.')[0:self._params['level']])
            if label[-1] != '"':
                # If there are more parts in the label that level, then the
                # closing quotation mark disappears.
                label = label + '"'
        if not label in self.nodes and self._show_node(label):
            attrs['label'] = label
            self.nodes[label] = attrs
        if not self._curr_node in self._file_mappings:
            self._file_mappings[self._curr_node] = label

    def _create_edge(self, ctx:DOTParser.A_listContext):
        logging.debug('Edge %s -> %s', self._curr_edge[0], self._curr_edge[1])
        attrs = {k: v for k,v in
                dict(zip([x.getText() for x in ctx.r_id()],
                         [x.getText() for x in ctx.v_id()])).items()}
        n1 = self._curr_edge[0]
        n2 = self._curr_edge[1]
        self._file_edges[(n1, n2)] = attrs
        #logging.debug('Edges: %s', self._file_edges)

    def _edge_exists(self, node1, node2):
        return ((node1, node2) in self.edges or (node2, node1) in self.edges)

    def _set_params(self, node):
        """
        Set some node parameters. This will set the color and group (if node fits
        into one).
        """
        found = False
        pkg = self._pkg_name(node['label'])
        if not self._settings['PACKAGE_COLORS'] is None:
            if pkg in self._settings['PACKAGE_COLORS']:
                node['color'] = self._settings['PACKAGE_COLORS'][pkg]
                found = True
        if not self._settings['PROBLEM_NODES'] is None:
            if len([x for x in self._settings['PROBLEM_NODES'] if node['label'].find(x) != -1]) > 0:
                node['color'] = self._settings['PACKAGE_COLORS']['problem']
                found = True
        if found == False:
            node['color'] = self._settings['PACKAGE_COLORS']['other']
        group = self._pkg_name(node['label'])
        if group != '':
            node['group'] = group.replace('.', '')
        if 'fillcolor' in node:
            del node['fillcolor']
        if 'fontcolor' in node:
            del node['fontcolor']

    def _show_node(self, node_label):
        """
        Checks whether given node should be shown in the graph. Nodes are filtered
        with FILTERED_RE_NODES (regular expression matching) and
        FILTERED_EXACT_NODES (exact string match).
        """
        if self._params['filter'] == True:
            for p in self._ignore_list:
                m = p.match(node_label)
                if m:
                    logging.info('Allowing %s', node_label)
                    return True
            for p in self._patterns:
                m = p.match(node_label)
                if m:
                    logging.debug('Ignoring node %s', node_label)
                    self.ignored_nodes[node_label] = node_label
                    return False
            if node_label.replace('"', '') in self._settings['FILTERED_EXACT_NODES']:
                logging.debug('Ignoring node %s', node_label)
                self.ignored_nodes[node_label] = node_label
                return False
            return True
        else:
            return True

    def has_edges(self, node_label):
        """
        Checks if given node name has any edges. Nodes with no edges are not added
        to the graph.
        """
        return len([
            k for k in self._edges.keys() if k[0] == node_label or k[1] == node_label]) > 0

    def _pkg_name(self, x):
        """
        Returns matching clustering value or empty string is string doesn't
        match pattern.
        """
        p = re.findall(self._settings['GROUP_RE_PATTERN'], x)
        if p:
            return p[0]
        else:
            return ''

