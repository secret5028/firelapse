"""Read-only L4 diagnostic of saved 10s states; no new integration or repair."""
import json
from pathlib import Path
import run_lite_l1 as base
import numpy as np
from pyrocast_lite.adapter import prepare
from pyrocast_lite.core import P0,RG,CP
ROOT=base.ROOT;OUT=ROOT/'simulation/results/lite_l1c_20261025'

def audit(stage):
    folder=OUT/stage/'standard'
    result=json.loads((folder/'result.json').read_text('utf-8'))
    raw=json.loads(base.inputs()['3F'].read_text('utf-8'));raw['room_rule_r8']={'preset':'standard','room_supply':'item_peak'}
    m,_=prepare(raw,{'gas_radiation_enabled':stage=='radiation_on'})
    for event in result['events']:m.activation[event['room']]=event['condition_time_s']
    state=np.load(folder/'state.npz');t=state['t'];ys=state['y'];n=m.N
    masses=[];energies=[];mass_rates=[];energy_rates=[];mass_defects=[];mass_in=[];energy_in=[];book_errors=[]
    for j,ts in enumerate(t):
        y=ys[:,j];dy=m.rhs(float(ts),y);d=m.rhs(float(ts),y,diag=True)
        vu=np.clip(y[n:2*n],m.Vmin,m.Va-m.Vmin);vl=m.Va-vu
        tu=np.maximum(y[2*n:3*n],200);tl=np.maximum(y[3*n:4*n],200)
        masses.append(float(np.sum(P0/RG*(vu/tu+vl/tl))))
        gas_energy=float(np.sum(P0/RG*(CP-RG)*m.Va))
        energies.append(gas_energy+float(np.sum(y[8*n+1:].reshape(n,3)*m.finite_walls.capacity)))
        mdot=float(np.sum(P0/RG*(dy[n:2*n]*(1/tu-1/tl)-vu*dy[2*n:3*n]/tu**2-vl*dy[3*n:4*n]/tl**2)))
        mass_rates.append(d['boundary_mass_in']-d['boundary_mass_out']+d['pyro_mass_rate'])
        erate=d['boundary_enthalpy_in']-d['boundary_enthalpy_out']+d['Q']+CP*m.P['T_pyro']*d['pyro_mass_rate']-d['wall_back_W']
        energy_rates.append(erate)
        mass_defects.append(mdot-mass_rates[-1])
        mass_in.append(d['boundary_mass_in']+d['pyro_mass_rate'])
        energy_in.append(d['boundary_enthalpy_in']+d['Q']+CP*m.P['T_pyro']*d['pyro_mass_rate'])
        book_errors.append(abs(erate-d['heat_rate']-d['wall_storage_W']))
    def cum(v):return np.r_[0.,np.cumsum((np.array(v)[1:]+np.array(v)[:-1])*.5*np.diff(t))]
    md=np.maximum(masses[0],cum(mass_in));ed=np.maximum(energies[0],cum(energy_in))
    mr=np.array(masses)-masses[0]-cum(mass_rates);er=np.array(energies)-energies[0]-cum(energy_rates)
    mp=float(np.max(np.abs(mr)/md)*100);ep=float(np.max(np.abs(er)/ed)*100)
    # 10s output integration is not accepted-step quadrature: never certify a
    # small sampled residual as L4 pass. A large residual is reported, not tuned.
    r={'stage':stage,'status':'sampled_diagnostic_not_certified','passed':False,
       'mass_max_cumulative_relative_percent':mp,'energy_max_cumulative_relative_percent':ep,
       'mass_end_residual_kg':float(mr[-1]),'energy_end_residual_J':float(er[-1]),
       'max_local_energy_bookkeeping_error_W':max(book_errors),
       'mass_closure_integrated_abs_defect_kg':float(np.trapezoid(np.abs(mass_defects),t)),
       'mass_closure_defect_relative_percent':float(np.trapezoid(np.abs(mass_defects),t)/md[-1]*100),
       'threshold_percent':.1,'sample_s':10,
       'normalization':'max(initial inventory,cumulative gross input), at each time',
       'inventory_basis':'model P0/(R*T) densities; gas internal energy m*(Cp-R)*T; wall node thermal energy',
       'limits':['only stored10s states; net boundary flux cancellation makes output quadrature unreliable',
                 'fixed-P0 density/clamped-volume closure differs from independent conservative mass state',
                 'no new integration, solver change or physical repair; accepted-step cumulative ledgers still needed']}
    base.save(folder/'balance-diagnostic.json',r);print(json.dumps(r,ensure_ascii=False),flush=True)

if __name__=='__main__':
    audit('trigger_only');audit('radiation_on')
