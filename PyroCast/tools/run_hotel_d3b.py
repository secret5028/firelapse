"""D-3b: one serial hotel screening batch; production rules/inputs are read only.

The factory-only approved-use map is intentionally NOT used. D-3 automatic
classifications supply the existing v8 formulas with the shared fuel table.
No retries, parameter sweeps, graph repairs, UI publication or native runs.
"""
import os
for _key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_key] = '1'
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'simulation'), str(ROOT/'simulation/deps'), str(ROOT/'tools')]
import numpy as np
from pyrocast_cfbt.cad import adapt
from pyrocast_cfbt.model import normalize
from pyrocast_lite import screening_v7 as v7
from pyrocast_lite.screening_v8_approved import origin_budgets, scenario, summarize
from pyrocast_lite.adapter import prepare
from pyrocast_lite.runner import run, results
from export_ui_attention import summarize as attention
from run_lite_l1 import save

OUT = ROOT/'simulation/results/hotel_d3b_20261103'
REVIEW = ROOT/'reviews/D3b-20261103'
PARAMS = dict(remove_cumulative_state=True, smooth_state_bounds=True,
              upper_combustion_enabled=True, door_jet_enabled=True)
STATES = ('open_except_confirmed', 'closed')


def read(path):
    return json.loads(path.read_text('utf-8'))


def hashes():
    paths = [ROOT/'data/parkmarine-hotel/building.json',
             ROOT/'data/parkmarine-hotel/graph-report.json',
             ROOT/'config/building-rules.json']
    paths += list((ROOT/'simulation/pyrocast_lite').glob('*.py'))
    paths += list((ROOT/'simulation/pyrocast_lite').glob('*.json'))
    paths += list((ROOT/'simulation/pyrocast_cfbt').glob('*.py'))
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths)}


def inputs():
    raw = adapt(ROOT, dict(building_path=str(ROOT/'data/parkmarine-hotel/building.json'),
                           fire_floor='5F', scope_floor='5F', fire_room='R0', duration_s=3600))
    table = read(ROOT/'simulation/pyrocast_lite/fire_load_table.json')['classes']
    classes = {r['id']: r for r in read(ROOT/'data/parkmarine-hotel/graph-report.json')['rooms']
               if r['floor'] == '5F'}
    records = {}
    for room in raw['rooms']:
        rid = room['id']; entry = classes[rid]; cls = table[entry['usage_class']]
        # Preserve the existing dedicated-core exclusion and its low-fuel proxy.
        core = bool(room['core_kind']); area = room['area_m2']
        load = room['fuel_default']['load_MJ_m2'] if core else cls['mean']
        hrrpua = room['fuel_default']['hrrpua_kW_m2'] if core else cls['rhrf']
        records[rid] = dict(room=rid, label=cls['label'], usage_class=entry['usage_class'],
                            classification_basis=entry['usage_evidence'], labels=entry['labels'],
                            area_m2=area, load_MJ_m2=load, hrrpua_kW_m2=hrrpua,
                            coverage=.5, core_preserved=core, automatic=True,
                            value_basis='D3 automatic class / fire_load_table mean,rhrf; existing core exception')
        if core:
            continue
        room['fuel_default'].update(usage='passage' if entry['usage_class']=='transport' else entry['usage_class'],
                                     load_MJ_m2=load, hrrpua_kW_m2=hrrpua,
                                     occupancy_fraction=.5, basis=records[rid]['value_basis'])
        for group in raw['fuel_groups']:
            if group['room'] != rid:
                continue
            group.update(energy_MJ=area*load, hrrpua_kW_m2=hrrpua,
                         fuel_area_m2=.5*area, coverage_fraction=.5)
            for unit in group.get('fuel_units', []):
                unit['energy_MJ'] = group['energy_MJ']*unit['budget_fraction']
    raw = normalize(raw)
    # Only a metadata argument to the pure budget function; not an approved map.
    budget_input = {**raw, 'approved_input': {'room_uses': records}}
    budgets = origin_budgets(budget_input)
    adjusted = deepcopy(raw)
    for group in adjusted['fuel_groups']:
        group['peak_kW'] = budgets[group['room']]['Q_origin_peak_kW']
    scored = v7.score(adjusted, 3)
    scored['classified_model']['fuel_groups'] = deepcopy(raw['fuel_groups'])
    scored.update(origin_budgets=budgets, automatic_room_uses=records,
                  revision='D3b_v8_formulas_automatic_D3_classes')
    for row in scored['ranked'] + scored['excluded']:
        row['origin_budget'] = budgets[row['room']]
    scored['settings']['ranking_order'] = ['burning_rooms_desc', 'attention_rooms_desc', 'first_FO_s_asc']
    scored['limits'] += ['D3 automatic classifications are uncorrected, not a surveyed fuel inventory',
                         'dedicated cores excluded by existing adapter; other mislabeled/unconnected rooms retained',
                         'standby item_peak remains CAD loader value; only selected origin uses v8 fuel-based peak',
                         'whole 5F only; other hotel floors and vertical propagation not simulated']
    assert len(raw['rooms']) == 23 and len(raw['openings']) == 49
    return raw, scored


def order(row):
    return (-row['burning_room_count'], -row['attention_room_count'],
            row['first_FO_s'] if row['first_FO_s'] is not None else float('inf'))


def batch():
    if (OUT/'started.json').exists():
        raise RuntimeError('D-3b already attempted: no automatic rerun')
    before = hashes(); start = time.perf_counter()
    raw, scored = inputs()
    save(OUT/'source-scenario.json', raw)
    score_data = {k:v for k,v in scored.items() if k!='classified_model'}
    save(OUT/'score.json', score_data); save(REVIEW/'score.json', score_data)
    save(OUT/'started.json', dict(duration_s=3600, output_s=10, scenario_count=6, workers=1,
                                 budget_s_per_case=1200, method='BDF', retry=False, parameters=PARAMS,
                                 sha256=before, current_rank_order=scored['settings']['ranking_order']))
    cases = []
    for candidate in scored['ranked'][:3]:
        for state in STATES:
            rid = candidate['room']; folder = OUT/rid/state
            data = scenario(scored, rid, state); data['cad']['fire_key'] = rid
            data['screening_source']['revision'] = scored['revision']
            save(folder/'input.json', data)
            save(OUT/'progress.json', dict(completed=len(cases), current=[rid,state], total=6))
            print('START', len(cases)+1, rid, state, flush=True)
            begin = time.perf_counter(); model = None
            try:
                model, manifest = prepare(data, PARAMS); prep = time.perf_counter()-begin
                save(folder/'rule_manifest.json', manifest); save(folder/'contract.json', model.contract)
                run(model, 3600, 10, 1200, method='BDF')
                result = results(model)
                save(folder/'result.json', result)
                np.savez_compressed(folder/'state.npz', t=model.sol.t, y=model.sol.y)
                summary = summarize(model, result)
                summary.update(attention(result))
                summary['burning_rooms'] = sorted(r for r,v in summary['rooms'].items() if v['burning'])
                summary.update(preprocess_s=prep, integration_s=model.integration['wall_seconds'],
                               postprocess_s=result['postprocess_wall_seconds'], failure=model.integration['failure'],
                               cell_count=model.N, events=result.get('events'))
            except Exception as exc:
                summary = dict(complete=False, failure=f'{type(exc).__name__}: {exc}',
                               integration=model.integration if model is not None and hasattr(model,'integration') else None)
            summary.update(room=rid, name=candidate['name'], rank1=candidate['rank1'], score=candidate['score'],
                           state=state, total_s=time.perf_counter()-begin)
            save(folder/'summary.json', summary); cases.append(summary)
            save(REVIEW/'cases.json', cases)
            print('END', json.dumps(summary, ensure_ascii=False), flush=True)
    rows = []
    for candidate in scored['ranked'][:3]:
        pair = [c for c in cases if c['room']==candidate['room']]
        complete = all(c['complete'] for c in pair)
        worst = min(pair, key=order) if complete else None
        row = dict(room=candidate['room'], rank1=candidate['rank1'], score=candidate['score'], complete=complete,
                   total_s=sum(c['total_s'] for c in pair), worst_state=worst['state'] if worst else None)
        if worst:
            row.update({k:worst[k] for k in ('burning_room_count','burning_rooms','attention_room_count','first_FO_s')})
            row['tied_states'] = [c['state'] for c in pair if order(c)==order(worst)]
        rows.append(row)
    good = sorted((r for r in rows if r['complete']), key=lambda r:(order(r),r['room']))
    last = None; rank = 0
    for i,row in enumerate(good,1):
        if order(row)!=last: rank=i
        row['rank2']=rank; last=order(row)
    output = dict(rows=good+[r for r in rows if not r['complete']], cases=cases,
                  complete_scenarios=sum(c['complete'] for c in cases), attempted_scenarios=len(cases),
                  total_wall_s=time.perf_counter()-start, code_and_input_unchanged=hashes()==before,
                  new_native_runs=0, mc_runs=0, geometry_repairs=0, automatic_retries=0)
    save(OUT/'comparison.json', output); save(REVIEW/'comparison.json', output)
    save(OUT/'progress.json', dict(completed=6, total=6, state='finished'))
    print('BATCH FINISHED', output['total_wall_s'], flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--prepare-only', action='store_true')
    args=parser.parse_args()
    if args.prepare_only:
        _,scored=inputs()
        print(json.dumps([dict(room=r['room'], rank=r['rank1'], score=r['score'], Q=r['origin_budget']['Q_origin_peak_kW'])
                          for r in scored['ranked'][:3]], ensure_ascii=False))
    else:
        batch()
