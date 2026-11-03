"""C11 r2 P1 only: stock CFAST input, one process, read-only diagnostics.

prepare/run/analyze are separate so postprocessing never repeats a simulation.
Condition diagnostics use the current shared formula; raw engine output stays immutable.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'simulation'), str(ROOT / 'simulation/deps')]
import numpy as np
from pyrocast_cfbt.model import DEFAULTS, merge
from pyrocast_cfbt.deck import fire_curve, make_deck
from pyrocast_cfbt.native import execute, read_native_csv
from pyrocast_cfbt.conditions import screening_scores, screening_lfl, fo_required_hrr
from pyrocast_cfbt.fo_hrr import apply_fo_hrr

OUT = ROOT / 'simulation/results/wando_C11_P1_20261102'
EXE = ROOT / 'simulation/build/baseline/cfast-baseline.exe'
SPEC = ROOT / 'specs/Claude지시-C11-완도저온창고사례-20261102.md'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / 'attempt.json').exists():
        raise RuntimeError('P1 already attempted; no input rewrite or automatic rerun')
    lining = 2 * 8.75 * 6.405
    fuel = dict(id='PU', room='CAVITY', initial_time_s=0., position_m=[1.75, 18.05, 0.],
                energy_MJ=lining * .1 * 35 * 25, peak_kW=lining * 400,
                growth_kW_s2=.00293, hrrpua_kW_m2=400., fuel_area_m2=lining,
                heat_of_combustion_kJ_kg=25000., formula={'carbon':1.,'hydrogen':1.8,'oxygen':.3,'nitrogen':.1}, co_yield=.05)
    # Wall lining area is the fuel inventory area, not the cavity's tiny floor.
    # Preserve the existing finite-energy 70%-growth / 30%-decay input convention.
    t, q, _ = fire_curve(fuel, lining)
    fuel['room_rule_curve'] = {'t':t, 'q':q, 'area':[min(.875, max(.1, v/400)) for v in q]}
    mats = json.loads((ROOT / 'data/wando-coldstore/thermal-input.json').read_text(encoding='utf-8'))
    surface = mats['surface_materials']
    rooms = [dict(id='ROOM',origin_m=[0.,0.,0.],size_m=[8.75,18.,6.405]),
             dict(id='CAVITY',origin_m=[0.,18.,0.],size_m=[8.75,.1,6.405])]
    for r in rooms:
        r.update(surface_material_ids={'wall':'PU_LINING','ceiling':'PU_LINING','floor':'CONCRETE_FLOOR'},
                 leak_area_ratio=[0.,0.])
    def vent(ident,a,b,width,bottom,top,face,offset,schedule):
        return dict(id=ident,a=a,b=b,type='WALL',width_m=width,bottom_m=bottom,top_m=top,
                    face=face,offset_m=offset,schedule=schedule)
    openings = [vent('ENTRY','ROOM','OUTSIDE',2.5,0.,3.,'FRONT',3.125,[[0,1]]),
                vent('BOTTOM_GAP','CAVITY','ROOM',8.75,0.,.01,'FRONT',0.,[[0,1]]),
                vent('TOP_GAP','CAVITY','ROOM',8.75,6.4,6.405,'FRONT',0.,[[0,1]]),
                vent('CUT','CAVITY','ROOM',2.,.5,2.5,'FRONT',.75,
                     [[0,0],[1320,0],[1320,.5],[1800,.5],[1800,1]])]
    model = merge(DEFAULTS, dict(duration_s=3600., output_step_s=5., max_time_step_s=1., ambient_C=15.,
                                surface_materials=surface, rooms=rooms, openings=openings, fuel_groups=[fuel]))
    model['gas'].update(enabled=False,bulk_enabled=False,vent_gate_enabled=False)
    model['spread']['enabled'] = False
    # The generic project normalizer rejects <0.6 m rooms. The stock deck reader
    # accepts this explicit 0.1 m case; do not weaken production validation.
    deck = make_deck(model, [], []).replace('SOOT_YIELD=0.02', 'SOOT_YIELD=0.1')
    deck = deck.replace('SIMULATION=3605', 'SIMULATION=3600')
    assert '&CFBT' not in deck and '&MVENT' not in deck
    assert abs(np.trapezoid(q,t)/1000-fuel['energy_MJ']) < 1e-6
    (OUT / 'case.in').write_text(deck, encoding='ascii')
    save('model.json', model)
    frozen = [EXE, SPEC, ROOT/'simulation/pyrocast_cfbt/conditions.py',
              ROOT/'simulation/pyrocast_cfbt/deck.py', ROOT/'simulation/pyrocast_cfbt/model.py']
    save('input-evidence.json', dict(engine='stock CFAST 7.7.7',
        hashes={str(p.relative_to(ROOT)):sha(p) for p in frozen}, deck_sha256=sha(OUT/'case.in'),
        cavity_lining_area_m2=lining, energy_MJ=fuel['energy_MJ'], peak_cap_kW=fuel['peak_kW'],
        prescribed_peak_kW=max(q), prescribed_peak_s=t[int(np.argmax(q))], supply_end_s=t[-1],
        integrated_supply_MJ=float(np.trapezoid(q,t)/1000), output_step_s=5., wall_budget_s=1800,
        assumptions=['70% energy before linear decay: existing fire_curve default; not fitted to 2100 s',
          'Fire footprint Q/400 capped at cavity floor 0.875 m2; lining energy separately preserved',
          'No unspecified envelope leakage; only the three explicit cavity openings',
          'CUT center x=1.75 m; instantaneous right-limit steps using repeated TIME knots',
          'CFAST native opening fraction changes width only',
          'Native solver MAX_TIME_STEP=1 s; output every 5 s',
          '15 C initial inside and outside; fan OFF; wind omitted',
          'Very thin cavity as two-zone compartment is an unvalidated geometry approximation',
          'No solid secondary fire in ROOM; no project gas combustion or forced FGI'],
        notes=['DJET is receiving-compartment total, not separable by gap versus CUT in stock CSV',
               'Four indices reuse conditions.py screening functions and DEFAULTS, not new criteria']))
    print(json.dumps(json.loads((OUT/'input-evidence.json').read_text(encoding='utf-8')),ensure_ascii=False,indent=2))


def run(scenario='P1'):
    with (OUT/'attempt.json').open('x',encoding='utf-8') as f:
        json.dump({'authorized_runs':1,'scenario':scenario,'budget_s':1800},f)
    try:
        result=execute(EXE,OUT,(OUT/'case.in').read_text(encoding='ascii'),'',3600,1800,stall_timeout_s=0)
        save('run-summary.json',result['run'])
        print(json.dumps(result['run'],ensure_ascii=False))
    except Exception as exc:
        save('run-failure.json',{'error':str(exc),'rerun':False})
        raise


def analyze(scenario='P1', fan_on=False):
    import csv
    model=json.loads((OUT/'model.json').read_text(encoding='utf-8'))
    c,_,cu=read_native_csv(OUT/'case_compartments.csv')
    m,_,mu=read_native_csv(OUT/'case_masses.csv')
    v,vid,_=read_native_csv(OUT/'case_vents.csv')
    t=c['Time'];n=len(t)
    assert np.array_equal(t,m['Time']) and np.array_equal(t,v['Time'])
    assert t[-1] in (3595,3600) and 'NORMAL EXIT' in (OUT/'case.log').read_text(errors='replace').upper()
    assert cu['ULO2_1']=='mol_frac' and mu['ULMTUHC_1']=='kg'
    evidence=json.loads((OUT/'input-evidence.json').read_text(encoding='utf-8'))
    unchanged={p:sha(ROOT/p)==h for p,h in evidence['hashes'].items()}
    # A later specification edit does not invalidate the immutable run input.
    # Preserve its mismatch in the audit; engine/physics/deck remain mandatory.
    diagnostic_files={'simulation/pyrocast_cfbt/conditions.py'}
    assert all(v for p,v in unchanged.items() if not p.startswith('specs') and p not in diagnostic_files) and sha(OUT/'case.in')==evidence['deck_sha256']
    states={};series={'time_s':t.tolist()};scores={};summaries={};shared_states={}
    def peak(a):
        j=int(np.argmax(a));return {'value':float(a[j]),'time_s':float(t[j])}
    def first(a,value,lower=False):
        hits=np.flatnonzero(np.asarray(a)<=value if lower else np.asarray(a)>=value)
        return float(t[hits[0]]) if len(hits) else None
    opening_states={}
    for i,op in enumerate(model['openings'],1):
        key=next(k for k in v if k.startswith('WF_') and vid[k]==op['id'])
        opening_states[op['id']]={'fraction':v[key]}
    for i,room in enumerate(model['rooms'],1):
        rid=room['id'];T=c[f'ULT_{i}'];O=c[f'ULO2_{i}']*100;Ol=c[f'LLO2_{i}']*100
        # Native ns_mass=9: count soot once; exclude soot subcategories, trace,
        # potential products and fuel-moles diagnostics (all double counts).
        total=sum(m[f'ULM{s}_{i}'] for s in ('N2','O2','CO2','CO','HCN','HCL','TUHC','H2O','OD'))
        assert np.all(total>0)
        yf=m[f'ULMTUHC_{i}']/total
        g=model['gas'];cr=model['criteria'];q=c['HRR_1']/1000 if rid=='CAVITY' else np.zeros(n)
        required=fo_required_hrr(model,{'time_s':t,'opening_states':opening_states},room,t)
        records={
            'FO':screening_scores((T,cr['fo_temperature_C'],False),(q,required,False),(Ol,g['oxygen_min_vol_percent'],False),n),
            'FGI':screening_scores((T,g['hot_C'],False),(yf,screening_lfl(model,T),False),(O,cr['fgi_oxygen_vol_percent'],False),n),
            'BD':screening_scores((T,cr['hot_C'],False),(yf,cr['fuel_rich_mass_fraction'],False),(O,cr['oxygen_deficient_vol_percent'],True),n)}
        fo_record={'scores':records['FO']}
        apply_fo_hrr(fo_record,q,c[f'DJET_{i}']/1000,required)
        records['FO']=fo_record['scores']
        scores[rid]=records
        idx={k:100*np.asarray(r['degree'],dtype=float) for k,r in records.items()}
        assert all(np.isfinite(a).all() for a in idx.values())
        states[rid]={'T_upper_C':T,'O2_upper_vol_percent':O,'fuel_upper_mass_fraction':yf,
                     'interface_m':c[f'HGT_{i}'],'source_HRR_kW':q,'door_jet_kW':c[f'DJET_{i}']/1000,**idx}
        shared_states[rid]={'T_upper_C':T,'o2_upper_vol':O/100,'o2_lower_vol':Ol/100,
            'upper_mass_kg':total,'fuel_upper_kg':m[f'ULMTUHC_{i}'],
            'fuel_upper_J':m[f'ULMTUHC_{i}']*25e6,'bulk_HRR_W':np.zeros(n),'received_door_jet_HRR_W':c[f'DJET_{i}']}
        summaries[rid]={'temperature_peak_C':peak(T),'source_HRR_peak_kW':peak(q),
                       'door_jet_peak_kW':peak(c[f'DJET_{i}']/1000),
                       'fuel_mass_fraction_peak':peak(yf),'minimum_O2_vol_percent':float(O.min()),
                       'interface_first_below_3m_s':first(c[f'HGT_{i}'],3,True),
                       'interface_first_below_1_8m_s':first(c[f'HGT_{i}'],1.8,True),
                       'indices':{k:{'first_70_s':first(a,70),'first_100_s':first(a,100),'peak':peak(a)} for k,a in idx.items()}}
        series[rid]={k:a.tolist() for k,a in states[rid].items()}
    expected_cut={float(p[1]) for p in next(op for op in model['openings'] if op['id']=='CUT')['schedule']}
    assert set(np.round(opening_states['CUT']['fraction'],8))==expected_cut
    # Verify direct helper calls against the full shared diagnostic evaluator.
    from pyrocast_cfbt.conditions import evaluate
    from pyrocast_cfbt.spread import classify
    native={'zone':{'Time':t,'HRR_1':c['HRR_1']},'slabs':[],'vents':[]}
    classified=classify(model,native,shared_states,[],[])
    curve=model['fuel_groups'][0]['room_rule_curve']
    common=evaluate(model,dict(time_s=t,rooms=shared_states,phenomena=classified,
        solid_fuel_inventory={'PU':{'actual_HRR_W':c['HRR_1'],
            'prescribed_pyrolysis_kW':np.interp(t,curve['t'],curve['q'])}},
        opening_states=opening_states,ignitions=[],candidates=[],directional_vent_reactions=[]))
    for rid in states:
        scores[rid]['FGI_rollover']=common[rid]['fgi']['rollover']
        series[rid]['rollover_active']=common[rid]['fgi']['rollover']['active']
        summaries[rid]['rollover_first_active_s']=common[rid]['fgi']['rollover']['first_active_s']
        for label,key in {'FO':'fo','FGI':'fgi','BD':'backdraft'}.items():
            assert np.array_equal(scores[rid][label]['degree'],common[rid][key]['scores']['degree'])
    save('timeseries.json',series);save('condition-scores.json',scores)
    run_summary=json.loads((OUT/'execution-state.json').read_text(encoding='utf-8'))
    run_summary.update(native_normal_exit=True,requested_end_s=3600,last_csv_s=float(t[-1]),
                       endpoint_sample_missing=bool(t[-1]<3600),rerun=False)
    summary={'scenario':scenario,'run':run_summary,'rooms':summaries,'unchanged':unchanged,
             'door_jet_outside_peak_kW':peak(c['DJET_Outside']/1000),
             'threshold_time_basis':'first 5 s native sample; no interpolation',
             'input_parser_failures_before_integration':int((OUT/'input-parse-error').exists()),'integration_runs':1,
             'shared_evaluate_score_identity':True,
             'cut_first_observed_half_s':first(opening_states['CUT']['fraction'],.5),
             'cut_first_observed_full_s':first(opening_states['CUT']['fraction'],1.),
             'door_jet_by_individual_opening':None,
             'door_jet_scope':'native DJET receiving-room sum; gaps and cut not independently available',
             'scores_scope':'shared FO own plus received door jet revision; T/O2 and other indices unchanged; not occurrence probabilities',
             'FO_ROOM_note':'Shared FO fuel factor includes own HRR plus receiving-compartment DJET once; temperature and oxygen factors unchanged',
             'times':{str(at):{'sample_s':float(t[np.argmin(abs(t-at))]),**{k:float(a[np.argmin(abs(t-at))]) for k,a in states['ROOM'].items()}} for at in (780,1320,1500,2100)}}
    save('summary.json',summary)
    with (OUT/'room-timeseries.csv').open('w',encoding='utf-8-sig',newline='') as f:
        wr=csv.writer(f);wr.writerow(['time_s',*states['ROOM']])
        wr.writerows(zip(t,*states['ROOM'].values()))
    sys.path.insert(0,str(ROOT/'simulation/results/ui_C9_20261102/plot-deps'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors={'FO':'#df2d28','FGI':'#863bad','BD':'#b72666'}
    for zoom,name in ((False,f'{scenario}-timeseries.png'),(True,f'{scenario}-zoom.png')):
        fig,axs=plt.subplots(4,1,figsize=(13,10),sharex=True,layout='constrained')
        fan_label='ON 1500-1920 s' if fan_on else 'OFF'
        fig.suptitle(f'Wando {scenario} | stock CFAST | fan {fan_label} | condition indices, not event probabilities',fontsize=14)
        s=states['ROOM']
        axs[0].plot(t,s['T_upper_C'],color='#bc3c22');axs[0].set_ylabel('Upper T (C)')
        axs[1].plot(t,s['O2_upper_vol_percent'],color='#167ab5');axs[1].set_ylabel('Upper O2 (vol %)')
        axs[2].plot(t,s['fuel_upper_mass_fraction'],color='#715087');axs[2].set_ylabel('Unburned fuel\n(kg/kg)')
        for k,col in colors.items():axs[3].plot(t,s[k],label=k,color=col,lw=1.7)
        axs[3].axhline(70,color='#777777',ls=':',lw=1);axs[3].axhline(100,color='#555555',ls='--',lw=1)
        axs[3].set_ylabel('Condition index');axs[3].legend(loc='upper right',ncol=4)
        for ax in axs:
            ax.grid(alpha=.2);ax.set_xlim(1100 if zoom else 0,2400 if zoom else 3600)
            for at in (780,1320,1500,2100):ax.axvline(at,color='#3d5666',ls='--',alpha=.6,lw=1)
            if t[-1]<3600:ax.axvspan(t[-1],3600,color='#cccccc',alpha=.7)
        cut_label='1320 cut reference (NO CUT)' if scenario=='P4' else '1320 cut'
        for at,label in ((780,'780 entry'),(1320,cut_label),(1500,'1500 fan ON' if fan_on else '1500 fan reference (OFF)'),(2100,'2100 incident reference')):
            if not zoom or at>=1100:axs[0].text(at+6,.97,label,rotation=90,va='top',transform=axs[0].get_xaxis_transform(),fontsize=8)
        axs[3].set_xlabel('Time after ignition (s) | CSV 0-3595 s; last 5 s not extrapolated');fig.savefig(OUT/name,dpi=155);plt.close(fig)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','analyze'])
    globals()[p.parse_args().action]()
