from __future__ import absolute_import

import os
import ctypes as C

import numpy
import numpy as np
import math
import fractions
import scipy as sp
from scipy.integrate import cumtrapz
import warnings
import datetime
import obspy

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from mpl_toolkits.basemap import Basemap
from matplotlib.ticker import MaxNLocator

from obspy import UTCDateTime, Stream, Inventory
from obspy.core.event.event import Event
from obspy.core.inventory.network import Network
from obspy.core import AttribDict
from obspy.geodetics.base import locations2degrees, gps2dist_azimuth, \
   kilometer2degrees
from obspy.taup import TauPyModel
from obspy.taup import getTravelTimes
from obspy.taup.taup_geo import add_geo_to_arrivals

from sipy.util.base import nextpow2

"""
Collection of useful functions for processing seismological array data

Author: S. Schneider 2016
"""

def __coordinate_values(inventory):
    geo = get_coords(inventory, returntype="dict")
    lats, lngs, hgt = [], [], []
    for coordinates in list(geo.values()):
        lats.append(coordinates["latitude"]),
        lngs.append(coordinates["longitude"]),
        hgt.append(coordinates["elevation"])
    return lats, lngs, hgt

def get_coords(inventory, returntype="dict"):
	"""
	Get the coordinates of the stations in the inventory, independently of the channels,
	better use for arrays, than the channel-dependent core.inventory.inventory.Inventory.get_coordinates() .
	returns the variable coords with entries: elevation (in km), latitude and longitude.
	:param inventory: Inventory to get the coordinates from
	:type inventory: obspy.core.inventory.inventory.Inventory

	:param coords: dictionary with stations of the inventory and its elevation (in km), latitude and longitude
	:type coords: dict

	:param return: type of desired return
	:type return: dictionary or numpy.array

	"""
	if isinstance(inventory, Inventory):
		if returntype == "dict":
			coords = {}
			for network in inventory:
				for station in network:
					coords["%s.%s" % (network.code, station.code)] = \
						{"latitude": station.latitude,
						 "longitude": station.longitude,
						 "elevation": float(station.elevation) / 1000.0,
						 "epidist" : None}

		if returntype == "array":
			nstats = len(inventory[0].stations)
			coords = np.empty((nstats, 3))
			if len(inventory.networks) == 1:
				i=0
				for network in inventory:
					for station in network:
						coords[i,0] = station.latitude
						coords[i,1] = station.longitude
						coords[i,2] = float(station.elevation) / 1000.0
						i += 1

	elif isinstance(inventory, Network):
		if returntype == "dict":
			coords = {}
			for station in inventory:
				coords["%s.%s" % (inventory.code, station.code)] = \
					{"latitude": station.latitude,
					 "longitude": station.longitude,
					 "elevation": float(station.elevation) / 1000.0,
					 "epidist" : None}

		if returntype == "array":
			nstats = len(inventory[0].stations)
			coords = np.empty((nstats, 3))
			if len(inventory) == 1:
				i=0
				for station in inventory:
					coords[i,0] = station.latitude
					coords[i,1] = station.longitude
					coords[i,2] = float(station.elevation) / 1000.0
					i += 1		

	return coords

def stream2array(stream, normalize=False):
	sx = stream.copy()
	x = np.zeros((len(sx), len(sx[0].data)))
	for i, traces in enumerate(sx):
		for j, data in enumerate(traces):
			x[i,j]=data

	if normalize:
		x = x / x.max()

	return(x)

def array2stream(ArrayData, st_original=None, network=None):
	"""
	param network: Network, of with all the station information
	type network: obspy.core.inventory.network.Network
	"""
	st_tmp = st_original.copy()
	traces = []
	
	for i, trace in enumerate(ArrayData):
		newtrace = obspy.core.trace.Trace(trace)
		traces.append(newtrace)
		
	stream = Stream(traces)
	
	# Just writes the network information, if possible input original stream
	
	if isinstance(st_tmp, Stream):
		
		# Checks length of ArrayData and st_original, if needed,
		# corrects trace.stats.npts value of new generated Stream-object.
		if ArrayData.shape[1] == len(st_tmp[0]):

			for i, trace in enumerate(stream):
				trace.stats = st_tmp[i].stats

		else:

			for i, trace in enumerate(stream):
				trace.stats = st_tmp[i].stats
				trace.stats.npts = ArrayData.shape[1]
			

	elif isinstance(network, Network) and not isinstance(st_tmp, Stream):

		for trace in stream:
			trace.meta.network = network.code
			trace.meta.station = network[0].code


	return(stream)


def attach_network_to_traces(stream, network):
	"""
	Attaches the network-code of the inventory to each trace of the stream
	"""
	for trace in stream:
		trace.meta.network = network.code

def attach_coordinates_to_traces(stream, inventory, event=None):
	"""
	Function to add coordinates to traces.

	It extracts coordinates from a :class:`obspy.station.inventory.Inventory`
	object and writes them to each trace's stats attribute. If an event is
	given, the distance in degree will also be attached.

	:param stream: Waveforms for the array processing.
	:type stream: :class:`obspy.core.stream.Stream`
	:param inventory: Station metadata for waveforms
	:type inventory: :class:`obspy.station.inventory.Inventory`
	:param event: If the event is given, the event distance in degree will also
	 be attached to the traces.
	:type event: :class:`obspy.core.event.Event`
	"""
	# Get the coordinates for all stations
	coords = {}
	for network in inventory:
		for station in network:
			coords["%s.%s" % (network.code, station.code)] = \
				{"latitude": station.latitude,
				 "longitude": station.longitude,
				 "elevation": station.elevation}

	# Calculate the event-station distances.
	if event:
		event_lat = event.origins[0].latitude
		event_lng = event.origins[0].longitude
		event_dpt = event.origins[0].depth/1000.
		for value in coords.values():
			value["distance"] = locations2degrees(
				value["latitude"], value["longitude"], event_lat, event_lng)
			value["depth"] = event_dpt

	# Attach the information to the traces.
	for trace in stream:
		try:
			station = ".".join(trace.id.split(".")[:2])
			value = coords[station]
			trace.stats.coordinates = AttribDict()
			trace.stats.coordinates.latitude = value["latitude"]
			trace.stats.coordinates.longitude = value["longitude"]
			trace.stats.coordinates.elevation = value["elevation"]
			if event:
				trace.stats.distance = value["distance"]
				trace.stats.depth = value["depth"]
		except:
			continue

def attach_epidist2coords(inventory, event, stream=None):
	"""
	Receives the epicentral distance of the station-source couple given in inventory - event and adds them to Array_Coords. 
	If called with stream, it uses just the coordinates of the used stations in stream.

	param inventory: 
	type inventory:

	param event:
	type event:

	param stream:
	type stream:
	"""
	inv = inventory
	Array_Coords = get_coords(inv)

	eventlat = event.origins[0].latitude
	eventlon = event.origins[0].longitude

	try:
		
		attach_network_to_traces(stream, inv[0])
		attach_coordinates_to_traces(stream, inv, event)
		for trace in stream:
			scode = trace.meta.network + "." + trace.meta.station
			Array_Coords[scode]["epidist"] =  trace.meta.distance

	except:

		for network in inv:
			for station in network:
				scode = network.code + "." + station.code
				lat1 = Array_Coords[scode]["latitude"]
				lat2 = Array_Coords[scode]["longitude"]
				# calculate epidist in km
				# adds an epidist entry to the Array_coords dictionary 
				Array_Coords[scode]["epidist"] = locations2degrees( lat1, lat2, eventlat, eventlon )

	return(Array_Coords)

def center_of_gravity(inventory):
    lats, lngs, hgts = __coordinate_values(inventory)
    return {
        "latitude": np.mean(lats),
        "longitude": np.mean(lngs),
        "elevation": np.mean(hgts)}

def geometrical_center(inventory):
    lats, lngs, hgt = __coordinate_values(inventory)

    return {
        "latitude": (np.max(lats) +
                     np.min(lats)) / 2.0,
        "longitude": (np.max(lngs) +
                      np.min(lngs)) / 2.0,
        "absolute_height_in_km":
        (np.max(hgt) +
         np.min(hgt)) / 2.0
    }

def aperture(inventory):
    """
    The aperture of the array in kilometers.
    Method:find the maximum of the calculation of distance of every possible combination of stations
    """
    lats, lngs, hgt = __coordinate_values(inventory)
    distances = []
    for i in range(len(lats)):
        for j in range(len(lats)):
            if lats[i] == lats[j]:
                continue
            distances.append(gps2dist_azimuth(lats[i],lngs[i],
                lats[j],lngs[j])[0] / 1000.0)
    return max(distances)

def find_closest_station(inventory, stream, latitude, longitude,
		                 absolute_height_in_km=0.0):
	"""
	If Station has latitude value of 0 check again!

	Calculates closest station of an inventory to a given latitude, longitude and absolute_height_in_km
	param latitude: latitude of interest, in degrees
	type latitude: float
	param longitude: longitude of interest, in degrees
	type: float
	param absolute_height_in_km: altitude of interest in km
	type: float
	"""
	used_stations = []
	for trace in stream:
		used_stations.append(trace.stats.station)

	min_distance = None
	min_distance_station = None

	lats, lngs, hgt = __coordinate_values(inventory)

	x = latitude
	y = longitude
	z = absolute_height_in_km

	for i, station in enumerate(inventory[0]):
		distance = np.sqrt( ((gps2dist_azimuth(lats[i], lngs[i], x, y)[0]) / 1000.0) ** 2  + ( np.abs( np.abs(z) - np.abs(hgt[i]))) ** 2 )
		if min_distance is None or distance < min_distance:
			if station.code in used_stations:
				min_distance = distance
				min_distance_station = station.code
	return min_distance_station
	
def epidist2list(Array_Coords):
	"""
	Returns a list of all epidistances in Array_Coords.
	"""
	epidist_list = []
	for scode in Array_Coords:
		if Array_Coords[scode]["epidist"]:
			epidist_list.append(Array_Coords[scode]["epidist"])
	
	epidist_list.sort()

	return(epidist_list)

def epidist2nparray(Array_Coords):
	"""
	Returns a numpy.ndarray of all epidistances in Array_Coords.
	"""
	epidist_np = []
	for scode in Array_Coords:
		if Array_Coords[scode]["epidist"]:
			epidist_np = np.append(epidist_np, [Array_Coords[scode]["epidist"]])
	
	epidist_np.sort()	
	return(epidist_np)

def isuniform(inv, event, stream=None, tolerance=0.5):
	"""
	Checks if the epicentral station distribution is uniform, in a given tolerance range.
	
	:param inv: Inventory with array information
	
	:param event:	 Event, that is used

	:param stream: stream-data, optional. If stream is an input only stations in stream will be used
			 for calculation

	:param tolerance: Percentage of deviation of ideal interstation spacing.
	:type tolerance: float

	returns: True or False
	"""

	distances = epidist2nparray( attach_epidist2coords(inv,event,stream) )
	delta_distances = np.diff(distances)	
	L = distances.max() - distances.min()
	ideal_delta = L / (distances.size - 1)
	
	ubound = ideal_delta * (1. + tolerance)
	lbound = ideal_delta * (1. - tolerance)

	for i in delta_distances:
		if lbound < i < ubound:
			continue
		else:
			return False

	return True

def find_equisets(numbers):
	"""
	Use Lomb-Scargle, get dominant wavelengths of the station-distribution.
	Use those to create grids, with tolerance, to find matching station-sets
	"""
	
	return



def alignon(st, inv, event, phase, ref=0 , maxtimewindow=0, shiftmethod='normal', taup_model='ak135'):
	"""
	Aligns traces on a given phase and truncates the starts to the latest beginning and the ends
	to the earliest end.
	
	:param st: stream
	
	:param inv: inventory

	:param event: Eventdata

	:param phase: Phase to align the traces on
	:type phase: str

	:param ref: name or index of reference station, to which the others are aligned
	:type ref: int or str

	:param maxtimewindow: Maximum timewindow in seconds, symmetrical around theoretical phase arrival time, 
						  in which to pick the maximum amplitude.
	:type maxtimewindow: int
	
	:param taup_model: model used by TauPyModel to calculate arrivals, default is ak135
	:type taup_model: str

	returns:
	:param st_align: Aligned and truncated stream on Phase
	:type st_align:

	"""
	# Prepare Array of data.
	st_tmp = st.copy()
	data = stream2array(st_tmp)
	shifttimes=np.zeros(data.shape[0])

	
	# Calculate depth and distance of receiver and event.
	# Set some variables.
	attach_coordinates_to_traces(st_tmp, inv, event)
	depth = event.origins[0]['depth']/1000.
	origin = event.origins[0]['time']
	m = TauPyModel(taup_model)
	tmin = 0
	tmax = 0

	if isinstance(ref, int):
		ref_dist = st[ref].stats.distance
		ref_start = st[ref].stats.starttime
		delta = st[ref].stats.delta
		iref = ref

	elif isinstance(ref, str):
		for i, trace in enumerate(st):
			if trace.stats['station'] != 'ref':
				continue
			ref_dist = trace.stats.distance
			iref = i
		ref_start = trace.stats.starttime
		delta = trace.stats.delta

	# Calculating reference arriving time/index of phase.
	ref_t = origin + m.get_travel_times(depth, ref_dist, phase_list=[phase])[0].time - ref_start
	ref_n = int(ref_t/delta)
	
	for no_x, data_x in enumerate(data):
		if no_x == iref:
			continue
	
		dist = st[no_x].stats.distance
		t = m.get_travel_times(depth, dist, phase_list=[phase])[0].time

		# Calculate arrivals, and shift times/indicies.
		phase_time = origin + t - st[no_x].stats.starttime
		phase_n = int(phase_time/delta)
		datashift, shift_index = shift2ref(data[no_x,:], ref_n, phase_n, mtw=maxtimewindow/delta, method=shiftmethod)
		shifttimes[no_x]=delta*shift_index
		data[no_x,:] = datashift

		# Positive shift_index indicates positive shift in time and vice versa.	
		if shift_index > 0 and shift_index > tmin: tmin = shift_index
		if shift_index < 0 and shift_index < tmax: tmax = abs(shift_index)

		data_trunc = truncate(data, tmin, tmax)

	st_align = array2stream(data_trunc, st)

	# Change startime entry and add alignon entry.
	for i, trace in enumerate(st_align):
		if i == iref:
			trace.stats.aligned = phase
		else:
			trace.stats.starttime = trace.stats.starttime - shifttimes[i]	
			trace.stats.aligned = phase

	return st_align


def shift2ref(array, tref, tshift, mtw=0, method='normal'):
	"""
	Shifts the trace in array to the order of tref - tshift. If mtw is given, tshift
	will be calculated depdending on the maximum amplitude of array in the give
	timewindow.

	:param array: array-like trace, 1D

	:param tref: Reference index, to be shifted

	:param tshift: Nondimensional shift value

	:param mtw: Maximum nondimensional timewindow symmetrical around tref, 
				in which to calculate the highest value of array
	
	Author: S. Schneider, 2016
	Source: Gubbins, D., 2004 Time series analysis and inverse theory for geophysicists
	"""

	trace=array.copy()
	# if mtw is set 
	if mtw != 0:
		tmin = tref - int(mtw/2.)
		tmax = tref + int(mtw/2.)
		stmax = trace[tref]
		mtw_index = tref
		for k in range(tmin,tmax+1):
			if trace[k] > stmax:
					stmax=trace[k]
					mtw_index = k
		shift_value = tref - mtw_index

	else:
		shift_value = tref - tshift

	if method in ("normal", "Normal"):
		shift_trace = np.roll(trace, shift_value)
	
	if method in ("FFT", "fft", "Fft", "fFt", "ffT", "FfT"):
		it = trace.size		
		iF = int(math.pow(2,nextpow2(it))) 
		dft = np.fft.fft(trace, iF)

		arg = -2. * np.pi * shift_value / float(iF)
		dft_shift = np.zeros(dft.size).astype('complex')

		for i, ampl in enumerate(dft):
			dft_shift[i] = ampl * np.complex(np.cos(i * arg), np.sin(i * arg))

		shift_trace = np.fft.ifft(dft_shift, iF)
		shift_trace = shift_trace[0:it].real			
	
	
	return shift_trace, shift_value


def corr_stat(stream, inv, phase):
	"""
	Static correction of the negative value of the ray parameter of the phase.
	"""
	if not stream[0].stats.distance or not stream[0].stats.depth:
		print("No event information attached to stream!")
		return
	
	st =stream.copy()
	data = stream2array(st)
	data_corr = np.zeros(data.shape)
	center = geometrical_center(inv)
	cstat =  find_closest_station(inv, st, center['latitude'], center['longitude'])
	
	tmin=0
	tmax=0

	for trace in stream:
		if trace.stats.station != cstat:
			continue
		depth = trace.stats.depth
		distance = trace.stats.distance
		delta = trace.stats.delta

	m = TauPyModel('ak135')
	arrival = m.get_travel_times(depth, distance, phase_list=[phase])
	slo = arrival[0].ray_param_sec_degree

	for i, trace in enumerate(data):
		shift = int( slo*( distance - st[i].stats.distance)/delta)
		print(shift)
		data_corr[i,:], shift_index = shift2ref(trace, 0, shift)
		if shift_index > 0 and shift_index > tmin: tmin = shift_index
		if shift_index < 0 and shift_index < tmax: tmax = abs(shift_index)
	data_corr = truncate(data, tmin, tmax)
	stream_corr = array2stream(data_corr, st)
	
	return stream_corr

def truncate(data, tmin, tmax):
	"""
	Truncates the data array on the left to tmin, on the right to right-end  - tmax.

	:param data: array-like

	:param tmin: new start index

	:param tmax: difference of the ending indicies
	"""
	if data.ndim > 1:
		trunc_n = data.shape[1] - tmin - tmax
		trunc_data = np.zeros( (data.shape[0], trunc_n) )

		for i,trace in enumerate(data):
			trunc_data[i,:] = trace[tmin:trace.size - tmax]

	else:
		trunc_n = data.size - tmin - tmax
		trunc_data = np.array( trunc_n )

		for x in data:
			trunc_data = data[tmin:data.size - tmax]

	return trunc_data

def stack(data, order=None):
	"""
	:param data: Array of data, that should be stacked.
				   Stacking is performed over axis = 1
	:type data: array_like

	:param order: Order of the stack
	:type order: int

	Author: S. Schneider, 2016
	Reference: Rost, S. & Thomas, C. (2002). Array seismology: Methods and Applications
	"""

	i, j = data.shape
	vNth = 0
	v = 0
	# if order is not None	
	try:
 		order = float(order)
		
		datasgn = np.sign(data)
		dataNth = abs(data)**(1./order)
		for i,trNth in enumerate(dataNth):
			vNth = vNth + datasgn[i] * trNth

		vsgn = np.sign(vNth)
		v = vsgn * abs(vNth)**order		

	except TypeError:
		for trace in data:
			v = v + trace
		v = v / data.shape[0]

	return v


def partial_stack(st, no_of_bins, phase, overlap=False, order=None, align=True, maxtimewindow=None, shiftmethod='normal', taup_model='ak135'):
	"""
	Will sort the traces into equally distributed bins and stack the bins.
	The stacking is just an addition of the traces, more advanced schemes might follow.
	The uniform distribution is useful for FK-filtering, SSA and every method that requires
	a uniform distribution.
	
	Needs depth information attached to the stream, array_util.see attach_coordinates_to_stream()
	and attach_network_to_traces()
	
	input:
	:param st: obspy stream object
	:type st: obspy.core.stream.Stream

	:param no_of_bins: number of bins, that should be used, if overlap is set, it is used to calculate
					   the size of each bin.
	:type no_of_bins: int

	:param phase: Phase 
	:type phase: str

	:param overlap: degree of overlap of each bin, e.g 0.5 corresponds to 50 percent
					overlap ov each bin
	:type: float

	:param order: Order of Nth-root stacking, default None
	:type order: float or int

	:param align: If True, traces will be shifted to reference time of the bin.
				  If Traces already aligned on a phase switch to False.
	:type align: bool

	:param maxtimewindow: Maximum timewindow in seconds, symmetrical around theoretical phase arrival time, 
						  in which to pick the maximum amplitude.

	:param taup_model:

	returns: 
	:param bin_data: partial stacked data of the array in no_of_bins uniform distributed stacks
	:type bin_data: array

	Author: S. Schneider, 2016
	Reference: Rost, S. & Thomas, C. (2002). Array seismology: Methods and Applications
	"""

	st_tmp = st.copy()

	data = stream2array(st_tmp, normalize=True)
	
	# Create list of distances from stations to array
	epidist = np.zeros(len(st_tmp))
	for i, trace in enumerate(st_tmp):
		epidist[i] = trace.stats.distance

	# Calculate the border of each bin 
	# and the new yinfo values.

	# Resample the borders of the bin, to overlap, if activated
	if overlap:
		bin_size = (epidist.max() - epidist.min()) / no_of_bins
		L = [ (epidist.min(), epidist.min() + bin_size) ]
		y_resample = [ epidist.min() + bin_size/2. ]
		i=0
		while ( L[i][0] + (1-overlap) * bin_size ) < epidist.max():
			lower = L[i][0] + (1-overlap) * bin_size
			upper = lower + bin_size
			L.append( (lower, upper) ) 
			y_resample.append( lower + bin_size/2. )
			i += 1

	else:
		L = np.linspace(min(epidist), max(epidist), no_of_bins+1)
		L = zip(L, np.roll(L, -1))
		L = L[0:len(L)-1]
		bin_size = abs(L[0][0] - L[0][1])

		# Resample the y-axis information to new, equally distributed ones.
		y_resample = np.linspace( min(min(L)) + bin_size/2., max(max(L))-bin_size/2., no_of_bins+1)
		bin_distribution = np.zeros(len(y_resample))

	# Preallocate some space in memory.
	bin_data = np.zeros((len(y_resample),data.shape[1]))

	
	m = TauPyModel(taup_model)
	depth = st_tmp[0].meta.depth
	delta = st_tmp[0].meta.delta

	# Calculate theoretical arrivals if align is enabled.
	if align:
		yr_sampleindex = np.zeros(len(y_resample)).astype('int')
		yi_sampleindex = np.zeros(len(epidist)).astype('int')
		for i, res_distance in enumerate(y_resample):
			yr_sampleindex[i] = int(m.get_travel_times(depth, res_distance, phase_list=[phase])[0].time / delta)
		
		for i, epi_distance in enumerate(epidist):
			yi_sampleindex[i] = int(m.get_travel_times(depth, epi_distance, phase_list=[phase])[0].time / delta)

	# Loop through all bins.
	for i, bins in enumerate(L):

		# Loop through all traces.
		for j, trace in enumerate(data):

			# First bin.
			if i==0 :
				if epidist[j] <= bins[1]:
					if align:
						trace_shift, si = shift2ref(trace, yr_sampleindex[i], yi_sampleindex[j], maxtimewindow/delta, method=shiftmethod)
					else:
						trace_shift = trace
					stack_arr = np.vstack([bin_data[i],trace_shift])
					bin_data[i] = stack(stack_arr, order)

			# Check if current trace is inside bin-boundaries.
			if epidist[j] > bins[0] and epidist[j] <= bins[1]:
				if align:
					trace_shift, si = shift2ref(trace, yr_sampleindex[i], yi_sampleindex[j], maxtimewindow/delta, method=shiftmethod)
				else:
					trace_shift = trace
				stack_arr = np.vstack([bin_data[i],trace_shift])
				bin_data[i] = stack(stack_arr, order)

			if overlap:
				if i == len(L):
					if align:
						trace_shift, si = shift2ref(trace, yr_sampleindex[i], yi_sampleindex[j], maxtimewindow/delta, method=shiftmethod)
					else:
						trace_shift = trace
					stack_arr = np.vstack([bin_data[i],trace_shift])
					bin_data[i] = stack(stack_arr, order)

	return bin_data

def vespagram(stream, inv, event, slomin, slomax, slostep, power=4, plot=False, markphases=['ttall', 'P^410P', 'P^660P'], method='FFT'):
	"""
	Creates a vespagram for the given slownessrange and slownessstepsize. Returns the vespagram as numpy array
	and if set a plot.

	:param st: Stream
	:type st: obspy.core.stream.Stream

	:param inv: inventory
	:type inv: obspy.station.inventory.Inventory

	:param event: Event
	:type event: obspy.core.event.Event

	:param slomin: Minimum of slowness range.
	:type slomin: int, float
	
	:param slomax: Maximum of slowness range.
	:type slomax: int, float
	
	:param slostep: Slowness stepsize.
	:type slostep: int
	
	:param power: Order of Nth-root stack, if None, just a linear stack is performed.
	:type power: float
	
	:param plot: If True, a figure is plottet with all theoretical arrivals, if set to 'contour'
				 a contour-plot is created.
	:type plot: bool or string.
	
	:param markphases: Which phases should be marked, default is 'ttall' + precursors, to mark all possible.
	:type markphases: list

	:param method: Shift method, to be used 'FFT' or 'normal'
	:type  method: string


	returns:

	:param vespa: The calculated Vespagram
	:type vespa: numpy.ndarray

	example:	import obspy
				from sipy.util.array_util import vespagram

				stream = obspy.read("../data/synthetics_uniform/SUNEW.QHD")
				inv = obspy.read_inventory("../data/synthetics_uniform/SUNEW_inv.xml")
				cat = obspy.read_events("../data/synthetics_random/SRNEW_cat.xml")
				vespagram = vespagram(stream, inv, cat[0], 3., 12., 0.1, power=4., plot='contour')

	Author: S. Schneider, 2016
	Reference: Rost, S. & Thomas, C. (2002). Array seismology: Methods and Applications
	"""

	# Prepare and convert objects.
	st = stream.copy()
	data = stream2array(st, normalize=True)

	attach_network_to_traces(st, inv[0])
	attach_coordinates_to_traces(st, inv, event)

	epidist = np.zeros(data.shape[0])
	for i,trace in enumerate(st):
		epidist[i]=trace.stats.distance
	#epidist.sort()

	dx = (epidist.max() - epidist.min() + 1) / epidist.size
	dsample = st[0].stats.delta
	Nsample = st[0].stats.npts

	# Find geometrical center station of array.
	center = geometrical_center(inv)
	
	cstat =  find_closest_station(inv, st, center['latitude'], center['longitude'])
	
	for i, trace in enumerate(st):
		if not trace.stats.station in [cstat]:
			continue
		else:
			sref=i

	# Prepare slownessrange, and allocate space in memory.
	uN = int ((slomax - slomin) / slostep + 1)
	urange = np.linspace(slomin, slomax, uN)
	it = data.shape[1]		
	iF = int(math.pow(2,nextpow2(it))) 
	dft = np.fft.fft(data, iF, axis=1)

	if method in ("fft"):
		# Calculate timeshift-table as a tensor, see shift2ref method "fft" as guide.
		timeshift_table = np.zeros((data.shape[0], urange.size, dft.shape[1])).astype('complex')
		
		# Slowness-Loop
		for j, slo in enumerate(urange):

			# Station-Loop
			for i in range(timeshift_table.shape[0]):
				sshift = int( abs(epidist[sref]-epidist[i]) * slo / dsample)
				if epidist[i] > epidist[sref]:
					timeshift_table[i][j] = np.exp((0.+ 1j) * ( 2. * np.pi * sshift / float(iF) ) * np.arange(dft.shape[1]))
				elif epidist[i] < epidist[sref]:
					timeshift_table[i][j] = np.exp((0.+ 1j) * ( -2. * np.pi * sshift / float(iF) ) * np.arange(dft.shape[1]))
				elif epidist[i] == epidist[sref]:
					timeshift_table[i][j] = 1. # np.exp((0.+ 1j) * 0) = 1.
				
		vespa = np.zeros( (uN, data.shape[1]) )

		# Transpose the tensor in right
		tst =  timeshift_table.transpose(1,0,2)
		
		# Slownesses
		for i, shifttable in enumerate(tst):
			dftshift = np.zeros(dft.shape).astype('complex')
			dftshift = dft * shifttable

			shiftdata = np.fft.ifft(dftshift, iF)
			vespatrace = shiftdata.real.copy()

			# Put it in the right size again.
			vespatrace = np.delete(vespatrace, np.s_[it:], 1)

			vespa[i] = stack(vespatrace, power)

	if method in ("normal"):
		vespa = np.zeros( (uN, data.shape[1]) )
		shift_data_tmp = np.zeros(data.shape)
	

		tmin=0
		tmax=0
		# Loop over all slownesses.
		for i, u in enumerate(urange):
			for j,trace in enumerate(data):
				sshift = int( abs(epidist[sref]-epidist[j]) * u / dsample)
				if epidist[j] > epidist[sref]:
					shift_data_tmp[j,:], shift_index = shift2ref(trace, 0, sshift, method="normal")

				elif epidist[j] < epidist[sref]:
					shift_data_tmp[j,:], shift_index = shift2ref(trace, 0, -sshift, method="normal")

				elif epidist[j] == epidist[sref]:
					shift_data_tmp[j,:] = trace
				# Positive shift_index indicates positive shift in time and vice versa.	
				#if shift_index > 0 and shift_index > tmin: tmin = shift_index
				#if shift_index < 0 and shift_index < tmax: tmax = abs(shift_index)

			vespa[i,:] = stack(shift_data_tmp, order=power)
		
		#vespa = truncate(vespa, tmin, tmax)

	vespa = vespa/vespa.max()		

	# Plotting routine
	if plot:
		
		if st[0].stats.aligned:
			refphase = st[0].stats.aligned
		else:
			refphase = None
		

		plt.figure()
		RE = 6371.0
		REdeg = kilometer2degrees(RE)
		origin = event.origins[0]['time']
		depth = event.origins[0]['depth']/1000.
		m = TauPyModel('ak135')
		dist = st[sref].stats.distance
		arrival =  m.get_travel_times(depth, dist, phase_list=markphases)


		# Labels of the plot.
		# Check if it is a relative plot to an aligned Phase.
		try:
			p_ref = m.get_travel_times(depth, dist, [refphase])[0].ray_param_sec_degree
			
			plt.ylabel(r'Relative $p$ in $\pm \frac{deg}{s}$  to %s arrival' % refphase, fontsize=12)
			try:
				plt.title(r'Relative %ith root Vespagram' %(power), fontsize=12 )
			except:
				plt.title(r'Relative linear Vespagram', fontsize=12 )
		except:
			p_ref = 0
			plt.ylabel(r'$p$ in $\frac{deg}{s}$')
			try:
				plt.title(r'%ith root Vespagram' %(power), fontsize=12 )
			except:
				plt.title(r'Linear Vespagram', fontsize=12 )
		
		

		
		plt.xlabel(r'Time in s', fontsize=15)
		taxis = np.arange(data.shape[1]) * dsample
		
		# Do the contour plot of the Vespagram.
		if plot in ['contour', 'Contour']:
			plt.imshow(vespa, aspect='auto', extent=(taxis.min(), taxis.max(), urange.min(), urange.max()), origin='lower')

			for phase in arrival:
				t = phase.time
				phase_time = origin + t - st[sref].stats.starttime
				Phase_npt = int(phase_time/st[sref].stats.delta)
				tPhase = Phase_npt * st[sref].stats.delta
				name = phase.name
				sloPhase = phase.ray_param_sec_degree - p_ref
				if tPhase > taxis.max() or tPhase < taxis.min() or sloPhase > urange.max() or sloPhase < urange.min():
					continue
				plt.plot(tPhase, sloPhase, 'x')
				plt.annotate('%s' % name, xy=(tPhase,sloPhase))

			plt.colorbar()

		# Plot all the traces of the Vespagram.
		else:
			plt.ylim(urange[0]-0.5, urange[urange.size-1]+0.5)
			plt.xticks(np.arange(taxis[0], taxis[taxis.size-1], 100))
			for i, trace in enumerate(vespa):
				plt.plot(taxis, trace+ urange[i], color='black')

			for phase in arrival:
				t = phase.time
				phase_time = origin + t - st[sref].stats.starttime
				Phase_npt = int(phase_time/st[sref].stats.delta)
				tPhase = Phase_npt * st[sref].stats.delta
				name = phase.name
				sloPhase = phase.ray_param_sec_degree - p_ref
				if tPhase > taxis.max() or tPhase < taxis.min() or sloPhase > urange.max() or sloPhase < urange.min():
					continue
				plt.plot(tPhase, sloPhase, 'x')
				plt.annotate('%s' % name, xy=(tPhase+1,sloPhase))
		plt.ion()
		plt.draw()
		plt.show()
		plt.ioff()

	return vespa


def gaps_fill_zeros(stream, inv, event, decimal_res=1):
	"""
	Fills the gaps inbetween irregular distributed traces 
	in Stream with zero-padded Traces for further work.

	:param stream: Obspy Stream

	:param inv: Obspy Inventory

	:param event: Obspy Event 

	:param d: Number of digits to round

	:returns: equi_stream
	"""
	st_tmp = stream.copy()
	d = 0.
	try:
		yinfo = epidist2nparray(epidist(inv, event, stream))
		attach_network_to_traces(stream, inv[0])
		attach_coordinates_to_traces(stream, inv, event)
	except:
		msg = "Need inventory and event information, not found"
		raise TypeError(msg)

	star = stream2array(st_tmp)
	
	# Define new grid for y-axis.
	grd_min = yinfo.min()
	grd_max = yinfo.max()
	
	decimal_res = float(decimal_res)
	# Find biggest value for y-ticks.
	mind = int(round(np.diff(yinfo).min() * decimal_res))
	maxd = int(round(np.diff(yinfo).max() * decimal_res))
	grd_delta = fractions.gcd(mind, maxd)/decimal_res
	
	N=(grd_max - grd_min)/grd_delta + 1
	
	grd = np.linspace(grd_min, grd_max, N) 
	
	equi_data = np.zeros((grd.size, star.shape[1]))
	
	# Create new Array and new Trace-object
	traces = []
	for i, trace in enumerate(equi_data):
		newtrace = obspy.core.trace.Trace(trace)
		newtrace.stats.distance = grd[i]
		newtrace.stats.processing = "empty"
		traces.append(newtrace)

	# Append data in Trace-Object
	for i, trace in enumerate(star):
		# Find nearest matching gridpoint for each trace.
		new_index = np.abs(grd-yinfo[i]).argmin()
		traces[ new_index ] = obspy.core.trace.Trace(trace)
		traces[ new_index ].stats = st_tmp[i].stats
		traces[ new_index ].stats.distance = grd[new_index]
	
	
	# Create new equidistant Stream-Object.
	equi_stream = Stream(traces)
	


	return equi_stream

def plot_inv(inventory, projection="local"):
    """
    Function to plot the geometry of the array, 
    including its center of gravity and geometrical center

    :type inventory: obspy.core.inventory.inventory.Inventory
    :param inventory: Inventory to be plotted

    :type projection: strg, optional
    :param projection: The map projection. Currently supported are:

    * ``"global"`` (Will plot the whole world.)
    * ``"ortho"`` (Will center around the mean lat/long.)
    * ``"local"`` (Will plot around local events)   
    """
    if isinstance(inventory, Inventory):
        inventory.plot(projection, show=False)
        bmap = plt.gca().basemap

        grav = center_of_gravity(inventory)
        x, y = bmap(grav["longitude"], grav["latitude"])
        bmap.scatter(x, y, marker="x", c="red", s=40, zorder=20)
        plt.text(x, y, "Center of Gravity", color="red")

        geo = geometrical_center(inventory)
        x, y = bmap(geo["longitude"], geo["latitude"])
        bmap.scatter(x, y, marker="x", c="green", s=40, zorder=20)
        plt.text(x, y, "Geometrical Center", color="green")
        plt.ion()
        plt.draw()
        plt.show()
        plt.ioff()




def plot_transfer_function(stream, inventory, sx=(-10, 10), sy=(-10, 10), sls=0.5, freqmin=0.1, freqmax=4.0,
                           numfreqs=10):
    """
    Plot transfer function (uses array transfer function as a function of
    slowness difference and frequency).

    :param sx: Min/Max slowness for analysis in x direction.
    :type sx: (float, float)
    :param sy: Min/Max slowness for analysis in y direction.
    :type sy: (float, float)
    :param sls: step width of slowness grid
    :type sls: float
    :param freqmin: Low corner of frequency range for array analysis
    :type freqmin: float
    :param freqmax: High corner of frequency range for array analysis
    :type freqmax: float
    :param numfreqs: number of frequency values used for computing array
     transfer function
    :type numfreqs: int
    """
    sllx, slmx = sx
    slly, slmy = sy
    sllx = kilometer2degrees(sllx)
    slmx = kilometer2degrees(slmx)
    slly = kilometer2degrees(slly)
    slmy = kilometer2degrees(slmy)
    sls = kilometer2degrees(sls)

    stepsfreq = (freqmax - freqmin) / float(numfreqs)
    transff = array_transff_freqslowness(stream, inventory, (sllx, slmx, slly, slmy),
                                               sls, freqmin, freqmax,
                                               stepsfreq)

    sllx = degrees2kilometers(sllx)
    slmx = degrees2kilometers(slmx)
    slly = degrees2kilometers(slly)
    slmy = degrees2kilometers(slmy)
    sls = degrees2kilometers(sls)

    slx = np.arange(sllx, slmx + sls, sls)
    sly = np.arange(slly, slmy + sls, sls)
    fig = plt.figure(figsize=(12, 12))
    ax = fig.add_axes([0.1, 0.1, 0.8, 0.8])

    # ax.pcolormesh(slx, sly, transff.T)
    ax.contour(sly, slx, transff.T, 10)
    ax.set_xlabel('slowness [s/deg]')
    ax.set_ylabel('slowness [s/deg]')
    ax.set_ylim(slx[0], slx[-1])
    ax.set_xlim(sly[0], sly[-1])
    plt.ion()
    plt.draw()
    plt.show()
    plt.ioff()

def plot_gcp(inventory, event, stream=None, phases=['P^410P', 'P^660P'], savefigure=None):
	"""
	Documantation follows, still working on. What kind of information would be useful to plot?
	Have to add a legend.
	"""
	model = TauPyModel('ak135')
	slat = event.origins[0].latitude
	slon = event.origins[0].longitude
	depth = event.origins[0].depth/1000.
	
	center = geometrical_center(inventory)
	rlat = center['latitude']
	rlon = center['longitude']
	pp = model.get_pierce_points_geo(depth, slat, slon, rlat, rlon, phases)
	pp = add_geo_to_arrivals(pp, slat, slon, rlat, rlon, 6372, 0)
	
	piercepoints = []
	plat = []
	plon = []
	for arrival in pp:
		name = arrival.name
		if not name in phases: continue

		piercedepth = float(name.split('^')[1][:3])
		count = 1
		for value in arrival.pierce:
			if value[3] != float(piercedepth): continue
			if depth < piercedepth and count == 2:
				plat.append(value[4])
				plon.append(value[5])
				piercepoints.append((value[4], value[5], piercedepth))
			elif depth > piercedepth and count == 1:
				plat.append(value[4])
				plon.append(value[5])
				piercepoints.append((value[4], value[5], piercedepth))
			
			count +=1


	# global m
	# lon_0 is central longitude of projection, lat_0 the central latitude.
	# resolution = 'c' means use crude resolution coastlines, 'l' means low, 'h' high etc.
	# zorder is the plotting level, 0 is the lowest, 1 = one level higher ...   
	# m = Basemap(projection='nsper',lon_0=20, lat_0=25,resolution='c')
	m = Basemap(projection='kav7',lon_0=piercepoints[0][1], resolution='c')   
	sx, sy = m(slon, slat)
	rx, ry = m(rlon, rlat)
	px, py = m(plon, plat)

	# import event coordinates, with symbol (* = Star)
	m.scatter(sx, sy, 80, marker='*', color= '#004BCB', zorder=2)
	# import station coordinates, with symbol (^ = triangle)
	m.scatter(rx, ry, 80, marker='^', color='red', zorder=2)
	# import bouncepoints coord.
	m.scatter(px, py, 10, marker='d', color='yellow', zorder=2)


	m.drawmapboundary(fill_color='#B4FFFF')
	m.fillcontinents(color='#00CC00',lake_color='#B4FFFF', zorder=0)
	m.drawcoastlines(zorder=1)

	# Greatcirclepath drawing from station to event
	# Check if qlat has a length
	#  try:
	#     for i in range(len(slat)):
	#       m.drawgreatcircle(slon[i], slat[i], rlon[i], rlat[i], linewidth = 1, color = 'black', zorder=1)
	#except TypeError:       
	m.drawgreatcircle(slon, slat, rlon, rlat, linewidth = 1, color = 'black', zorder=1)

	# Draw parallels and meridians.
	m.drawparallels(np.arange(-90.,120.,30.), zorder=1)
	m.drawmeridians(np.arange(0.,420.,60.), zorder=1)
	plt.title("")

	if savefigure:
		plt.savefig('plot_gcp.png', format="png", dpi=900)
	else:
		plt.ion()
		plt.draw()
		plt.show()
		plt.ioff()

