from __future__ import absolute_import
import numpy
import numpy as np
from numpy import dot
import math
import scipy as sp
from sipy.utilities.fkutil import nextpow2


def ssa(d,nw,p,ssa_flag):
	"""
	SSA: 1D Singular Spectrum Analysis for snr enhancement

	  dp,sing,R = ssa(d,nw,p,ssa_flag);

	  IN   d:   1D time series (column)
	       nw:  view used to make the Hankel matrix
	       p:   number of singular values used to reconstuct the data
	       ssa_flag = 0 do not compute R

	  OUT  dp:  predicted (clean) data
	       R:   matrix consisting of the data predicted with
	            the first eof (R[:,0]), the second eof (R[:,1]) etc
	       sing: singular values of the Hankel matrix

	  Example:
		from math import pi
		import numpy as np
		from numpy import cos
		import matplotlib.pyplot as plt
		from ssa import ssa
		import scipy.io as sio
		
		rand =  sio.loadmat("mtz_ssa/randomnumbers.mat")
		r = rand['r']
		d = (cos(2*pi*0.01*np.linspace(1,200,200)) + 0.5*r[:,0])
		dp, sing, R = ssa(d,100,2,0)

		plt.plot(d/d.max())
		plt.plot(dp/dp.max()+3)
		plt.show()

	  Based on: 

	  M.D.Sacchi, 2009, FX SSA, CSEG Annual Convention, Abstracts,392-395.
	                    http://www.geoconvention.org/2009abstracts/194.pdf

	  Copyright (C) 2008, Signal Analysis and Imaging Group.
	  For more information: http://www-geo.phys.ualberta.ca/saig/SeismicLab
	  Author: M.D.Sacchi
	  Translated to Python by: S. Schneider, 2016



	  This program is free software: you can redistribute it and/or modify
	  it under the terms of the GNU General Public License as published
	  by the Free Software Foundation, either version 3 of the License, or
	  any later version.

	  This program is distributed in the hope that it will be useful,
	  but WITHOUT ANY WARRANTY; without even the implied warranty of
	  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
	  GNU General Public License for more details: http://www.gnu.org/licenses/

	"""



	# Check for Data type of variables.
	if not type(d) == numpy.ndarray:
		print( "Wrong input type of d, must be numpy.ndarray" )
		raise TypeError

	nt = d.size
	N = nt-nw+1
	l = np.arange(0,nw,1)
	R = np.zeros((nt,p))

 	# Make Hankel Matrix.
	M = np.zeros((N-1,N))
	Mp = np.zeros((N-1,N))

	for k in range(N):
		M[:,k] = d[k+l]

 	# Eigenimage decomposition

 	U,S,V = sp.linalg.svd(M)
	


	 # Reconstruct with one oscillatory component at the time.
	if not ssa_flag == 0:
	 	for k in range(p):
			u = np.zeros((N-1,2))
	 		u[:,0] = U[:,k]
	 		Mp = dot( dot(u, u.transpose()), M )
	 		R[:,k] = average_anti_diag(Mp)
	 	dp = sum(d)

	else:
	 	
		for k in range(p):
			u = np.zeros((N-1,2))
			u[:,0] = U[:,k]
			Mp = Mp + dot( dot(u, u.transpose()), M )

		R = None
		dp = average_anti_diag(Mp)
		

	sing = S

	return(dp,sing,R)

def fx_ssa(DATA,dt,p,flow,fhigh):
	"""
	FX_SSA: Singular Spectrum Analysis in the fx domain for snr enhancement
	
	
	 [DATA_f] = fx_ssa(DATA,dt,p,flow,fhigh);
	
	  IN   DATA:      data (traces are columns)
	       dt:     samplimg interval
	       p:      number of singular values used to reconstuct the data
	       flow:   min  freq. in the data in Hz
	       fhigh:  max  freq. in the data in Hz
	
	
	  OUT  DATA_f:  filtered data
	
	  Example:
	
	        d = linear_events;
	        [df] = fx_ssa(d,0.004,4,1,120);
	        wigb([d,df]);
	
	  Based on:
	
	  M.D.Sacchi, 2009, FX SSA, CSEG Annual Convention, Abstracts,392-395.
	                    http://www.geoconvention.org/2009abstracts/194.pdf
	
	  Copyright (C) 2008, Signal Analysis and Imaging Group.
	  For more information: http://www-geo.phys.ualberta.ca/saig/SeismicLab
	  Author: M.D.Sacchi
	  Translated to Python by: S. Schneider 2016
	
	  This program is free software: you can redistribute it and/or modify
	  it under the terms of the GNU General Public License as published
	  by the Free Software Foundation, either version 3 of the License, or
	  any later version.
	
	  This program is distributed in the hope that it will be useful,
	  but WITHOUT ANY WARRANTY; without even the implied warranty of
	  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
	  GNU General Public License for more details: http://www.gnu.org/licenses/
	
	"""
	nt, ntraces = DATA.shape
	nf = 2 * 2 ** nextpow2(nt)
	
	DATA_FX_f = np.zeros((nf, ntraces))
	# First and last samples of the DFT.

	ilow = math.floor(fhigh*dt*nf)+1
	
	if ihigh > math.floor(nf/2)+1:
		ihigh = math.floor(nf/2)+1
	
	DATA_FX = np.fft.fft(DATA,nf,0)
	DATA_FX = np.zeros(DATA_FX.shape)
	
	nw = math.floor(ntraces/2)

	for k in range(ilow,ihigh+1):
		tmp = DATA_FX[k-1,:].conj().transpose()
		
	for j in range(10):
		tmp_out = ssa(tmp,nw,p,0)
		tmp = tmp_out
	
	for k in range(nf/2+2, nf+1):
		DATA_FX_f[k,:] = DATA_FX_f[nf-k+2,:].conj()
		
	DATA_f = np.fft.ifft(DATA_FX_f, axis=0).real
	DATA_f = DATA_f[0:nt,:]
	
	return DATA_f

def average_anti_diag(A):
	"""
	Given a Hankel matrix A,  this program retrieves
	the signal that was used to make the Hankel matrix
	by averaging along the antidiagonals of A.

	M.D.Sacchi
	2008
	SAIG - Physics - UofA
	msacchi@ualberta.ca


	In    A: A hankel matrix

	Out   s: signal (column vector)
	"""

	"""
	MATLAB
	[m,n] = size(A);
	N = m+n-1;

	 s = zeros(N,1);

	 for i = 1 : N

	  a = max(1,i-m+1);
	  b = min(n,i);

	   for k = a : b
	    s(i,1) = s(i,1) + A(i-k+1,k);
	   end

	 s(i,1) = s(i,1)/(b-a+1);

	 end;
 	"""

 	m,n = A.shape

 	N = m+n-1

 	s = np.zeros(N)

 	for i in range(N):
		a = max(1,(i+1)-m+1)
		b = min(n,(i+1))
		
		if a == b:
			k = a
			s[i] = s[i] + A[i-k+1,k-1]
		else:
	 		for k in range(a,b+1):
	 			s[i] = s[i] + A[i-k+1,k-1]

		s[i]= s[i]/(b-a+1)
 		
	return(s)










