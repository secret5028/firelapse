"""r6 gates: first A only; never sweep sensor positions or alter fixture values."""
import argparse,json,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'simulation'))
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.deck import make_deck
from pyrocast_cfbt.native import execute,load_result,digest
from pyrocast_cfbt.rule_sensor import gas_proxy_plate
OUT=ROOT/'simulation/results/room_rule_r6_20261025'
ENGINE=ROOT/'simulation/build/baseline/cfast-baseline.exe'
FIXTURE=ROOT/'fixtures/room_rule_benchmark_3room.json'

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')

def crossing(t,a,threshold=600):
    hits=np.flatnonzero(np.asarray(a)>=threshold)
    if not len(hits):return None
    i=int(hits[0]);return [float(t[max(0,i-1)]),float(t[i])]

def stage_a(analyze_only=False):
    model=normalize(json.loads(FIXTURE.read_text('utf-8')))
    source=next(g for g in model['fuel_groups'] if 'initial_time_s' in g)
    room=next(r for r in model['rooms'] if r['id']==source['room'])
    new=gas_proxy_plate(model,room,source,'T4B_R1')
    old={**new,'id':'T4_OLD_R1','xyz':[*source['position_m'][:2],room['origin_m'][2]+room['size_m'][2]-.2],
         'normal':[0,0,-1],'material':{**new['material'],'thickness_m':.001,'emissivity':.9},
         'basis':'r5 original plate above fire, measurement only'}
    old['solver_xyz']=old['xyz']
    deck=make_deck(model,[],[old,new]);folder=OUT/'A'
    assert 'DEVC_ID=' not in deck and '&CFBT' not in deck
    manifest={'stage':'A','measurement_only':True,'threshold_C':600.,'sensors':[old,new],
        'fixture_sha256':digest(FIXTURE),'engine_sha256':digest(ENGINE),
        'source_basis':['input_namelist.f90:438-445 (material values assigned without clamp)',
                        'input_namelist.f90:772 (DEVC thickness assigned)',
                        'initialization.f90:826-837 (target thickness and emissivity copied)',
                        'target.f90 (native plate conduction, convection and radiation retained)'],
        'parameter_adjustments':[],'wall_tie_rule':'lowest x/y farthest corner; nearest wall tie LEFT/RIGHT/FRONT/REAR'}
    if analyze_only:
        cached=json.loads((folder/'completed.json').read_text('utf-8'))
        native=load_result(folder,model['duration_s'],cached['run'])
    else:
        if (folder/'execution.json').exists():raise ValueError('Existing A measurement; use --analyze-only')
        save(folder/'rule_manifest.json',manifest)
        start=time.monotonic()
        try:
            native=execute(ENGINE,folder,deck,'',model['duration_s'],model['spread']['run_timeout_s'])
        except Exception as exc:
            save(folder/'execution.json',{'complete':False,'error':str(exc),'wall_seconds':time.monotonic()-start})
            raise
        save(folder/'execution.json',{'complete':True,'wall_seconds':time.monotonic()-start})
    t=native['zone']['Time'];gas=native['compartments']['ULT_1'];data=native['devices'];ids=native['devices_ids']
    values={sensor:next(data[key] for key,id_ in ids.items() if id_.strip()==sensor and key.startswith('TRGSURT_')) for sensor in ('T4_OLD_R1','T4B_R1')}
    stats={name:{'max_C':float(max(a)),'first_600C_bracket_s':crossing(t,a),
                'max_abs_same_time_difference_from_gas_C':float(max(abs(a-gas))),
                'difference_of_maxima_C':float(max(a)-max(gas))} for name,a in values.items()}
    for name,a in values.items():
        peak=int(np.argmax(a))
        columns={k:v for k,v in data.items() if ids[k].strip()==name}
        surrounding=next(v for k,v in columns.items() if k.startswith('TRGGAST_'))
        stats[name].update(peak_time_s=float(t[peak]),local_gas_max_C=float(max(surrounding)),
            local_gas_600C_bracket_s=crossing(t,surrounding),
            at_plate_peak={k:float(v[peak]) for k,v in columns.items() if k.startswith((
                'TRGGAST_','TRGFLXR_','B_TRGFLXR_','TRGFLXC_','B_TRGFLXC_','TRGFLXF_','B_TRGFLXF_'))})
    passed=abs(stats['T4B_R1']['difference_of_maxima_C'])<=50
    report={'stage':'A','complete':True,'passed':passed,'criterion':'absolute difference of maxima <=50 C, as r6 prescribes; same-time deviation also reported',
            'R1_upper_max_C':float(max(gas)),'R1_upper_600C_bracket_s':crossing(t,gas),
            'sensors':stats,'native_wall_seconds':native['run']['wall_seconds'],'manifest':manifest,
            'B_started':False,'C_started':False,'sensor_parameter_sweep':False,
            '600C_time_difference':'not defined if either series does not reach 600 C; no fictitious zero difference'}
    report['source_findings']={'target_convection':'target.f90:329-335 calls get_gas_temp_and_velocity for both internal faces',
        'local_gas':'fire.f90:889-957 starts with layer temperature then takes max(layer, plume, ceiling jet)',
        'radiation':'target.f90:342-379 multiplies absorbed and emitted radiation by material emissivity; flipping normal retains rear-face irradiation',
        'conclusion':'Low emissivity does not make a plate a layer-average gas sensor: its convective driver includes local plume/ceiling-jet temperature.',
        'metadata_note':'Inherited material absorptivity/ignition_C fields are not written to MATL/DEVC; native uses EMISSIVITY=0.05 and THICKNESS=0.0001 exactly.'}
    save(folder/'analysis.json',report);print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--analyze-only',action='store_true');a=p.parse_args()
    stage_a(a.analyze_only)
