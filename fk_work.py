"""
perform 2d fft
ordne k richtig zu, Formel finden!
Synthetics mit sinus wavelet und multiplen dessen
damit erstmal testen
"""



import obspy
from obspy import read
import numpy as np
import matplotlib.pyplot as plt
import Muenster_Array_Seismology as MAS
from Muenster_Array_Seismology import get_coords
from obspy.core.util.geodetics import gps2DistAzimuth


def create_signal(no_of_traces=10, len_of_traces=30000,
                  multiple=False, multipdist=2):
  """
  function that creates a 
  """
  dist=multipdist
  if multiple:
      data = np.array([np.zeros(len_of_traces)])
      data[0][0] = 1
      data[0][dist] = 1
  else:
      data = np.array([np.zeros(len_of_traces)])
      data[0][0] = 1
  
  for i in range(no_of_traces)[1:]:
      new_trace = np.array([np.zeros(len_of_traces)])
      if multiple and i < len_of_traces-dist:
          new_trace[0][i] = 1
          new_trace[0][i+dist] = 1
      else:
          new_trace[0][i] = 1
      data = np.append(data, new_trace, axis=0)
  data = np.flipud(data)
  return(data)
  
def fk_filter(stream, inventory, catalog, phase):
	"""
	Import stream, inventory, catalog and phase you want to investigate.
	The function bins the data, applies an 2D FFT, removes a certain window around the
	desired phase to surpress mutliples and applies an 2d iFFT

	param stream: with ending like MSEED
	type stream: string

	param inventory: with ending xml
	type inventory: string

	param catalog: with ending xml
	type catalog: string

	param phase: name of the phase to be investigated
	type phase: string
	"""

	"""
	Read data ######################################################################
	"""
	st = obspy.read(stream)
	inv = obspy.read_inventory(inventory)
	cat = obspy.readEvents(catalog)

	#pushing the trace data in an array
	ArrayData = np.array([st[0].data])
	
	for i in range(len(st))[1:]:
	  next_st = np.array([st[i].data])
	  ArrayData = np.append(ArrayData, next_st, axis=0)
	
	"""
	Binning of the data ############################################################
	"""
	
	#calc min and max epidist between source and receivers
	Array_Coords = get_coords(inv)
	
	stat1 = st[i].meta.station
	stat2 = st[i+1].meta.station
	lat1 = Array_Coords[""][""]
	lon1 = Array_Coords[""][""]
	
	lat2 = Array_Coords[""][""]
	lon2 = Array_Coords[""][""]
	
	epi_dist = gps2DistAzumiuth( lat1, lon1, lat2, lon2 )
	
	#create equidistant (delta x) x-mesh with ->  N artificial receiver / ghost receiver

	#assign stations to ghost receiver

	#calc local slowness of the phase and align all the traces assigned to the respective ghost with that slowness

	#beamform them

	#return N binned traces with equidistant delta x 


	"""
	Correction of global(array) slowness of phase ##################################
	"""

	#align all binned traces with the slowness of the imported phase

	"""
	2D FFT #########################################################################
	"""
	#apply 2D FFT

	#np.fft.fft2(a, s=None, axes=(-2, -1))
	"""
	Parameters
	----------
	a : array_like
	Input array, can be complex
	s : sequence of ints, optional
	Shape (length of each transformed axis) of the output
	(`s[0]` refers to axis 0, `s[1]` to axis 1, etc.).
	This corresponds to `n` for `fft(x, n)`.
	Along each axis, if the given shape is smaller than that of the input,
	the input is cropped.  If it is larger, the input is padded with zeros.
	if `s` is not given, the shape of the input along the axes specified
	by `axes` is used.
	axes : sequence of ints, optional
	Axes over which to compute the FFT.  If not given, the last two
	axes are used.  A repeated index in `axes` means the transform over
	that axis is performed multiple times.  A one-element sequence means
	that a one-dimensional FFT is performed.

	Returns
	-------
	out : complex ndarray
	The truncated or zero-padded input, transformed along the axes
	indicated by `axes`, or the last two axes if `axes` is not given.
	"""

	#mute area around |f| > eps, choose eps dependent on your phase/data/i dont know yet

	#apply 2D iFFT

	"""
	Undo global-correction of the phase ############################################
	""" 

	"""
	return stream with filtered and binned data ####################################
	"""

stream="2011-03-11T05:46:23.MSEED"
inventory="2011-03-11T05:46:23.MSEED_inv.xml"
catalog="2011-03-11T05:46:23.MSEED_cat.xml"
phase="PP"

#fk_filter(stream, inventory, catalog, phase)
data=create_signal(len_of_traces=12,multiple=True)
