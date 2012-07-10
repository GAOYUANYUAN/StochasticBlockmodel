#!/usr/bin/env python

# Algorithms for producing random binary matrices with margin constraints
# Daniel Klein, 5/11/2012

from __future__ import division
import numpy as np

##############################################################################
# Adapting a Matlab routine provided by Jeff Miller
# (jeffrey_miller@brown.edu), which implements an algorithm suggested
# in Manfred Krause's "A Simple Proof of the Gale-Ryser Theorem".
##############################################################################

# Necessary and sufficient check for the existence of a binary matrix
# with the specified row and column margins.
#
# Failure here throws an exception that should stop the calling
# function before anything weird happens.
def check_margins(r, c):
    # Check for conforming input
    assert(np.all(r >= 0))
    assert(np.all(c >= 0))
    assert(r.dtype.kind == 'i')
    assert(c.dtype.kind == 'i')
    assert(np.sum(r) == np.sum(c))

    # Check whether a satisfying matrix exists (Gale-Ryser conditions)
    cc = conjugate(c, len(c))
    cd = c[np.argsort(-c)]
    assert(np.sum(c) == np.sum(cc))
    assert(np.all(np.cumsum(c) <= np.cumsum(cc)))

# Eliminating the column margin nonincreasing condition by sorting and
# then undoing the sorting after the target matrix is generated.
#
# Return an arbitrary binary matrix with specified margins.
# Inputs:
#   r: row margins, length m
#   c: column margins, length n
# Output:
#   (m x n) binary matrix
def arbitrary_from_margins(r, c):
    check_margins(r, c)

    m = len(r)
    n = len(c)

    # Sort column margins and prepare for unsorting
    o = np.argsort(-c)
    oo = np.argsort(o)
    c = c[o]
    c_unsorted = c[oo]
    assert(np.all(np.diff(c) <= 0))

    # Construct the maximal matrix and the conjugate
    A = np.zeros((m,n), dtype = np.bool)
    for i in range(m):
        A[i,0:r[i]] = True
    col = np.sum(A, axis = 0)

    # Convert the maximal matrix into one with column sums c
    # (This procedure is guaranteed to terminate.)
    while not np.all(col == c):
        j = np.where(col > c)[0][0]
        k = np.where(col < c)[0][0]
        i = np.where(A[:,j] > A[:,k])[0][0]
        A[i,j] = False
        A[i,k] = True
        col[j] -= 1
        col[k] += 1

    # Undo the sort
    A = A[:,oo]
 
    # Verify that the procedure found a satisfying matrix
    assert(np.all(r == np.sum(A, axis = 1)))
    assert(np.all(c_unsorted == np.sum(A, axis = 0)))

    return A

##############################################################################
# Adapting Matlab code provided by Matt Harrison (matt_harrison@brown.edu).
##############################################################################

# Find row and column scalings to balance a matrix, using the
# Sinkhorn(-Knopp) algorithm
def canonical_scalings(w):
    tol = 1e-8;

    # Balancing is only meaningful for a nonnegative matrix
    assert(np.all(w >= 0.0))

    m, n = w.shape
    M, N = n * np.ones((m,1)), m * np.ones((1,n))
    r, c = w.sum(1).reshape((m,1)), w.sum(0).reshape((1,n))

    a = M / r
    a /= np.mean(a)
    b = N / (a * w).sum(0)

    tol_check = np.Inf
    while tol_check > tol:
        a_new = M / ((w * b).sum(1).reshape((m,1)))
        a_new /= np.mean(a_new)
        b_new = N / ((a_new * w).sum(0).reshape((1,n)))

        # "L1"-ish tolerance in change during the last iteration
        tol_check = np.sum(np.abs(a - a_new)) + np.sum(np.abs(b - b_new))
        a, b = a_new, b_new

    return a, b

# Suppose c is a sequence of nonnegative integers. Returns c_conj where:
#   c_conj(k) := sum(c > k),    k = 0, ..., (n-1)
def conjugate(c, n):
    cc = np.zeros(n, dtype = np.int);

    for j, k in enumerate(c):
        if k >= n:
            cc[n-1] += 1
        elif k >= 1:
            cc[k-1] += 1

    s = cc[n-1]
    for j in range(n-2,-1,-1):
        s += cc[j]
        cc[j] = s

    return cc

# Return a binary matrix sampled approximately according to the
# specified Bernoulli weights, conditioned on having the specified
# margins.
# Inputs:
#   r: row margins, length m
#   c: column margins, length n
#   w: weight matrix, (m x n) matrix with values in (0, +infty)
# Output:
#   B_sample_sparse: sparse representation of (m x n) binary matrix
#
# More explicitly, consider independent Bernoulli random variables
# B(i,j) arranged as an m x n matrix B given the m-vector of row sums
# r and the n-vector of column sums c of the sample, i.e., given that
# sum(B_sample, 1) = r and sum(B_sample, 0) = c.
#
# An error is generated if no binary matrix agrees with r and c.
#
# B(i,j) is Bernoulli(p(i,j)) where p(i,j) = w(i,j)/(1+w(i,j)), i.e.,
# w(i,j) = p(i,j)/(1-p(i,j)).  [The case p(i,j) = 1 must be handled by
# the user in a preprocessing step, by converting to p(i,j) = 0 and
# decrementing the row and column sums appropriately.]
#
# The sparse representation used for output is a matrix giving the
# locations of the ones in the sample. If d = sum(r) = sum(c), then
# B_sample_sparse has dimensions (d x 2). If something goes wrong (due
# to undetected improper input), some of the rows of B_sample_sparse
# may [-1,-1], indicating no entry of B_sample.
# 
# B_sample can be recovered from B_sample_sparse via:
#
#     B_sample = np.zeros((m,n), dtype=np.bool)
#     for i, j in B_sample_sparse:
#         if i == -1: break 
#         B_sample[i,j] = 1
def approximate_from_margins_weights(r, c, w):
    check_margins(r, c)

    # Make a copy of the margins as they are mutated below...
    r, c = r.copy(), c.copy()

    ### Preprocessing

    # (If re-enabling repeated samples, everything from here until
    # Initialization needs to be done only once across samples.)
    
    # Sizing
    m, n = len(r), len(c)
    assert((m,n) == w.shape)

    # Sort the row margins (descending)
    rndx = np.argsort(-r)
    rsort = r[rndx]

    # Balance the weights
    a_scale, b_scale = canonical_scalings(w)
    wopt = a_scale * w * b_scale

    # Reorder the columns
    cndx = np.lexsort((-c, -wopt.var(0)))
    csort = c[cndx];
    wopt = wopt[:,cndx]

    # Precompute log weights
    logwopt = np.log(wopt)

    # Compute G
    r_max = np.max(r)
    G = np.tile(-np.inf, (r_max+1, m, n-1))
    G[0,:,:] = 0.0
    G[1,:,n-2] = logwopt[:,n-1]
    for i, ri in enumerate(r):
        for j in range(n-2, 0, -1):
            wij = logwopt[i,j]
            for k in range(1, ri+1):
                b = G[k-1,i,j] + wij
                a = G[k,i,j]
                if a == -np.inf and b == -np.inf: continue
                if a > b:
                    G[k,i,j-1] = a + np.logaddexp(1.0, b-a)
                else:
                    G[k,i,j-1] = b + np.logaddexp(1.0, a-b)
        for j in range(n-1):
            for k in range(r_max):
                Gk_num = G[k,i,j]
                Gk_den = G[k+1,i,j]
                if np.isinf(Gk_den):
                    G[k,i,j] = -1.0
                else:
                # Python's 0-based indexing affected the last term
                    G[k,i,j] = wopt[i,j] * np.exp(Gk_num-Gk_den) * \
                        ((n - j - k - 1.0) / (k + 1.0))
            # Tricky idiom: this is Gk_den for k = r_max-1
            if np.isinf(Gk_den):
                G[r_max,i,j] = -1.0

    # Generate the inverse index for the row orders to facilitate fast
    # sorting during the updating
    irndx = np.argsort(rndx)

    # Compute the conjugate of c
    cconj = conjugate(csort, m)

    # Get the running total of number of ones to assign
    count = np.sum(rsort)

    # Get the running total of sum of c squared
    ccount2 = np.sum(csort ** 2)
    # Get the running total of (2 times the) column margins choose 2
    ccount2c = np.sum(csort * (csort - 1))
    # Get the running total of (6 times the) column margins choose 3
    ccount3c = np.sum(csort * (csort - 1) * (csort - 2))

    # Get the running total of sum of r squared
    rcount2 = np.sum(rsort ** 2)
    # Get the running total of (2 times the) column margins choose 2
    rcount2c = np.sum(rsort * (rsort - 1))
    # Get the running total of (6 times the) column margins choose 3
    rcount3c = np.sum(rsort * (rsort - 1) * (rsort - 2))

    # Initialize B_sample_sparse
    B_sample_sparse = -np.ones((count,2), dtype=np.int)
    
    # Initialize intermediate storage
    #
    # Index 0 corresponds to -1, index 1 corresponds to 0, index 2
    # corresponds to 1, ..., index M-1 corresponds to c[0]+1
    M = csort[0] + 3
    S = np.zeros((M,n))
    SS = np.zeros(M)

    # Used to prevent divide by zero
    eps0 = np.spacing(0)

    ### Initialization

    # Most recent assigned column in B_sample_sparse
    place = -1

    # Loop over columns for column-wise sampling
    #
    # Warning: things that "should" be fixed are modified in this
    # loop, e.g., n, the number of columns!
    for c1 in range(n):
        ### Sample the next column

        # Remember the starting point for this column in B_sample_sparse
        placestart = place + 1

        # Inspect column
        label, colval = cndx[c1], csort[c1]
        if colval == 0 or count == 0: break

        # Update the conjugate
        cconj[0:colval] -= 1

        # Update the number of columns remaining
        n -= 1

        ### DP initialization

        # Variables used inside DP
        smin, smax = colval, colval
        cumsums, cumconj = count, count - colval

        # Update the count and the running column counts
        count -= colval
        ccount2 -= colval ** 2
        ccount2c -= colval * (colval - 1)
        ccount3c -= colval * (colval - 1) * (colval - 2)

        # Start filling SS (indices corresponding to colval-1, colval, colval+1)
        SS[colval:(colval+3)] = [0,1,0]

        # Get the constants for computing the probabilities
        if count == 0 or m*n == count:
            weightA = 0
        else:
            wA = 1.0 * m * n / (count * (m * n - count))
            weightA = wA * (1 - wA * (ccount2 - count**2 / n)) / 2

        ### DP

        # Loop over (remaining and sorted descending) rows in reverse
        for i in reversed(range(m)):
            # Get the value for this row, for use in computing the
            # probability of a 1 for this row/column pair
            rlabel = rndx[i]
            val = r[rlabel]

            # Use the Canfield, Greenhill, and McKay (2008)
            # approximation to N(r,c)
            #
            # Question: versus (3.12a) in Harrison (2009), why is n
            # replaced with n+1?
            p1 = val * np.exp(weightA * (1.0 - 2.0 * (val - count / m)))
            p = p1 / (n + 1.0 - val + p1)
            q = 1.0 - p

            # Incorporate weights
            if n > 0 and val > 0:
                Gk = G[val-1,rlabel,c1]
                if Gk < 0:
                    q = 0
                else:
                    p *= Gk

            # Update the feasibility constraints
            cumsums -= val
            cumconj -= cconj[i]

            # Incorporate the feasibility constraints into bounds on
            # the running column sum
            sminold, smaxold = smin, smax
            smin = max(0, max(cumsums - cumconj, sminold - 1))
            smax = min(smaxold, i)

            # DP iteration (only needed parts of SS updated)
            SSS = 0.0
            SS[smin] = 0.0
            for j in range(smin+1,smax+2):
                a = SS[j] * q
                b = SS[j+1] * p
                apb = a + b
                SSS += apb
                SS[j] = apb
                S[j,i] = b / (apb + eps0)
            SS[smax+2] = 0.0

            # Check for impossible; if so, jump out of inner loop
            if SSS <= 0: break

            # Normalize to prevent overflow/underflow
            SS[(smin+1):(smax+2)] /= SSS

        # Check for impossible; if so, jump out of outer loop
        if SSS <= 0: break

        ### Sampling

        # Running total and target of how many entries filled (offset
        # to match S)
        j, jmax = 1, colval + 1

        # Skip assigning anything when colval = 0
        if j < jmax:
            for i in range(m):
                # Generate a one according to the transition probability
                p = S[j,i]
                if np.random.random() < p:
                    # Decrement row total
                    rlabel = rndx[i]
                    val = r[rlabel]
                    r[rlabel] -= 1

                    # Update the running row counts
                    rcount2 -= 2 * val - 1
                    rcount2c -= 2 * val - 2
                    rcount3c -= 3 * (val - 1) * (val - 2)

                    # Record the entry
                    place += 1
                    B_sample_sparse[place,:] = [rlabel,label]
                    j += 1

                    # Break the loop early, since all the remaining
                    # p's must be 0
                    if j == jmax: break

        # Everything is updated except the re-sorting, so skip if possible
        if count == 0: break

        ### Re-sort row sums

        # Essentially, we only need to re-sort the assigned rows. In
        # greater detail, we take each row that was assigned to the
        # list and either leave it in place or swap it with the last
        # row that matches its value; this leaves the rows sorted
        # (descending) since each row was decremented by only 1.

        # Looping in reverse ensures that least rows are swapped first
        for j in range(place, placestart-1, -1):
            # Get the row label, its new value, and its inverse index
            k = B_sample_sparse[j,0]
            val = r[k]
            irndxk = irndx[k]

            # See if the list is still sorted
            irndxk1 = irndxk + 1
            if irndxk1 >= m or r[rndx[irndxk1]] <= val:
                continue

            # Find the first place where k can be inserted
            irndxk1 += 1
            while irndxk1 < m and r[rndx[irndxk1]] > val:
                irndxk1 += 1
            irndxk1 -= 1

            # Perform swap
            rndxk1 = rndx[irndxk1]
            rndx[irndxk] = rndxk1
            rndx[irndxk1] = k
            irndx[k] = irndxk1
            irndx[rndxk1] = irndxk

        ### Recursion

        # At this point:
        #   r[rndx] is sorted and represents unassigned row margins
        #   rndx[irndx] = 0:m
        #   c[cndx[(c1+1):]] is sorted and represents unassigned column margins
        #   m, n, count, ccount*, rcount*, cconj, etc. are valid
        #   place points to new entries in B_sample_sparse
        #
        # In other words, it is as if Initialization had just
        # completed for sampling a submatrix of B_sample.

    return B_sample_sparse

##############################################################################
# End of adapted code
##############################################################################


if __name__ == '__main__':
    # Test of binary matrix generation code
    m = np.random.random(size=(12,10)) < 0.3
    r, c = np.sum(m, axis = 1), np.sum(m, axis = 0)
    print r, c
    A = arbitrary_from_margins(r, c)
    print np.sum(A, axis = 1), np.sum(A, axis = 0)

    # Test of Sinkhorn balancing
    m = np.random.normal(10, 1, size = (6,5))
    a, b = canonical_scalings(m)
    m_canonical = a * m * b
    print m_canonical.sum(1)
    print m_canonical.sum(0)

    # Test of conjugate
    print conjugate([1,1,1,1,2,8], 10)

    # Test of approximate margins-conditional sampling
    N = 50;
    a_out = np.random.normal(0, 1, N)
    a_in = np.random.normal(0, 1, N)
    x = np.random.normal(0, 1, (N,N))
    theta = 0.8
    log_w = np.zeros((N,N))
    for i, a in enumerate(a_out):
        log_w[i,:] += a
    for j, a in enumerate(a_out):
        log_w[:,j] += a
    log_w += theta * x
    r, c = np.repeat(5, N), np.repeat(5, N)
    B_sample_sparse = approximate_from_margins_weights(r, c, np.exp(log_w))
    B_sample = np.zeros((N,N), dtype=np.bool)
    for i, j in B_sample_sparse:
        if i == -1: break
        B_sample[i,j] = 1
    print B_sample.sum(1)
    print B_sample.sum(0)
    print B_sample[x < -1.0].sum(), B_sample[x > 1.0].sum()