"""Check actual native FO runs and evaluate the unchanged saved CAD case."""
from pathlib import Path
import json
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.native import load_result, digest
from pyrocast_cfbt.exposure import room_series
from pyrocast_cfbt.spread import check_causality, simulate
from pyrocast_cfbt.flashover import proposals, source_curves, integral


def main():
    path=ROOT/'results/fo_transition_check'
    raw=json.loads((ROOT/'examples/fo_transition_check.json').read_text())
    # Reuses completed native caches if present; updates only this new result.
    d=simulate(raw,ROOT/'build/cfbt/cfast-cfbt.exe',path)
    assert d['error'] is None and len(d['fo_transitions'])==1
    assert d['simulation_complete_to_requested_horizon'] and d['fo_transition_search_complete']
    assert not d['spread_search_complete']  # Deliberately disabled in this isolated check.
    model=normalize(raw); at=d['fo_transitions'][0]['t_ign_s']
    before=load_result(path/'run_00',180,{'folder':str(path/'run_00')})
    after=load_result(path/'run_01',180,{'folder':str(path/'run_01')})
    check_causality(before,after,d['fo_transitions'][0],model['spread'])
    b=room_series(model,before)['R1']; a=room_series(model,after)['R1']
    t=after['zone']['Time']; mask=t<at-model['spread']['event_tolerance_s']
    delta=float(np.max(np.abs(a['T_upper_C'][mask]-b['T_upper_C'][mask])))
    assert delta < .2
    assert np.max(np.abs(a['T_upper_C']-b['T_upper_C']))>10
    assert np.max(np.abs(a['o2_upper_vol']-b['o2_upper_vol']))>.001
    assert np.max(np.abs(a['optical_density_upper_m_inv']-b['optical_density_upper_m_inv']))>.01
    assert min(a['o2_upper_vol'])>=0 and min(a['o2_lower_vol'])>=0
    curves,pools=source_curves(model,[],d['fo_transitions'])
    curve=curves['primary']; energy=float(integral(curve['t'],curve['q'],1e9))
    assert np.isclose(energy,3000000.,rtol=1e-10)
    assert np.all(np.asarray(d['room_fuel_pools']['R1']['remaining_solid_kg'])>=0)
    # Native receives one FIRE; no new heat source or O2 is injected directly.
    assert (path/'run_01/case.in').read_text().count('&FIRE ')==1
    assert np.max(after['zone']['HRR_1']-after['compartments']['HRR_E1'])<1.
    samples=[]
    for ti in (60,90,120,180):
        j=int(np.flatnonzero(t==ti)[0])
        record={'time_s':ti}
        for label,r,series in (('fixed_curve',before,b),('fo_transition',after,a)):
            record[label]={'upper_C':float(series['T_upper_C'][j]),
                           'lower_C':float(series['T_lower_C'][j]),
                           'actual_HRR_MW':float(r['zone']['HRR_1'][j]/1e6),
                           'oxygen_upper_vol_percent':float(series['o2_upper_vol'][j]*100),
                           'optical_density_upper_m_inv':float(series['optical_density_upper_m_inv'][j])}
        samples.append(record)

    cad_path=ROOT/'results/cad_opening_30min/result.json'
    cad_hash=digest(cad_path)
    cad=json.loads(cad_path.read_text(encoding='utf-8'))
    cm=normalize(cad['scenario']);cm['flashover']['enabled']=True
    cr={'zone':{'Time':np.asarray(cad['time_s'])}}
    # Existing temperature samples suffice: if no threshold crossing exists,
    # inserting a solely post-threshold mode cannot alter any earlier state.
    cad_events=proposals(cm,cr,cad['rooms'],cad['ignitions'],[],cad['candidates'])
    assert not cad_events
    assert digest(cad_path)==cad_hash
    summary={
        'purpose':'functional comparison, not validation of a real fire',
        'case':'one room 4x4x3 m; different from CAD R9',
        'fo_threshold_C':600,'fo_time_s':at,'transition_s':pools['R1']['ramp_s'],
        'post_transition_hrrpua_kW_m2':500,
        'ramp_and_hrrpua_basis':'declared exploration assumptions, not NIST universal defaults',
        'native_engine_sha256':digest(ROOT/'build/cfbt/cfast-cfbt.exe'),
        'before_input_sha256':digest(path/'run_00/case.in'),
        'after_input_sha256':digest(path/'run_01/case.in'),
        'pre_transition_upper_temperature_max_difference_C':delta,
        'finite_full_curve_energy_kJ':energy,'allocated_energy_kJ':3000000.,
        'normal_runs':d['successful_runs_count'],'post_transition_native_fire_count':1,
        'samples':samples,
        'cad_R9':{'method':'stored 30-minute data evaluated; no new native execution',
                  'result_sha256':cad_hash,'threshold_C':600,
                  'all_CAD_room_transition_proposals':len(cad_events),
                  'R9_upper_max_C':max(cad['rooms']['CAD_3F_R9']['T_upper_C']),
                  'floor_flux_evaluated':False,
                  'conclusion':'600 C switch does not activate on this existing trajectory'},
        'limits':['prescribed fuel supply, not predicted pyrolysis',
                  'original aperture and direct-flame radiation retained',
                  'external reruns, no continuous-engine speedup claimed',
                  'native/plume assumptions retained; no NIST certification claimed']}
    output=ROOT/'results/verification/fo_transition_checks.json'
    output.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    # Compact reusable comparison data for plotting without another engine run.
    np.savez(path/'comparison.npz',time_s=t,fo_time_s=at,
             baseline_upper_C=b['T_upper_C'],transition_upper_C=a['T_upper_C'],
             baseline_HRR_MW=before['zone']['HRR_1']/1e6,transition_HRR_MW=after['zone']['HRR_1']/1e6,
             baseline_o2_percent=b['o2_upper_vol']*100,transition_o2_percent=a['o2_upper_vol']*100,
             baseline_OD_m_inv=b['optical_density_upper_m_inv'],transition_OD_m_inv=a['optical_density_upper_m_inv'])
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
