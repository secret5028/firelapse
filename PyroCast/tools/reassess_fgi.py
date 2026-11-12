"""Re-evaluate FGI in saved CFAST results with the layer-potential definition (origin and burning rooms included).

Only the FGI records and what is derived from them change. Temperatures, oxygen, fuel, heat release, pressure,
FO, BD and the validity verdict are read and left as stored; CFAST is not run. Each result keeps the hashes of the
files it was reassessed from, so the earlier evaluation stays identifiable.

    python tools/reassess_fgi.py <results folder> --source "<where the stored results came from>"
"""
import argparse, copy, hashlib, json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'simulation')]
from pyrocast_cfbt.criteria import BASE_REVISION, CONDITION_VERSION, FGI_REVISION, evaluate_cell, settings

DERIVED = ('smoke_caution_rooms', 'smoke_risk_rooms', 'smoke_risk_room_count', 'smoke_caution_room_count', 'attention_room_count', 'phenomena')
FILES = ('playback.json', 'result.json', 'summary.json', 'index-summary.json')


def read(path): return json.loads(Path(path).read_text('utf-8'))
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def numbers(values): return np.array([np.nan if v is None else v for v in values], dtype=float)


def potential(record, deep, cool, t):
    """The stored fuel and oxygen factors under the new gate; same arithmetic as criteria.evaluate_cell."""
    factors = record['scores']['factors']; proximity = np.minimum(numbers(factors['fuel']), numbers(factors['oxygen']))
    gate = deep & cool; known = deep & np.isfinite(proximity); value = np.where(gate & known, proximity, np.nan); met = gate & known & (proximity >= 1)
    degree = [float(x) if np.isfinite(x) else None for x in value]
    flags = [bool(x) if d and (not g or k) else None for x, d, g, k in zip(met, deep, gate, known)]; hits = np.flatnonzero(met)
    new = copy.deepcopy(record)
    new.update(revision=FGI_REVISION, gate=[bool(g) if d else None for g, d in zip(gate, deep)], proximity=degree, occurred=[None]*len(t), all_met=flags,
               first_met_s=float(t[hits[0]]) if len(hits) else None, occurrence_assessed=False,
               applicability='all rooms including origin; gas mixture potential, not observed ignition')
    new['scores'].update(degree=list(degree), all_met=list(flags))
    return new


def remote_ignition(state, degree, t):
    """conditions.rollover_states for a new score series. The stored ignition flags are kept: the door-jet heat
    behind them is rounded away in the display playback and cannot be rebuilt from it."""
    active = [False if state['excluded_origin'] or not lit else None if v is None else bool(v*100 >= state['threshold']) for lit, v in zip(state['ignition'], degree)]
    hits = [i for i, v in enumerate(active) if v is True]
    return {**state, 'active': active, 'first_active_s': float(t[hits[0]]) if hits else None}


def reassess(folder, source):
    from cfast_calculation import report
    from display_playback import display_copy
    from export_ui_attention import result_index
    from result_catalog import atomic_json
    folder = Path(folder); playback = read(folder/'playback.json')
    if playback.get('condition_version') == CONDITION_VERSION: return dict(case=folder.name, state='already current')
    result = read(folder/'result.json'); summary = read(folder/'summary.json'); model = read(folder/'scenario.json'); evidence = read(folder/'cfast-evidence.json')
    assert playback['engine_kind'] == 'cfast_native' and playback['condition_version'] == result['condition_version'] == BASE_REVISION, folder.name
    before = {name: digest(folder/name) for name in FILES}
    assert all(evidence['files'][name] == before[name] for name in FILES), 'stored result does not match its evidence: '+folder.name
    t = np.asarray(playback['time_s']); limit = settings(model)['gas_ignition_C']; rooms = {r['id']: r for r in model['rooms']}
    stored = result['shared_conditions']['rooms']; solvers = playback['solvers']; untouched = copy.deepcopy(playback)

    # The stored summary and remote-ignition states must be reproducible from the stored data before anything is replaced.
    def summarize(): return report({**playback, 'solvers': {r: {**s, 'conditions': stored[r]} for r, s in solvers.items()}}, model)[1]
    old_summary = summarize()
    assert all(old_summary[k] == summary[k] for k in DERIVED), 'stored summary is not reproducible: '+folder.name
    for rid in solvers:
        old = stored[rid]['FGI']
        assert remote_ignition(old['remote_ignition_condition'], old['scores']['degree'], t) == old['remote_ignition_condition'], 'stored remote-ignition state is not reproducible: '+rid

    worst = 0.; added = 0
    for rid, s in solvers.items():
        old = stored[rid]['FGI']; temp = numbers(s['Tu']); deep = np.array([g is not None for g in old['gate']])
        assert not np.any(np.abs(temp-limit) < 1e-4), 'temperature sample on the ignition limit: '+rid
        new = potential(old, deep, temp < limit, t)
        # Scores that existed stay exactly as they were; the evaluator on the stored series must agree on the rest.
        check = evaluate_cell(model, rooms[rid], t, s['Tu'], s['h'], numbers(s['Ou'])*100, s['Fu'], s['Qsolid_kW'], jet_kW=s['Qvent_kW'])['FGI']
        assert new['gate'] == check['gate'], 'gate differs from the evaluator: '+rid
        for a, b, c in zip(old['scores']['degree'], new['scores']['degree'], check['scores']['degree']):
            assert a is None or a == b, 'existing score changed: '+rid
            assert (b is None) == (c is None), 'evaluated steps differ from the evaluator: '+rid
            if b is not None: worst = max(worst, abs(b-c)); added += a is None
        stored[rid]['FGI'] = new
    assert worst <= 2e-4, worst  # display rounding of the stored series (5 decimals)
    for rid in solvers:
        new = stored[rid]['FGI']; new['remote_ignition_condition'] = remote_ignition(new['remote_ignition_condition'], new['scores']['degree'], t)
        solvers[rid]['conditions']['FGI'] = copy.deepcopy(new)
    note = dict(revision=FGI_REVISION, previous_condition_version=BASE_REVISION, source=source, source_files=before, native_recomputed=False,
                thresholds_unchanged=True, change='FGI is evaluated in every room with a smoke layer below the gas-ignition temperature limit, the origin and burning rooms included; ignition is not assessed',
                evaluator_sha256=digest(ROOT/'simulation/pyrocast_cfbt/criteria.py'))
    playback['condition_version'] = result['condition_version'] = CONDITION_VERSION; playback['fgi_reassessment'] = result['fgi_reassessment'] = note
    shown = display_copy(playback)
    for value in (shown, untouched):  # everything except the FGI records is byte-for-byte what was stored
        for s in value['solvers'].values(): s['conditions'].pop('FGI')
        value.pop('condition_version'); value.pop('fgi_reassessment', None)
    assert json.dumps(shown, sort_keys=True) == json.dumps(untouched, sort_keys=True), 'non-FGI playback data changed: '+folder.name
    new_summary = summarize()
    assert all(new_summary['phenomena'][k] == summary['phenomena'][k] for k in ('FO', 'backdraft'))
    summary.update({k: new_summary[k] for k in DERIVED}); summary['condition_version'] = CONDITION_VERSION; summary['fgi_reassessment'] = note
    atomic_json(folder/'playback.json', display_copy(playback), compact=True)
    atomic_json(folder/'result.json', result); atomic_json(folder/'summary.json', summary)
    result_index(folder/'result.json')
    evidence['files'].update({name: digest(folder/name) for name in FILES}); evidence['fgi_reassessment'] = dict(revision=FGI_REVISION, source_files=before)
    atomic_json(folder/'cfast-evidence.json', evidence)
    fgi = summary['phenomena']['FGI']
    return dict(case=folder.name, state='reassessed', label=playback.get('label'), rooms=len(solvers), newly_scored_steps=int(added), evaluator_max_difference=worst,
                score_max=fgi['score_max'], previous_score_max=old_summary['phenomena']['FGI']['score_max'], first_s=fgi['first_s'], ever_room_count=fgi['ever_room_count'])


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('results', type=Path); parser.add_argument('--source', required=True); args = parser.parse_args()
    rows = [reassess(p.parent, args.source) for p in sorted(args.results.rglob('playback.json')) if (p.parent/'cfast-evidence.json').is_file()]
    print(json.dumps(rows, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
