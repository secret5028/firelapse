"""Reproduce a saved lite input without changing it or overwriting its results."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'simulation'), str(ROOT / 'simulation/deps'), str(ROOT / 'tools')]
import numpy as np
from pyrocast_lite.adapter import prepare
from pyrocast_lite.runner import run, results
from pyrocast_lite.visualization import package


def read(path):
    return json.loads(path.read_text('utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2), 'utf-8')


def execute(source, output):
    raw = read(source / 'input.json')
    previous = read(source / 'result.json')
    shared = {'T_in','T_out','kpc','eps','chi_r','dHc','door_leak','win_leak','Cd',
              'oxygen_limit_model','native_lower_oxygen_limit_mass'}
    model, manifest = prepare(raw, {k:v for k,v in previous['physical_parameters'].items() if k not in shared})
    assert model.P == previous['physical_parameters'], 'Physical input drift'
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'result.json').exists():
        raise ValueError('Never overwrite a completed diagnostic')
    run(model, float(previous['t'][-1]), 10, 1200)
    result = results(model)
    write(output / 'result.json', result)
    write(output / 'rule_manifest.json', manifest)
    np.savez_compressed(output / 'states.npz', t=model.sol.t, y=model.sol.y)
    write(output / 'playback.json', package(model, result, raw, 'Hotel plume oxygen diagnostic'))
    trace = []
    import inspect
    from pyrocast_lite.core import Model
    source_lines, first_line = inspect.getsourcelines(Model.rhs)
    trace_line = first_line + next(i for i,line in enumerate(source_lines) if 'mp = Qp / heat_comb' in line)
    # Read each fire's locals after combustion, never alter the equations.
    def observe(frame, event, arg):
        if event == 'line' and frame.f_code == Model.rhs.__code__ and frame.f_lineno == trace_line:
            local = frame.f_locals
            trace.append({key: float(local[key]) for key in ('t', 'me', 'meu', 'Hf', 'Q', 'Qf', 'Qp', 'fire_height') if key in local})
            if trace and 'i' in local:
                i = local['i']
                trace[-1].update(cell=model.nodes[i]['id'], interface_m=float(local['hl'][i]),
                    lower_inflow_kg_s=float(local['inl'][i]), lower_O2_mass=float(local['Yo'][1][i]),
                    upper_O2_mass=float(local['Yo'][0][i]))
        return observe
    for t in (300, 1000, 2080, 3000):
        j = int(np.argmin(abs(model.sol.t-t)))
        sys.settrace(observe)
        try:
            model.rhs(float(model.sol.t[j]), model.sol.y[:, j], diag=True)
        finally:
            sys.settrace(None)
    rows = []
    for room in result['rooms']:
        conditions = result['shared_conditions']['rooms'][room['id']]
        row = {'room': room['id'], 'max_unburned_fraction': max(room['Yf_u']),
               'actual_peak_kW': max(room['actual_HRR_kW']), 'max_upper_C': max(room['T_u']),
               'upper_peak_kW': max(room['upper_HRR_kW']), 'jet_peak_kW': max(room['door_jet_HRR_kW'])}
        for phenomenon in ('FO', 'FGI', 'backdraft'):
            values = conditions[phenomenon]['scores']['degree']
            peak = max((v for v in values if v is not None), default=None)
            row[phenomenon] = {'peak': None if peak is None else 100*peak,
                'peak_s': None if peak is None else result['t'][values.index(peak)]}
        rows.append(row)
    for row in rows:
        i = model.rmap[row['room']]
        row['max_unburned_fraction_raw'] = float(np.maximum(model.sol.y[6*model.N+i],0).max())
        row['raw_unburned_min'] = float(model.sol.y[6*model.N+i].min())
    evidence = {'source': str(source), 'input_sha256': hashlib.sha256((source/'input.json').read_bytes()).hexdigest(),
        'core_sha256': hashlib.sha256((ROOT/'simulation/pyrocast_lite/core.py').read_bytes()).hexdigest(),
        'integration': result['integration'], 'rooms': rows, 'trace_sources': trace}
    write(output / 'diagnosis.json', evidence)
    print(json.dumps({'complete': result['ok'], 'seconds': result['integration']['wall_seconds'],
        'origin': next(r for r in rows if r['room']=='CAD_5F_R16')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    execute(args.source, args.output)
