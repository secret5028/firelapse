"""Diagnostic-only checks: receiving attribution, no double count, unchanged T/O."""
import copy
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'simulation'),str(ROOT/'simulation/deps')]
import numpy as np
from pyrocast_cfbt.conditions import screening_scores, evaluate
from pyrocast_cfbt.fo_hrr import apply_fo_hrr
from pyrocast_cfbt.model import DEFAULTS, merge


def main():
    old=screening_scores(([600.,300.,600.],600.,False),([0.,0.,0.],100.,False),([12.,12.,6.],12.,False),3)
    rec={'scores':copy.deepcopy(old)}
    apply_fo_hrr(rec,[0.,0.,0.],[100.,100.,100.],[100.]*3)
    assert rec['scores']['degree']==[1.,.5,.5]
    assert rec['scores']['factors']['temperature']==old['factors']['temperature']
    assert rec['scores']['factors']['oxygen']==old['factors']['oxygen']
    first=copy.deepcopy(rec);apply_fo_hrr(rec,[0.]*3,[100.]*3,[100.]*3);assert rec==first
    unknown=copy.deepcopy(first);apply_fo_hrr(unknown,[0.]*3,[None,100.,100.],[100.]*3)
    assert unknown['scores']['degree'][0] is None
    # Exercise the actual common evaluator: same door jet appears in native
    # room total and directional aggregate, but must be counted exactly once.
    room={'id':'A','size_m':[5.,5.,3.],'origin_m':[0.,0.,0.]}
    model=merge(DEFAULTS,{'rooms':[room],'openings':[],'fuel_groups':[]})
    s={'T_upper_C':np.array([600.]),'o2_upper_vol':np.array([.15]),'o2_lower_vol':np.array([.12]),
       'upper_mass_kg':np.array([10.]),'fuel_upper_kg':np.array([.1]),'fuel_upper_J':np.array([1e6]),'bulk_HRR_W':np.array([10000.])}
    p={'vent_HRR_W':np.array([100000.]),'floor_incident_flux_kW_m2':None,
       'tags':{'FGI_POTENTIAL':[False]},'temperature_rate_C_s':np.array([0.]),'fuel_in_kg_s':np.array([0.])}
    result={'time_s':[0.],'rooms':{'A':s},'phenomena':{'A':p},'solid_fuel_inventory':{},
       'zone':{'DJET_1':np.array([100000.])},'ignitions':[],'candidates':[],'directional_vent_reactions':[]}
    native=evaluate(model,result)['A']['fo'];assert native['score_basis']['Q_actual_kW']==[110.]
    assert native['actual_quantities']['Q_actual_kW']==[110.]
    assert native['actual_quantities']['Q_source_kW']==[0.]
    s['received_door_jet_HRR_W']=np.array([200000.])
    lite=evaluate(model,result)['A']['fo'];assert lite['score_basis']['Q_actual_kW']==[210.]
    s['received_door_jet_HRR_W']=np.array([0.])
    assert evaluate(model,result)['A']['fo']['score_basis']['Q_actual_kW']==[10.]
    print('PASS: shared native/lite receiving precedence; exactly-once; T/O unchanged; idempotence; unknown retained')

if __name__=='__main__':main()
