# -*- coding: utf-8 -*-
"""
Created on Mon Apr 15 09:24:19 2019

@author: suraj
"""
import matplotlib.pyplot as plt
from utils.bayesianmixture import BayesianMoG
from utils.simulation import CPPSimulation
from utils.distributions import Gaussian, MixtureOfDistribution
plt.rcParams['font.size'] = 12

#example 1
mog =  MixtureOfDistribution(Gaussian, [0.3, 0.7], [-2, 1], [1, 1])
jumps = CPPSimulation(1, mog).observe_jumps(1, T=8000)
bayesmix = BayesianMoG(2, 15000, jumps, T=8000, 1)
bayesmix.performMCMC()
params = bayesmix.calculate_posterior()
density = MixtureOfDistribution(
        Gaussian, params['mixing_coeffs'], params['means'], 
        np.repeat(params['precision'], 2))


plt.plot(np.arange(15000), bayesmix.means)
plt.plot(np.arange(15000), bayesmix.mixing_coeffs)
plt.plot(np.arange(15000), bayesmix.precision)

#graphs
params = {'legend.fontsize': 20,
          'legend.handlelength': 2}
plt.rcParams.update(params)
x = np.arange(-5, 5, 0.01)
plt.plot(x, density.pdf(x))
plt.xlim(-5, 5)
plt.ylim(0, 0.5)
plt.plot(x, mog.pdf(x))
plt.legend(['Estimate', 'True'])
plt.show()