#!/usr/bin/env python

# Application of network inference to C. elegans connectome
# Daniel Klein, 4/10/2013

import numpy as np
import matplotlib.pyplot as plt
import networkx as nx
import xlrd

from Network import network_from_edges
from Models import Stationary, StationaryLogistic, NonstationaryLogistic
from Models import FixedMargins, alpha_zero

# Parameters
params = { 'use_gap': False,
           'use_chemical': True,
           'cov_soma': True,
           'cov_lineage': False,
           'cov_class': False,
           'file_network': 'data/c_elegans_chen/NeuronConnect.xls',
           'file_neurons': 'data/c_elegans_chen/NeuronType.xls',
           'file_landmarks': 'data/c_elegans_chen/NeuronFixedPoints.xls',
           'file_lineage_1': 'data/c_elegans_chen/NeuronLineage_Part1.xls',
           'file_lineage_2': 'data/c_elegans_chen/NeuronLineage_Part2.xls' }

# Import network connectivity from file
edges = []
nodes = set()
wb_network = xlrd.open_workbook(params['file_network'])
ws_network = wb_network.sheet_by_name('NeuronConnect.csv')
for r in range(1, ws_network.nrows):
    n_1 = ws_network.cell_value(r, 0)
    n_2 = ws_network.cell_value(r, 1)
    t = ws_network.cell_value(r, 2)[0]
    if n_1 == 'NMJ' or n_2 == 'NMJ': continue
    if params['use_gap'] and t == 'E':
        edges.append((n_1, n_2))
        edges.append((n_2, n_1))
        nodes.add(n_1)
        nodes.add(n_2)
    if params['use_chemical'] and t == 'S':
        edges.append((n_1, n_2))
        nodes.add(n_1)
        nodes.add(n_2)
print '# Nodes: %d' % len(nodes)

# Initialize network from connectivity data
net = network_from_edges(edges)
A = np.array(net.adjacency_matrix())
r = A.sum(1)
c = A.sum(0)
print '# Edges: %d' % net.array.sum()
cov_names = []

# Import soma position from file
soma_pos = {}
wb_neurons = xlrd.open_workbook(params['file_neurons'])
ws_neurons = wb_neurons.sheet_by_name('NeuronType.csv')
for r in range(1, ws_neurons.nrows):
    n = ws_neurons.cell_value(r, 0)
    pos = ws_neurons.cell_value(r, 1)
    soma_pos[n] = pos
cov = net.new_node_covariate('soma_pos')
cov.from_pairs(soma_pos.keys(), soma_pos.values())
if params['cov_soma']:
    cov_names.append('soma_dist')
cov = net.new_edge_covariate('soma_dist')
def f_soma_pos_dist(n_1, n_2):
    return abs(soma_pos[n_1] - soma_pos[n_2])
cov.from_binary_function_name(f_soma_pos_dist)

# Import landmark type (hence sensory, motor, inter-) from file
neuron_class = {}
wb_landmarks = xlrd.open_workbook(params['file_landmarks'])
ws_landmarks = wb_landmarks.sheet_by_name('NeuronFixedPoints.csv')
for r in range(1, ws_landmarks.nrows):
    n = ws_landmarks.cell_value(r, 0)
    t = ws_landmarks.cell_value(r, 1)[0]
    neuron_class[n] = t
for n in net.names:
    if not n in neuron_class:
        neuron_class[n] = 'I'
for class_1 in ['S', 'I', 'M']:
    for class_2 in ['S', 'I', 'M']:
        if class_1 == 'I' and class_2 == 'I': continue
        cov_name = '%s_%s' % (class_1, class_2)
        if params['cov_class']:
            cov_names.append(cov_name)
        cov = net.new_edge_covariate(cov_name)
        def f_same_class(n_1, n_2):
            return ((neuron_class[n_1] == class_1) and
                    (neuron_class[n_2] == class_2))
        cov.from_binary_function_name(f_same_class)

# Import lineage distance from files
dist = {}
wb_lineage_1 = xlrd.open_workbook(params['file_lineage_1'])
ws_lineage_1 = wb_lineage_1.sheet_by_name('NeuronLineage_Part1.csv')
for r in range(1, ws_lineage_1.nrows):
    n_1 = ws_lineage_1.cell_value(r, 0)
    n_2 = ws_lineage_1.cell_value(r, 1)
    d = ws_lineage_1.cell_value(r, 2)
    dist[(n_1,n_2)] = d
    dist[(n_2,n_1)] = d
wb_lineage_2 = xlrd.open_workbook(params['file_lineage_2'])
ws_lineage_2 = wb_lineage_2.sheet_by_name('NeuronLineage_Part2.csv')
for r in range(1, ws_lineage_1.nrows):
    n_1 = ws_lineage_2.cell_value(r, 0)
    n_2 = ws_lineage_2.cell_value(r, 1)
    d = ws_lineage_2.cell_value(r, 2)
    dist[(n_1,n_2)] = d
    dist[(n_2,n_1)] = d
if params['cov_lineage']:
    cov_names.append('lineage_dist')
cov = net.new_edge_covariate('lineage_dist')
def f_lineage_dist(n_1, n_2):
    if n_1 == n_2: return 0
    return dist[(n_1, n_2)]
cov.from_binary_function_name(f_lineage_dist)

# Display observed network
o = np.argsort(net.node_covariates['soma_pos'][:])
A = np.asarray(net.adjacency_matrix())
def heatmap(data, cmap = 'binary'):
    plt.imshow(data[o][:,o]).set_cmap(cmap)
def residuals(data_mean, data_sd):
    r = np.abs((data_mean - A) / data_sd)
    plt.imshow(r[o][:,o], vmin = 0, vmax = 3.0).set_cmap('binary')
plt.figure()
plt.subplot(331)
plt.title('Observed')
heatmap(A)
plt.subplot(332)
plt.title('Network')
graph = nx.DiGraph()
for n1, n2 in edges:
    graph.add_edge(n1, n2)
pos = nx.graphviz_layout(graph, prog = 'neato')
nx.draw(graph, pos, node_size = 10, with_labels = False)

# Store sampled typical networks from fit models
n_samples = 100
s_samples = np.empty((n_samples, net.N, net.N))
ns_samples = np.empty((n_samples, net.N, net.N))
c_samples = np.empty((n_samples, net.N, net.N))

print 'Fitting stationary model'
s_model = StationaryLogistic()
for cov_name in cov_names:
    s_model.beta[cov_name] = None
s_model.fit(net)
print 'NLL: %.2f' % s_model.nll(net)
print 'kappa: %.2f' % s_model.kappa
for cov_name in cov_names:
    print '%s: %.2f' % (cov_name, s_model.beta[cov_name])
print
for rep in range(n_samples):
    s_samples[rep,:,:] = s_model.generate(net)
s_model.confidence(net)
print 'Pivotal:'
for cov_name in cov_names:
    ci = s_model.conf[cov_name]['pivotal']
    print ' %s: (%.2f, %.2f)' % (cov_name, ci[0], ci[1])
print

print 'Fitting nonstationary model'
alpha_zero(net)
ns_model = NonstationaryLogistic()
for cov_name in cov_names:
    ns_model.beta[cov_name] = None
ns_model.fit(net)
print 'NLL: %.2f' % ns_model.nll(net)
print 'kappa: %.2f' % ns_model.kappa
for cov_name in cov_names:
    print '%s: %.2f' % (cov_name, ns_model.beta[cov_name])
print
for rep in range(n_samples):
    ns_samples[rep,:,:] = ns_model.generate(net)
ns_model.confidence(net)
print 'Pivotal:'
for cov_name in cov_names:
    ci = ns_model.conf[cov_name]['pivotal']
    print ' %s: (%.2f, %.2f)' % (cov_name, ci[0], ci[1])
print

print 'Fitting conditional model'
c_model = StationaryLogistic()
c_model.fit = c_model.fit_conditional
c_model.generate = c_model.generate_margins
for cov_name in cov_names:
    c_model.beta[cov_name] = None
c_model.fit_conditional(net, verbose = True)
print 'NLL: %.2f' % c_model.nll(net)
print 'kappa: %.2f' % c_model.kappa
for cov_name in cov_names:
    print '%s: %.2f' % (cov_name, c_model.beta[cov_name])
print
for rep in range(n_samples):
    c_samples[rep,:,:] = c_model.generate(net)
c_model.confidence(net)
print 'Pivotal:'
for cov_name in cov_names:
    ci = c_model.conf[cov_name]['pivotal']
    print ' %s: (%.2f, %.2f)' % (cov_name, ci[0], ci[1])
#print 'Harrison:'
#for cov_name in cov_names:
#    c_model.confidence_harrison(net, cov_name)
#    ci = c_model.conf[cov_name]['harrison']
#    print ' %s: (%.2f, %.2f)' % (cov_name, ci[0], ci[1])
#print

# Calculate sample means and variances
s_samples_mean = np.mean(s_samples, axis = 0)
s_samples_sd = np.sqrt(np.var(s_samples, axis = 0))
ns_samples_mean = np.mean(ns_samples, axis = 0)
ns_samples_sd = np.sqrt(np.var(ns_samples, axis = 0))
c_samples_mean = np.mean(c_samples, axis = 0)
c_samples_sd = np.sqrt(np.var(c_samples, axis = 0))

# Finish plotting
plt.subplot(334)
plt.title('Stationary')
heatmap(s_samples_mean)
plt.subplot(337)
residuals(s_samples_mean, s_samples_sd)
plt.subplot(335)
plt.title('Nonstationary')
heatmap(ns_samples_mean)
plt.subplot(338)
residuals(ns_samples_mean, ns_samples_sd)
plt.subplot(336)
plt.title('Conditional')
heatmap(c_samples_mean)
plt.subplot(339)
residuals(c_samples_mean, c_samples_sd)
plt.show()
