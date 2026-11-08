"""Map stock CFAST CSV to the viewer; geometry only is borrowed from its MC source."""
from copy import deepcopy
import numpy as np
from pyrocast_cfbt.native import read_native_csv, digest
from pyrocast_cfbt.conditions import screening_scores, screening_lfl, fo_required_hrr, rollover_states, _finite
from pyrocast_cfbt.native_criteria import native_interface


def smoke_optics(table, ids, units, room, index):
    def layer(key):
        if key not in table:
            return [None]*len(table['Time'])
        if ids[key]!=room:
            raise ValueError('Native smoke room identity mismatch')
        if units[key]=='mg/m^3':
            # Inverse of the stock validation CSV conversion in outputspreadsheet.f90.
            return table[key]/264.6903
        if units[key]=='1/m':
            return table[key]
        raise ValueError('Native smoke density unit mismatch')
    return layer(f'ULOD_{index}'),layer(f'LLOD_{index}')


def restore_smoke(playback, folder):
    path=folder/'case_compartments.csv'
    if not path.is_file():
        return
    table,ids,units=read_native_csv(path,float(playback['time_s'][-1]))
    if not np.array_equal(table['Time'],playback['time_s']):
        raise ValueError('Native smoke timestamp mismatch')
    for key,rid in ids.items():
        if key.startswith('ULOD_') and rid in playback['solvers']:
            upper,lower=smoke_optics(table,ids,units,rid,int(key.split('_')[-1]))
            playback['solvers'][rid].update(ODu=_finite(upper),ODl=_finite(lower))
    playback['native_mapping']='fixed-r8-native-v2'


def native_geometry(model, template):
    """Union original CAD cell polygons; never borrow an old thermal series."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    mapping=model.get('native_compartments',{}).get('cell_to_room')
    if not mapping:return deepcopy(template)
    if {r['solver_id'] for r in template['rooms']}=={r['id'] for r in model['rooms']}:
        return deepcopy(template)
    if set(mapping)!=set(r['solver_id'] for r in template['rooms']):
        raise ValueError('Native source cells differ from MC geometry')
    data=deepcopy(template);rows=[]
    for room in model['rooms']:
        rid=room['id'];cells=[r for r in template['rooms'] if mapping[r['solver_id']]==rid]
        shape=unary_union([Polygon(p['o'],p.get('h',[])) for r in cells for p in r['cad_polys']])
        parts=list(shape.geoms) if hasattr(shape,'geoms') else [shape]
        if any(p.geom_type!='Polygon' for p in parts) or shape.is_empty:
            raise ValueError('Invalid physical room geometry: '+rid)
        center=shape.representative_point();row=deepcopy(cells[0])
        row.update(key=rid,solver_id=rid,original_room=rid,cad_room=rid.removeprefix('CAD_'+row['cad_floor']+'_'),
                   cad_center_m=[center.x,center.y],cad_polys=[dict(o=list(p.exterior.coords),h=[list(h.coords) for h in p.interiors]) for p in parts],
                   area_m2=float(shape.area),height_m=room['size_m'][2])
        rows.append(row)
    data['rooms']=rows;data['fire_key']=mapping[data['fire_key']]
    for f in data.get('fires',[]):
        f['solver_id']=mapping.get(f.get('solver_id',f['cad_key']),f.get('solver_id',f['cad_key']))
        f['cad_key']=mapping.get(f['cad_key'],f['cad_key'])
    for unit in data.get('fuel_symbols',[]):unit['room']=mapping.get(unit['room'],unit['room'])
    return data


def package(model, native, template, folder):
    template=native_geometry(model,template)
    c = native['compartments']; z = native['zone']; ids = native['compartments_ids']
    units = native['compartments_units']; t = c['Time']; n = len(t)
    masses, _, _ = read_native_csv(folder/'case_masses.csv', float(t[-1]))
    if not np.array_equal(t, masses['Time']):
        raise ValueError('Native mass timestamp mismatch')
    byid = {r['id']: r for r in model['rooms']}
    geometry = {r['solver_id']: r for r in template['rooms']}
    if set(byid) != set(geometry):
        raise ValueError('CFAST/MC cell geometry differs; refusing to reuse geometry')
    v = native['native_vents']; vids = native['native_vents_ids']
    opening_states = {}
    for op in model['openings']:
        k = next(k for k in v if k.startswith(('WF_','CFF_')) and vids[k] == op['id'])
        if not np.allclose(v[k], op['schedule'][0][1], atol=1e-8):
            raise ValueError('Native fixed opening fraction changed')
        opening_states[op['id']] = dict(fraction=v[k])
    def col(table, key):
        return table[key] if key in table else np.full(n, np.nan)
    solvers = {}; fires = []; criteria = model['criteria']; gas = model['gas']
    from pyrocast_cfbt.floor_flux import read_floor_flux
    floor_flux=read_floor_flux(model,native)
    for i, room in enumerate(model['rooms'], 1):
        rid = room['id']
        if ids[f'ULT_{i}'] != rid or units[f'ULO2_{i}'] != 'mol_frac':
            raise ValueError('Native room or oxygen unit mismatch')
        mass = sum(masses[f'ULM{s}_{i}'] for s in ('N2','O2','CO2','CO','HCN','HCL','TUHC','H2O','OD'))
        fuel = np.divide(masses[f'ULMTUHC_{i}'], mass, out=np.full(n, np.nan), where=mass>0)
        q = np.zeros(n)
        for j, group in enumerate(model['fuel_groups'], 1):
            if group['room'] != rid: continue
            if ids[f'HRR_{j}'].strip() != 'F_'+group['id'] or units[f'HRR_{j}'] != 'W':
                raise ValueError('Native fire identity or HRR unit mismatch')
            actual = c[f'HRR_{j}']/1000; q += actual
            hits = np.flatnonzero(actual>0)
            if not len(hits): continue
            meta = geometry[rid]
            # Preserve the existing CAD fire placement, never old thermal values.
            prior = next((f for f in template['fires'] if f.get('id') == group['id']), None)
            position = prior['position_m'] if prior else [*meta['cad_center_m'], meta['z_m']]
            fires.append(dict(id=group['id'], cad_key=rid, solver_id=rid, cad_floor=meta['cad_floor'],
                position_m=position, time_s=float(t[hits[0]]),
                kind='initial' if 'initial_time_s' in group else 'additional', Q_kW=actual,
                visuals=dict(base_height_m=0., flame_height_m=col(c, f'FLHGT_{j}'),
                    area_m2=col(z, f'FAREA_{j}'), radiative_fraction=group.get('radiative_fraction', .35),
                    basis='stock CFAST FLHGT/FAREA; CAD position from matching cell')))
        Tu = c[f'ULT_{i}']; Ou = c[f'ULO2_{i}']; Ol = col(c, f'LLO2_{i}')
        jet = c[f'DJET_{i}']/1000
        required = fo_required_hrr(model, dict(time_s=t, opening_states=opening_states), room, t)
        from pyrocast_cfbt.criteria import evaluate_cell
        parent=room.get('parent_room',rid)
        sibling_ids={r['id'] for r in model['rooms'] if r.get('parent_room',r['id'])==parent}
        parent_heat=sum((c[f'HRR_{j}']/1000 for j,g in enumerate(model['fuel_groups'],1) if g['room'] in sibling_ids),np.zeros(n))
        heights=[col(c,f'FLHGT_{j}') for j,g in enumerate(model['fuel_groups'],1) if g['room']==rid]
        interface=native_interface(c,room,i)
        conditions=evaluate_cell(model,room,t,Tu,interface,Ou*100,fuel,q,jet_kW=jet,
            own_fire=parent_heat,flux_kW_m2=floor_flux[rid]['values'],flame_height_m=np.max(heights,axis=0) if heights else None)
        conditions['FO']['diagnostics']={'Thomas_required_kW':required,'label':'셀·대공간에서는 무효인 진단값'}
        conditions['FO']['floor_flux']={k:v for k,v in floor_flux[rid].items() if k!='values'}
        conditions['FGI']['rollover']=conditions.pop('rollover')
        upper_od,lower_od=smoke_optics(c,ids,units,rid,i)
        solvers[rid] = dict(Tu=Tu, Tl=col(c,f'LLT_{i}'), h=interface, Ou=Ou, Ol=Ol,
            Fu=fuel, ODu=upper_od, ODl=lower_od, height_m=room['size_m'][2],floor_incident_kW_m2=floor_flux[rid]['values'],
            Qsolid_kW=q, Qvent_kW=jet, Qbulk_kW=[None]*n,
            conditions=conditions)
    rollover = rollover_states(model, t, {r:s['conditions']['FGI'] for r,s in solvers.items()},
        {r:s['Qsolid_kW'] for r,s in solvers.items()}, {r:s['Qvent_kW'] for r,s in solvers.items()},
        dict(time_s=t, opening_states=opening_states))
    for r, state in rollover.items(): solvers[r]['conditions']['FGI']['remote_ignition_condition'] = state
    playback = _finite(dict(schema='pyrocast-cad-playback-1', engine_kind='cfast_native',
        native_mapping='fixed-r8-native-v3', condition_version=__import__('pyrocast_cfbt.criteria',fromlist=['CONDITION_VERSION']).CONDITION_VERSION, complete=True,
        building_sha256=model['cad']['building_sha256'], time_s=t, fire_key=template['fire_key'],
        native_compartments=model.get('native_compartments'),
        basement_pressure=model.get('basement_pressure'),
        rooms=deepcopy(template['rooms']), fuel_symbols=deepcopy(template.get('fuel_symbols', [])),
        solvers=solvers, fires=fires, events=[], fuel_units=[], opening_states=opening_states,
        limits=model.get('limits',[])+['순정 CFAST 1회 · MC 저장 개폐 상태 사용. 착화 판정은 r8 판 센서.',
                '문 분출은 수신 실 합계. 개구부별 분출 화염·상층 반응 발열은 미평가.',
                'FO 복사열은 바닥 등면적 측정점의 평균 입사 복사열입니다. 국소 최대값이 아니며 격자 근사입니다.',
                '조건 충족 지수이며 발생 확률 아님.'],
        provenance=dict(engine_sha256=native['run']['engine_sha256'], final_input_sha256=digest(folder/'case.in'),
            mapping='stock compartments CSV: C, mol_frac, W/1000, OD converted to 1/m, TUHC/upper gas mass')))

    from pyrocast_cfbt.validation import validate_native, protect_playback
    protect_playback(playback,validate_native(native,model,folder))
    return playback
