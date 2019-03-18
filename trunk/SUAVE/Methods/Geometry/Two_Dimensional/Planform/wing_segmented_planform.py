## @ingroup Methods-Weights-Correlations-Common
# wing_segmented_planform.py
# 
# Created:  Mar 2019, E. Botero 
# Modified: 

# ----------------------------------------------------------------------
#  Imports
# ----------------------------------------------------------------------
import SUAVE
from SUAVE.Core import Data

import numpy as np

# ----------------------------------------------------------------------
#  Methods
# ----------------------------------------------------------------------

def wing_segmented_planform(wing):
    """Computes standard wing planform values.
    
    Assumptions:
    Multisigmented wing. We only find the first spanwise location of the mean aerodynamic chord.
    There is no unexposed wetted area, ie wing that intersects a fuselage
    
    Source:
    None
    
    Inputs:
    wing.
      chords.root              [m]
      spans.projected          [m]
      symmetric                <boolean> Determines if wing is symmetric
    
    Outputs:
    wing.
      spans.total              [m]
      chords.tip               [m]
      chords.mean_aerodynamics [m]
      areas.reference          [m^2]
      taper                    [-]
      sweeps.quarter_chord     [radians]
      aspect_ratio             [-]
      thickness_to_chord       [-]
      dihedral                 [radians]
      
      aerodynamic_center       [m]      x, y, and z location

        
    
    Properties Used:
    N/A
    """
    
    # Unpack
    span = wing.spans.projected
    RC   = wing.chords.root
    sym  = wing.symmetric
    
    # Pull all the segment data into array format
    span_locs = []
    twists    = []
    sweeps    = []
    dihedrals = []
    chords    = []
    t_cs      = []
    for key in wing.Segments:
        seg = wing.Segments[key]
        span_locs.append(seg.percent_span_location)
        twists.append(seg.twist)
        chords.append(seg.root_chord_percent)
        sweeps.append(seg.sweeps.quarter_chord)
        t_cs.append(seg.thickness_to_chord)
        dihedrals.append(seg.dihedral_outboard)
        
    # Convert to arrays
    chords    = np.array(chords)
    span_locs = np.array(span_locs)
    sweeps    = np.array(sweeps)
    t_cs      = np.array(t_cs)
    
    # Basic calcs:
    semispan     = span/(1+sym)
    lengths_ndim = span_locs[1:]-span_locs[:-1]
    lengths_dim  = lengths_ndim*semispan
    chords_dim   = RC*chords
    tapers       = chords[1:]/chords[:-1]
    
    # Calculate the areas of each segment
    As = RC*((lengths_dim)*chords[:-1]-(chords[:-1]-chords[1:])*(lengths_dim)/2)
    
    # Calculate the weighted area, this should not include any unexposed area 
    A_wets = 2*(1+0.2*t_cs[:-1])*As
    wet_area = np.sum(A_wets)
    
    # Calculate the wing area
    ref_area = np.sum(As)*2
    
    # Calculate the Aspect Ratio
    AR = (span**2)/ref_area
    
    # Calculate the total span
    lens = lengths_dim/np.cos(dihedrals[:-1])
    total_len = np.sum(np.array(lens))*(1+sym)
    
    # Calculate the mean geometric chord
    mgc = ref_area/span
    
    # Calculate the mean aerodynamic chord
    A = chords_dim[:-1]
    B = (A-chords_dim[1:])/(-lengths_ndim)
    C = span_locs[:-1]
    integral = ((A+B*(span_locs[1:]-C))**3-(A+B*(span_locs[:-1]-C))**3)/(3*B)
    # For the cases when the wing doesn't taper in a spot
    integral[np.isnan(integral)] = (A[np.isnan(integral)]**2)*((lengths_ndim)[np.isnan(integral)])
    panel_mac = integral*lengths_dim*(1+sym)/As
    MAC = (semispan*(1+sym)/(ref_area))*np.sum(integral)
    
    # Calculate the effective taper ratio
    lamda = 2*mgc/RC - 1
    
    # effective tip chord
    ct = lamda*RC
    
    # Calculate an average t/c weighted by area
    t_c = np.sum(As*t_cs[:-1])/(ref_area/2)
    
    # Calculate the segment leading edge sweeps
    r_offsets = chords_dim[:-1]/4
    t_offsets = chords_dim[1:]/4
    le_sweeps = np.arctan((r_offsets+np.tan(sweeps[:-1])*(lengths_dim)-t_offsets)/(lengths_dim))    
    
    # Calculate the effective sweeps
    c_4_sweep   = np.arctan(np.sum(lengths_ndim*np.tan(sweeps[:-1])))
    le_sweep_total= np.arctan(np.sum(lengths_ndim*np.tan(le_sweeps)))

    # Calculate the aerodynamic center, but first the centroid
    dxs = np.cumsum(np.concatenate([np.array([0]),np.tan(le_sweeps[:-1])*lengths_dim[:-1]]))
    dys = np.cumsum(np.concatenate([np.array([0]),lengths_dim[:-1]]))
    dzs = np.cumsum(np.concatenate([np.array([0]),np.tan(dihedrals[:-2])*lengths_dim[:-1]]))
    
    Cxys = []
    for i in range(len(lengths_dim)):
        Cxys.append(segment_centroid(le_sweeps[i],lengths_dim[i]*(1+sym),dxs[i],dys[i],dzs[i], tapers[i], As[i], panel_mac[i], dihedrals[i]))

    aerodynamic_center= np.dot(np.transpose(Cxys),As)/(ref_area/(1+sym))
    
    # If necessary the location of the MAC in the Y-direction could be outputted before overwriting
    if sym== True:
        aerodynamic_center[1] = 0
    
    # Total length for supersonics
    total_length = np.tan(le_sweep_total)*semispan + chords[-1]*RC
    
    # Pack stuff
    wing.areas.reference         = ref_area
    wing.areas.wetted            = wet_area
    wing.aspect_ratio            = AR
    wing.spans.total             = total_len
    wing.chords.mean_geometric   = mgc
    wing.chords.mean_aerodynamic = MAC
    wing.chords.tip              = ct
    wing.taper                   = lamda
    wing.sweeps.quarter_chord    = c_4_sweep
    wing.sweeps.leading_edge     = le_sweep_total
    wing.thickness_to_chord      = t_c
    wing.aerodynamic_center      = aerodynamic_center
    wing.total_length            = total_length
    
    return wing

# Segment centroid
def segment_centroid(le_sweep,seg_span,dx,dy,dz,taper,A,mac,dihedral):
    """Computes the centroid of a polygonal segment
    
    Assumptions:
    Polygon
    
    Source:
    None
    
    Inputs:
    seg_le_sweep  [rad]
    seg_span      [m]
    dx            [m]
    dy            [m]
    taper         [dimensionless]
    A             [m**2]
    mac           [m]
    dihedral      [radians]

    Outputs:
    cx,cy         [m,m]

    Properties Used:
    N/A
    """    
    
    cy = seg_span / 6. * (( 1. + 2. * taper ) / (1. + taper))
    cx = mac * 0.25 + cy * np.tan(le_sweep)
    cz = cy * np.tan(dihedral)    
    
    return np.array([cx+dx,cy+dy,cz+dz])