from antlr4 import *
from DOTLexer import DOTLexer
from DOTListener import DOTListener
from DOTParser import DOTParser
import sys
import re


class DOTReader(DOTListener):

    _settings = {}
    _params = {}
    _curr_node = ''
    _curr_edge = ''
    _curr_edge2 = ''

    nodes = {}
    edges = {}
    _file_mappings = {}

    def __init__(self, settings, params):
        self._settings = settings
        self._params = params

    def enterNode_stmt(self, ctx:DOTParser.Node_stmtContext):
        self._curr_node = ctx.node_id().getText()
        self._curr_edge = ''

    def enterEdge_stmt(self, ctx:DOTParser.Edge_stmtContext):
        self._curr_edge = ctx.node_id().getText()
        self._curr_edge2 = ctx.edgeRHS().getText()[2:]
        self._curr_node = ''

    def exitA_list(self, ctx:DOTParser.A_listContext):
        if self._curr_node != '':
            self._create_node(ctx)
        elif self._curr_edge != '':
            self._create_edge(ctx)

    def next_file(self):
        self.nodes.clear()
        self.edges.clear()
        self._file_mappings.clear()
        self._curr_node = ''
        self._curr_edge = ''
        self._curr_edge2 = ''

    def _create_node(self, ctx:DOTParser.A_listContext):
        attrs = {k: v for k,v in
                dict(zip([x.getText() for x in ctx.r_id()],
                         [x.getText() for x in ctx.v_id()])).items()
                if not k in self._settings['FILTERED_FIELDS']}
        self._set_params(attrs)
        label = attrs['label']
        if not self._curr_node in self._file_mappings:
            self._file_mappings[self._curr_node] = label
        if not label in self.nodes and self._show_node(label):
            self.nodes[label] = attrs

    def _create_edge(self, ctx:DOTParser.A_listContext):
        attrs = {k: v for k,v in
                dict(zip([x.getText() for x in ctx.r_id()],
                         [x.getText() for x in ctx.v_id()])).items()}
        if self._curr_edge in self._file_mappings and self._curr_edge2 in self._file_mappings:
            n1 = self._file_mappings[self._curr_edge]
            n2 = self._file_mappings[self._curr_edge2]
            self.edges[(n1, n2)] = attrs

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
            if len([x for x in self._settings['FILTERED_RE_NODES'] if node_label.find(x) != -1]) > 0:
                return False
            if node_label in self._settings['FILTERED_EXACT_NODES']:
                return False
            return True
        else:
            return True
            pass

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

