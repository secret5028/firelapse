"""Native conditional-VENT integration, deliberately small test geometry."""
from pathlib import Path
import sys,json
from copy import deepcopy
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.deck import make_deck,gas_sidecar,candidates
from pyrocast_cfbt.native import execute
from pyrocast_cfbt.openings import histories,window_targets,device_series


def main():
    out=ROOT/'results/window_r8_20261022/native_checks';engine=ROOT/'build/ignition/cfbt/cfast-cfbt.exe'
    raw={'duration_s':300,'output_step_s':5.,'max_time_step_s':1.,'gas':{'enabled':False},
        'spread':{'enabled':False},'window_breakage':{'enabled':True,'threshold':450.,'post_fraction':.8},
        'rooms':[{'id':'R1','origin_m':[0,0,0],'size_m':[4,4,3]}],
        'openings':[{'id':'Door','a':'R1','b':'OUTSIDE','face':'FRONT','offset_m':1.,'width_m':1.,'top_m':2.1,'schedule':[[0,1]]},
                    {'id':'Window','kind':'window','a':'R1','b':'OUTSIDE','face':'REAR','offset_m':1.,'width_m':2.,'bottom_m':1.,'top_m':2.8,'schedule':[[0,0]]}],
        'fuel_groups':[{'id':'fuel','room':'R1','initial_time_s':0,'position_m':[2,2,.02],
            'energy_MJ':1500,'heat_of_combustion_kJ_kg':18100,'growth_kW_s2':2.,'peak_kW':3000,'hrrpua_kW_m2':500}]}
    records=[]
    for name,threshold,f0,after in [('default450',450.,0.,.8),('partial',100.,.5,.8),('no_effect',450.,.5,.5),('flux',5.,0.,.8)]:
        r=deepcopy(raw);r['window_breakage'].update(threshold=threshold,post_fraction=after,
            criterion='FLUX' if name=='flux' else 'TEMPERATURE');r['openings'][1]['schedule']=[[0,f0]]
        m=normalize(r);native=execute(engine,out/name,make_deck(m,[],[]),gas_sidecar(m),300,90)
        state=histories(m,native)['Window'];values=np.asarray(state['fraction'])
        assert np.all(np.diff(values)>=-1e-10)
        assert values[0]==f0 and values[-1]<=after+1e-8
        if name!='no_effect':
            assert state['changed'],name
            assert abs(values[-1]-after)<1e-8
        else:assert not state['changed'] and not window_targets(m)
        records.append({'case':name,'wall_s':native['run']['wall_seconds'],'initial':f0,'final':float(values[-1]),
            'observed_interval_s':state['observed_interval_s'],'max_surface_C':max(state.get('surface_C',[0]))})
    # Input and output identity: appending passive window devices must not change
    # which native surface is used by each existing fuel candidate.
    r=deepcopy(raw);r['fuel_groups'].append({'id':'reserve','room':'R1','position_m':[1,1,.02],
        'energy_MJ':100,'heat_of_combustion_kJ_kg':18100,'growth_kW_s2':.01,'peak_kW':100,'hrrpua_kW_m2':150})
    m=normalize(r);targets=candidates(m)
    native=execute(engine,out/'with_fuel_devices',make_deck(m,[],targets),gas_sidecar(m),300,90)
    for i,t in enumerate(targets,1):
        np.testing.assert_array_equal(device_series(native,t['id'],'TRGFLXI'),native['devices']['TRGFLXI_'+str(i)])
    report={'passed':True,'cases':records,'fuel_devices_preserved':len(targets),
        'engine_modified':False,'purpose':'native feature integration; not validation of real glass fallout'}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
