#!/usr/bin/env python

import numpy as np

from BinaryMatrix import approximate_conditional_nll as acnll
from BinaryMatrix import approximate_from_margins_weights as sample

from Experiment import Seed

# Parameters
params = { 'M': 20,
           'N': 10,
           'theta': 2.0,
           'kappa': -1.628,
           'alpha_min': -0.4,
           'beta_min': -0.86,
           'alpha_level': 0.05,
           'n_MC_levels': [10, 50, 100, 500],
           'n_rep': 10,
           'L': 601,
           'theta_l_min': -6.0,
           'theta_l_max': 6.0,
           'do_prune': True,
           'random_seed': 137 }

def generate_data(params, seed):
    M, N = params['M'], params['N']
    
    # Advance random seed for data generation
    seed.next()

    # Generate covariate
    v = np.random.normal(0, 1.0, (M,N))

    # Generate Bernoulli probabilities from logistic regression model
    logit_P = np.zeros((M,N))
    for i in range(1,M):
        logit_P[i,:] += np.random.uniform(params['alpha_min'],
                                          params['alpha_min'] + 1)
    for j in range(1,N):
        logit_P[:,j] += np.random.uniform(params['beta_min'],
                                          params['beta_min'] + 1)
    logit_P += params['kappa']
    logit_P += params['theta'] * v
    P = 1.0 / (1.0 + np.exp(-logit_P))

    # Generate data for this trial
    X = np.random.random((M,N)) < P

    # Pruning rows and columns of 0's and 1's; this may improve
    # the quality of the approximation for certain versions of the
    # sampler
    if params['do_prune']:
        r, c = X.sum(1), X.sum(0)
        r_p = (r == 0) + (r == N)
        c_p = (c == 0) + (c == M)
        X = X[-r_p][:,-c_p].copy()
        v = v[-r_p][:,-c_p].copy()

    return X, v

def confidence_interval(X, v, K, theta_grid, alpha_level):
    M_p, N_p = X.shape
    L = len(theta_grid)
    theta_l_min, theta_l_max = min(theta_grid), max(theta_grid)
    
    # Observed statistic
    t_X = np.sum(X * v)

    # Row and column margins; the part of the data we can use to design Q
    r, c = X.sum(1), X.sum(0)

    # Generate samples from the mixture proposal distribution
    Y = []
    for k in range(K):
        l_k = np.random.randint(L)
        theta_k = theta_grid[l_k]
        print '%.2f' % theta_k
        logit_P_l = theta_k * v

        Y_sparse = sample(r, c, np.exp(logit_P_l))
        Y_dense = np.zeros((M_p,N_p), dtype = np.bool)
        for i, j in Y_sparse:
            if i == -1: break
            Y_dense[i,j] = 1
        Y.append(Y_dense)

    # Statistics for the samples from the proposal distribution only
    # need to be calculated once...
    t_Y = np.empty(K)
    for k in range(K):
        t_Y[k] = np.sum(Y[k] * v)
    I_t_Y_plus = t_Y >= t_X
    I_t_Y_minus = -t_Y >= -t_X

    # Probabilities under each component of the proposal distribution
    # only need to be calculated once...
    log_Q_X = np.empty(L)
    log_Q_Y = np.empty((L,K))
    for l in range(L):
        theta_l = theta_grid[l]

        logit_P_l = theta_l * v
        log_Q_X[l] = -acnll(X, np.exp(logit_P_l))
        for k in range(K):
            log_Q_Y[l,k] = -acnll(Y[k], np.exp(logit_P_l))
        print '%.2f: %.2g' % (theta_l, np.exp(log_Q_Y[l].max()))
    log_Q_sum_X = np.logaddexp.reduce(log_Q_X)
    log_Q_sum_Y = np.empty(K)
    for k in range(K):
        log_Q_sum_Y[k] = np.logaddexp.reduce(log_Q_Y[:,k])

    # Step over the grid, calculating approximate p-values
    p_plus = np.empty(L)
    p_minus = np.empty(L)
    for l in range(L):
        theta_l = theta_grid[l]

        p_num_plus, p_num_minus, p_denom = 0.0, 0.0, 0.0

        # X contribution
        log_w_X = (theta_l * t_X) - log_Q_sum_X
        w_X_l = np.exp(log_w_X)

        p_num_plus += w_X_l
        p_num_minus += w_X_l
        p_denom += w_X_l

        # Y contribution
        w_Y_l = np.empty(K)
        for k in range(K):
            log_w_Y = (theta_l * t_Y[k]) - log_Q_sum_Y[k]
            w_Y = np.exp(log_w_Y)
            w_Y_l[k] = w_Y

            if I_t_Y_plus[k]: p_num_plus += w_Y
            if I_t_Y_minus[k]: p_num_minus += w_Y
            p_denom += w_Y

        print '%.2f: %.2g (%.2g, %.2g)' % \
          (theta_l, w_X_l, w_Y_l.min(), w_Y_l.max())

        p_plus[l] = p_num_plus / p_denom
        p_minus[l] = p_num_minus / p_denom

    p_plus_minus = np.fmin(1, 2 * np.fmin(p_plus, p_minus))

    C_alpha = theta_grid[p_plus_minus > alpha_level]
    C_alpha_l, C_alpha_u = np.min(C_alpha), np.max(C_alpha)
    if C_alpha_l == theta_l_min:
        C_alpha_l = -np.inf
    if C_alpha_u == theta_l_max:
        C_alpha_u = np.inf

    return C_alpha_l, C_alpha_u

def do_experiment(params):
    seed = Seed(params['random_seed'])

    L = params['L']
    K = params['n_MC_levels'][0]
    R = params['n_rep']

    # Generate theta grid for inference
    theta_grid = np.linspace(params['theta_l_min'], params['theta_l_max'], L)

    # Do experiment
    in_interval = np.empty(R)
    length = np.empty(R)
    for trial in range(R):
        X, v = generate_data(params, seed)

        ci_l, ci_u = confidence_interval(X, v, K, theta_grid,
                                         params['alpha_level'])
        
        print '[%.2f, %.2f]' % (ci_l, ci_u)

        in_interval[trial] = ci_l <= params['theta'] <= ci_u
        length[trial] = ci_u - ci_l

    # For verifying that same data was generated even if different
    # algorithms consumed a different amount of randomness
    seed.final()

    return in_interval, length

in_interval, length = do_experiment(params)
print 'Coverage probability: %.2f' % np.mean(in_interval)
print 'Median length: %.2f' % np.median(length)
