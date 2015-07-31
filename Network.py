#!/usr/bin/env python

# Network representation and basic operations
# Daniel Klein, 5/10/2012

from os import system, unlink
import numpy as np
import scipy.sparse as sparse
import networkx as nx
import matplotlib.pyplot as plt

from Covariate import NodeCovariate, EdgeCovariate

class Network:
    def __init__(self, N = None, M = None):
        if N:
            self.N = N
            if M:
                self.M = M
                self.bipartite = True
            else:
                self.M = N
                self.bipartite = False
            self.network = sparse.lil_matrix((self.M,self.N), dtype=np.bool)
            if self.bipartite:
                self.names = None
                self.rnames = np.array(['m_%d' % m for m in range(self.M)])
                self.cnames = np.array(['n_%d' % n for n in range(self.N)])
            else:
                self.names = np.array(['%d' % n for n in range(self.N)])
                self.rnames = None
                self.cnames = None
        else:
            self.M = 0
            self.N = 0
            self.bipartite = False
            self.network = None
            self.names = None
            self.rnames = None
            self.cnames = None

        # Offset intitially set to None so simpler offset-free model
        # code can be used by default
        self.offset = None
             
        # Maps from names to 1-D and 2-D arrays, respectively
        self.node_covariates = {}
        self.row_covariates = {}
        self.col_covariates = {}
        self.edge_covariates = {}

    def tocsr(self):
        if self.is_sparse():
            self.network = self.network.tocsr()
        else:
            print 'Attempting CSR conversion of a non-sparse network.'
            raise
            
    def new_node_covariate(self, name, as_int = False):
        self.node_covariates[name] = NodeCovariate(self.names)
        return self.node_covariates[name]

    def new_node_covariate_int(self, name):
        self.node_covariates[name] = NodeCovariate(self.names, dtype = np.int)
        return self.node_covariates[name]

    def new_row_covariate(self, name):
        self.row_covariates[name] = NodeCovariate(self.rnames)
        return self.row_covariates[name]

    def new_col_covariate(self, name):
        self.col_covariates[name] = NodeCovariate(self.cnames)
        return self.col_covariates[name]

    def new_edge_covariate(self, name):
        if self.bipartite:
            names_tuple = (self.rnames, self.cnames)
            self.edge_covariates[name] = EdgeCovariate(names_tuple)
        else:
            self.edge_covariates[name] = EdgeCovariate(self.names)
        return self.edge_covariates[name]

    def initialize_offset(self):
        if self.bipartite:
            names_tuple = (self.rnames, self.cnames)
            self.offset = EdgeCovariate(names_tuple)
        else:
            self.offset = EdgeCovariate(self.names)
        return self.offset

    def subnetwork(self, inds, sub_type = 'node'):
        if sub_type == 'node':
            if type(inds) == tuple:
                rinds = inds[0]
                cinds = inds[1]
                sub_M = len(rinds)
                sub_N = len(cinds)
            else:
                sub_M = len(inds)
                sub_N = len(inds)
                rinds = inds
                cinds = inds
        elif sub_type == 'row':
            rinds = inds
            sub_M = len(rinds)
            sub_N = self.N
            cinds = np.arange(sub_N)
        elif sub_type == 'col':
            cinds = inds
            sub_M = self.M
            sub_N = len(cinds)
            rinds = np.arange(sub_M)
        sub = Network()

        sub.bipartite = self.bipartite
        if self.is_sparse():
            self.tocsr()
        if type(inds) == tuple:
            sub.bipartite = True
            sub.network = self.network[rinds][:,cinds]
            sub.rnames = self.names[rinds]
            sub.cnames = self.names[cinds]
        elif sub_type == 'node':
            sub.network = self.network[inds][:,inds]
            sub.names = self.names[inds]
        else:
            sub.network = self.network[rinds][:,cinds]
            sub.rnames = self.rnames[rinds]
            sub.cnames = self.cnames[cinds]
        sub.M = sub_M
        sub.N = sub_N

        sub.node_covariates = {}
        sub.row_covariates = {}
        sub.col_covariates = {}
        sub.edge_covariates = {}
        if type(inds) == tuple:
            for node_covariate in self.node_covariates:
                src = self.node_covariates[node_covariate]
                sub.row_covariates[node_covariate] = src.subset(rinds)
                sub.col_covariates[node_covariate] = src.subset(cinds)
            for edge_covariate in self.edge_covariates:
                src = self.edge_covariates[edge_covariate]
                sub.edge_covariates[edge_covariate] = src.subset((rinds,cinds))
        elif sub_type == 'node':
            for node_covariate in self.node_covariates:
                src = self.node_covariates[node_covariate]
                sub.node_covariates[node_covariate] = src.subset(inds)
            for edge_covariate in self.edge_covariates:
                src = self.edge_covariates[edge_covariate]
                sub.edge_covariates[edge_covariate] = src.subset(inds)
        else:
            for row_covariate in self.row_covariates:
                src = self.row_covariates[row_covariate]
                sub.row_covariates[row_covariate] = src.subset(rinds)
            for col_covariate in self.col_covariates:
                src = self.col_covariates[col_covariate]
                sub.col_covariates[col_covariate] = src.subset(cinds)
            for edge_covariate in self.edge_covariates:
                src = self.edge_covariates[edge_covariate]
                sub.edge_covariates[edge_covariate] = src.subset((rinds,cinds))

        if self.offset:
            if type(inds) == tuple:
                sub.offset = self.offset.subset((rinds,cinds))
            elif sub_type == 'node':
                sub.offset = self.offset.subset(inds)
            else:
                sub.offset = self.offset.subset((rinds,cinds))
            
        return sub

    # Syntactic sugar to make network generation look like object mutation
    def generate(self, model, **opts):
        self.network = model.generate(self, **opts)

    def network_from_networkx(self, g, cov_names = []):
        self.N = g.number_of_nodes()
        self.names = np.array(g.nodes())
        self.network = sparse.lil_matrix((self.N,self.N), dtype=np.bool)

        name_to_index = {}
        for i, n in enumerate(self.names):
            name_to_index[n] = i
        for s, t in g.edges():
            self.network[name_to_index[s],name_to_index[t]] = True

        for cov_name in cov_names:
            nodes = g.nodes()
            covs = [g.node[n][cov_name] for n in nodes]
            self.new_node_covariate(cov_name).from_pairs(nodes, covs)
        
    def network_from_file_gexf(self, path, cov_names = []):
        in_network = nx.read_gexf(path)
        self.network_from_networkx(in_network, cov_names)

    def network_from_file_gml(self, path, cov_names = []):
        in_network = nx.read_gml(path)
        self.network_from_networkx(in_network, cov_names)

    def network_from_edges(self, edges):
        # First pass over edges to determine names and number of nodes
        names = set()
        N = 0
        for n_1, n_2 in edges:
            if not n_1 in names:
                names.add(n_1)
                N += 1
            if not n_2 in names:
                names.add(n_2)
                N += 1

        # Process list of names and assign indices
        self.M = N
        self.N = N
        self.network = sparse.lil_matrix((self.N,self.N), dtype=np.bool)
        self.names = np.array(list(names))
        name_to_index = {}
        for i, n in enumerate(self.names):
            name_to_index[n] = i

        # Second pass over edges to populate network
        for n_1, n_2 in edges:
            self.network[name_to_index[n_1],name_to_index[n_2]] = True

    def nodes(self):
        return self.names

    def adjacency_matrix(self):
        if self.is_sparse():
            return self.network.todense()
        else:
            return self.network

    def is_sparse(self):
        return sparse.issparse(self.network)

    def offset_extremes(self):
        if not self.offset:
            self.initialize_offset()

        # (Separately) sort rows and columns of adjacency matrix by
        # increasing sum
        A = np.asarray(self.adjacency_matrix())
        r_ord = np.argsort(A.sum(1))
        c_ord = np.argsort(A.sum(0))
        A = A[r_ord][:,c_ord]

        # Convenience function to set blocks of the offset
        def set_offset_block(r, c, val):
            # XXX: Replace this with working vectorized code
            for i in r_ord[r]:
                for j in c_ord[c]:
                    self.offset[i,j] = val

        # Recursively examine for submatrices that will send
        # corresponding EMLE parameter estimates to infinity
        to_screen = [(np.arange(self.M), np.arange(self.N))]
        while len(to_screen) > 0:
            r_act, c_act = to_screen.pop()

            if len(r_act) == 0 or len(c_act) == 0:
                continue

            A_act = A[r_act][:,c_act]
            n_act = A_act.shape

            # Cumulative sums allow for efficient bad substructure search
            C_inc = np.cumsum(np.cumsum(A_act,1),0)
            def reverse(x):
                return x[range(n_act[0]-1,-1,-1)][:,range(n_act[1]-1,-1,-1)]
            C_dec = reverse(np.cumsum(np.cumsum(reverse(1-A_act),1),0))

            if C_inc[-1,-1] == 0:
                set_offset_block(r_act, c_act, -np.inf)
                continue
            if C_dec[0,0] == 0:
                set_offset_block(r_act, c_act, np.inf)
                continue

            align = np.zeros((n_act[0]+1,n_act[1]+1))
            align[1:(n_act[0]+1)][:,1:(n_act[1]+1)] += (C_inc == 0)
            align[0:n_act[0]][:,0:n_act[1]] *= (C_dec == 0)
            splits = zip(*np.where(align))
            if len(splits) == 0:
                continue
            i_split, j_split = splits[0]

            set_offset_block(r_act[:i_split], c_act[:j_split], -np.inf)
            set_offset_block(r_act[i_split:], c_act[j_split:], np.inf)

            to_screen.append((r_act[i_split:], c_act[:j_split]))
            to_screen.append((r_act[:i_split], c_act[j_split:]))

    def show(self):
        graph = nx.DiGraph()

        for n in self.nodes():
            graph.add_node(n)

        if self.is_sparse():
            nz_i, nz_j = self.network.nonzero()
            for n in range(self.network.nnz):
                graph.add_edge(self.names[nz_i[n]],self.names[nz_j[n]])
        else:
            for i in range(self.N):
                for j in range(self.N):
                    if self.network[i,j]:
                        graph.add_edge(self.names[i], self.names[j])
        
        nx.draw_graphviz(graph)
        plt.show()

    def show_graphviz(self, file = 'graph.pdf', splines = True, labels = True):
        outfile = open('temp_graphviz.dot', 'w')
        outfile.write('digraph G {\n')
        outfile.write('size="12,16";\n')
        outfile.write('orientation=landscape;\n')
        outfile.write('overlap=none;\n')
        outfile.write('repulsiveforce=12;\n')
        if splines:
            outfile.write('splines=true;\n')

        for name in self.names:
            outfile.write('%s [label=""];\n' % name)

        if self.is_sparse():
            nz_i, nz_j = self.network.nonzero()
            for n in range(self.network.nnz):
                outfile.write('%s -> %s;\n' % \
                              (self.names[nz_i[n]], self.names[nz_j[n]]))
        else:
            for i in range(self.N):
                for j in range(self.N):
                    if self.network[i,j]:
                        outfile.write('%s -> %s;\n' % \
                                      (self.names[i], self.names[j]))
                        
        outfile.write('}\n')
        outfile.close()
        system('fdp -Tps2 temp_graphviz.dot -o temp_graphviz.ps')
        unlink('temp_graphviz.dot')
        system('ps2pdf temp_graphviz.ps %s' % file)
        unlink('temp_graphviz.ps')

    def show_heatmap(self, order_by = None):
        if order_by:
            title = 'Adjacency matrix ordered by node covariate\n"%s"' % order_by
            o = np.argsort(self.node_covariates[order_by][:])
        else:
            title, o = 'Unordered adjacency matrix', np.arange(self.N)

        f, (ax_im, ax_ord) = plt.subplots(2, sharex = True)
        f.set_figwidth(3)
        f.set_figheight(6)
        A = self.adjacency_matrix()
        ax_im.imshow(A[o][:,o]).set_cmap('binary')
        ax_im.set_ylim(0, self.N - 1)
        ax_im.set_xticks([])
        ax_im.set_yticks([])
        ax_im.set_title(title)
        #plt.setp([ax_im.get_xticklabels(), ax_im.get_yticklabels()],
        #         visible = False)
        if order_by:
            ax_ord.scatter(np.arange(self.N), self.node_covariates[order_by][o])
            ax_ord.set_xlim(0, self.N - 1)
            ax_ord.set_ylim(self.node_covariates[order_by][o[0]],
                            self.node_covariates[order_by][o[-1]])
        plt.show()

    def show_offset(self, order_by = None):
        if order_by:
            title = 'Offsets ordered by node covariate\n"%s"' % order_by
            o = np.argsort(self.node_covariates[order_by][:])
        else:
            title, o = 'Unordered offsets', np.arange(self.N)

        f = plt.figure()
        ax = f.add_subplot(1, 1, 1)
        O = self.offset.matrix()
        ax.imshow(O[o][:,o])
        ax.set_xlim(0, self.N - 1)
        ax.set_ylim(0, self.N - 1)
        ax.set_title(title)
        plt.setp([ax.get_xticklabels(), ax.get_yticklabels()],
                 visible = False)
        plt.show()

    def show_degree_histograms(self):
        # Messy since otherwise row/column sums can overflow...
        r = np.array(self.network.asfptype().sum(1),dtype=np.int).flatten()
        c = np.array(self.network.asfptype().sum(0),dtype=np.int).flatten()
        
        plt.figure()
        plt.subplot(2,1,1)
        plt.title('out-degree')
        plt.hist(r, bins = max(r))
        plt.subplot(2,1,2)
        plt.title('in-degree')
        plt.hist(c, bins = max(c))
        plt.show()

# Some "tests"
if __name__ == '__main__':
    net = Network()
    net.network_from_file_gexf('data/test.gexf')
    net.new_node_covariate('x_0')
    net.node_covariates['x_0'].from_pairs([str(i) for i in range(10)],
                                          [i**2 for i in range(10)])
    net.new_node_covariate('x_1')
    net.node_covariates['x_1'].data[:] = np.random.normal(2,1,net.N)
    def f_self(n_1, n_2):
        return n_1 == n_2
    net.new_edge_covariate('self_edge').from_binary_function_name(f_self)
    def f_first_half_dir(n_1, n_2):
        return (n_1 < n_2) and (n_2 in ['0','1','2','3','4'])
    net.new_edge_covariate('ec_2').from_binary_function_name(f_first_half_dir)

    print net.node_covariates['x_0']
    print net.node_covariates['x_1']
    print net.edge_covariates['self_edge']
    print net.edge_covariates['ec_2']
    
    print net.adjacency_matrix()
    print net.nodes()
    net.show()

    net_2 = net.subnetwork(np.array([5,0,1,6]))
    print net_2.adjacency_matrix()
    print net_2.node_covariates['x_0']
    print net_2.node_covariates['x_1']
    print net_2.edge_covariates['self_edge']
    print net_2.edge_covariates['ec_2']
    net_2.show()
            
    net_3 = Network(10)
    ord = np.arange(10)
    np.random.shuffle(ord)
    for i in range(10):
        for j in range(i,10):
            net_3.network[ord[i],ord[j]] = True
    net_3.offset_extremes()
    print net_3.offset.matrix()
    print net_3.subnetwork(np.array([2,1,0])).offset.matrix()

    net_4 = Network()
    net_4.network_from_file_gml('data/polblogs/polblogs.gml', ['value'])
    print net_4.node_covariates['value']
