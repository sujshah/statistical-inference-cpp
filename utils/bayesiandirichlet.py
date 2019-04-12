"""
Created on Fri Mar 29 15:58:05 2019

@author: suraj
"""
import numpy as np
from distributions import Gaussian, ZeroTruncatedPoission
from time import sleep

class BayesianDPP:
    """
    Implements the Bayesian approach of density estimation of a mixture of
    Gaussians of fixed size using a data augmentation scheme.
    """
    
    def __init__(self, n_components, n_iterations, jumps, T, delta,
                 burn_in=5000, hyperparameters=None):
        """
        Initialises the tuning parameters of the MCMC algorithm and the 
        non-zero jump observations needed for drawing from the posterior.
        :param n_components: number of components in our mixture.
        :param n_iterations: number of iterations of our MCMC
        :param jumps: the non-zero jump observations of the CPP.
        :param T: the time up to which we observe the CPP.
        :param delta: the separation time between the observations.
        :param burn_in: MCMC burn in.
        :param hyperparameters: hyperparameters for our parameters we want to
                                 obtain inference on.
        """
        
        self.n_components = n_components
        self.active_components = [True for _ in range(self.n_components)]
        self.n_iterations = n_iterations
        self.burn_in = burn_in
        self.acceptance_rate = 0.
        
        self.alpha = np.zeros(self.n_iterations)
        self.betas = np.zeros((self.n_iterations, self.n_components))
        self.mixing_coeffs = np.zeros((self.n_iterations, self.n_components))
        self.means = np.zeros((self.n_iterations, self.n_components))
        self.precision = np.zeros(self.n_iterations)
        
        self.metropolis = None
        
        self.jumps = jumps
        self.n_segments = self.jumps.size
        self.auxiliary = np.ones((self.n_segments, self.n_components))
        self.T = T
        self.delta = delta
        
        if hyperparameters is None:
            hyperparameters = {'mix_shape' : np.ones(self.n_components),
                               'mix_rate' : 1,
                               'precision_shape' : 1,
                               'precision_rate' : 1,
                               'means_loc' : np.zeros(self.n_components),
                               'means_scale' : 1}
        
        self.hyparam = hyperparameters
    
    def performMCMC(self):
        """
        Performs the MCMC algorithm to sample from the posterior.
        """
        
        self.initialise_parameters()
        accept_count = 0
        
        print(f'Performing MCMC with {self.n_iterations} steps.')
        print('Initial parameter values are:')
        print(f'Hyperprior Alpha: {self.alpha[0]}')
        print(f'Mixing Coeffs: {self.mixing_coeffs[0, :]}')
        print(f'Means: {self.means[0, :]}')
        print(f'Precision: {self.precision[0]}')
        sleep(4)
        
        for it in range(1, self.n_iterations):
            accept_count += self.update_segments(it)
            self.update_mixing_coeffs(it)
            self.update_parameters(it)
            self.acceptance_rate = accept_count/it
            
            print(f'Iteration {it}:')
            print(f'Hyperprior Alpha: {self.alpha[it]}')
            print(f'Mixing Coeffs: {self.mixing_coeffs[it, :]}')
            print(f'Means: {self.means[it, :]}')
            print(f'Precision: {self.precision[it]}')
            print(f'Acceptance Rate: {self.acceptance_rate}%')
        
        print('MCMC has completed.')
    
    def compute_stick_breaking_weights(self, betas):
        log_betas = np.log(betas)
        log_betas[1:] = log_betas[1:] + np.cumsum(np.log(1 - betas[:-1]))
        return np.exp(log_betas)

    def initialise_parameters(self):
        """
        Initialises the parameter values using the hyperparameters.
        """
        #self.alpha[0] = np.random.gamma(1, 1)
        self.alpha[0] = 1
        
        self.betas[0] = np.random.beta(1, self.alpha[0], size=self.n_components)
        natural_log_one_minus_beta = np.log(1- self.betas[0])
        cum_log = np.insert(np.cumsum(natural_log_one_minus_beta[:-1]), 0, 0)
        inside_exp = np.dot(self.betas[0], np.exp(cum_log))
        self.metropolis = np.exp(inside_exp)
        
        self.mixing_coeffs[0] = self.compute_stick_breaking_weights(self.betas[0])
        
        self.precision[0] = np.random.gamma(
                self.hyparam['precision_shape'], 
                1.0/self.hyparam['precision_rate'])
        
        self.means[0] = np.random.normal(
                self.hyparam['means_loc'],
                np.sqrt(1.0/(self.precision[0]*self.hyparam['means_scale'])))
    
    def computeQPR(self, segment_sums):
        """
        Computes the P, Q, R matrix/vector/scalar for use in updating the 
        parameters. See Essay for more information.
        :param segment_sums: the jump sums for each segment in the auxiliary
                             variable.
        :return: vector Q, matrix P, scalar R.
        """
        
        Q = ((self.hyparam['means_scale']*
             self.hyparam['means_loc']) +
             np.matmul(self.auxiliary.transpose(), self.jumps/segment_sums))
        
        P = ((self.hyparam['means_scale']*
             np.identity(self.n_components)) +
             np.matmul(self.auxiliary.transpose(),
                       self.auxiliary/segment_sums[:, np.newaxis]))
        
        R = ((self.hyparam['means_scale']*
              np.sum(self.hyparam['means_loc']**2)) + 
             np.sum((self.jumps**2)/segment_sums))
        
        return Q, P, R
    
    def update_mixing_coeffs(self, it):
        component_sums = np.sum(self.auxiliary, axis=0)
        
        proposal_betas = np.empty(self.n_components)
        for i in range(self.n_components):
            a = component_sums[i] + 1
            b = self.alpha[it-1] + np.sum(component_sums[i+1:])
            if b <= 0:
                proposal_betas[i] = 1
            else:
                proposal_betas[i] = np.random.beta(a, b)
        
        natural_log_one_minus_beta = np.log(1- proposal_betas)
        cum_log = np.insert(np.cumsum(natural_log_one_minus_beta[:-1]), 0, 0)
        inside_exp = np.dot(proposal_betas, np.exp(cum_log))
        proposal_top = np.exp(inside_exp)
        
        if np.random.rand() < proposal_top/self.metropolis:
            self.metropolis = proposal_top
            self.betas[it] = proposal_betas
            self.mixing_coeffs[it] = self.compute_stick_breaking_weights(self.betas[it])
            #self.alpha[it] = np.random.gamma(1, 1.0/(1 - np.sum(natural_log_one_minus_beta)))
            self.alpha[it] = 1
        else:
            self.betas[it] = self.betas[it-1]
            self.mixing_coeffs[it] = self.mixing_coeffs[it-1]
            self.alpha[it] = self.alpha[it-1]
        
    
    def update_parameters(self, it):
        """
        Samples the parameter values condiitonal on the auxiliary variable
        using the conjugate prior formulas.
        :param it: the MCMC iteration number.
        """
        
        component_sums = np.sum(self.auxiliary, axis=0)
        segment_sums = np.sum(self.auxiliary, axis=1)  
        Q, P, R = self.computeQPR(segment_sums)
        invP = np.linalg.inv(P)
        
        
        """
        for i in range(self.n_components):
            if not self.active_components[i]:
                self.mixing_coeffs[it, i] = 0.
        """
        
        self.precision[it] = np.random.gamma(
                self.hyparam['precision_shape'] + self.n_segments/2,
                1.0/(self.hyparam['precision_rate'] + 
                     (R - np.dot(Q, np.matmul(invP, Q)))/2.0))
        
        self.means[it] = np.random.multivariate_normal(np.matmul(invP, Q),
                  invP/self.precision[it])

    def update_segments(self, it):
        """
        Samples the auxiliary variable using a Metropolis-Hastings step
        conditional on the updated parameter values.
        :param it: theh MCMC iteration number.
        :return: the average number of proposal acceptances over each segment.
        """
        
        accept_count = 0
        zerotrun_pois = (ZeroTruncatedPoission(
                rate=np.sum(self.mixing_coeffs[it-1])*self.delta)
            .sample(self.n_segments))
        
        for seg in range(self.n_segments):
            prop = zerotrun_pois[seg]
            prop_components = np.random.multinomial(
                prop, 
                self.mixing_coeffs[it-1]/np.sum(self.mixing_coeffs[it-1]))
            
            accept_top = Gaussian(
                    np.dot(prop_components, self.means[it-1]), 
                    prop/self.precision[it-1]).pdf(self.jumps[seg])
            
            accept_bot = Gaussian(
                    np.dot(self.auxiliary[seg], self.means[it-1]),
                    np.sum(self.auxiliary[seg])/self.precision[it-1]).pdf(
                            self.jumps[seg])
            
            if np.random.rand() < accept_top/accept_bot:
                accept_count += 1
                self.auxiliary[seg] = prop_components
        
        return accept_count/self.n_segments
    
    def heuristic_merge(self, it):
        mean_of_means = np.mean(self.means[it-1000:it], axis=0)
        for i in range(len(mean_of_means)-1):
            for j in range(i+1, len(mean_of_means)):
                if np.abs(mean_of_means[i] - mean_of_means[j]) < 0.2:
                    self.active_components[j] = False
                    self.mixing_coeffs[it-1, i] += self.mixing_coeffs[it-1, j]
                    self.mixing_coeffs[it-1, j] = 0
                    self.auxiliary[:, i] += self.auxiliary[:, j]
                    self.auxiliary[:, j] = np.zeros(self.n_segments)
                    
                    
            
            