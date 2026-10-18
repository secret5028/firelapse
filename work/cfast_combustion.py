"""Postprocess native CFAST output; never changes physical input or solver results."""
import csv
import math
from pathlib import Path


def sustained_intervals(times, flags, hold=10):
    intervals = []
    start = None
    for i in range(len(times) + 1):
        if i < len(times) and flags[i]:
            if start is None:
                start = i
        elif start is not None:
            last = i - 1
            if times[last] - times[start] >= hold:
                intervals.append(dict(onset=times[start], confirmed=times[start]+hold,
                                      end=times[i] if i < len(times) else None))
            start = None
    return intervals


def add_combustion(result, directory, building, stem='multifloor'):
    """HRR_E is engine expected HRR after native suppression, not original input HRR.
    DJET is a receiving compartment total, not an individual doorway measurement.
    """
    with (Path(directory)/f'{stem}_compartments.csv').open() as stream:
        rd = csv.reader(stream)
        headers = next(rd); next(rd)
        ids = dict(zip(headers, next(rd))); units = dict(zip(headers, next(rd)))
        records = [dict(zip(headers, map(float, row))) for row in rd if row]
    times = [r['Time'] for r in records]
    expected_times = [i*result['step'] for i in range(len(result['hrr']))]
    assert times == expected_times, 'Combustion samples must align exactly with playback'
    assert all(math.isfinite(x) for r in records for x in r.values())
    rooms = {r['key']: r for r in result['rooms']}
    solver_for = {r['key']: r['solver_key'] for r in result['rooms']}
    native_index = {ids[k]: k[4:] for k in headers if k.startswith('ULT_')}
    floor_map = {f['name']: f for f in building['floors']}
    fire_groups = {}
    fire_by_id = {f['id']: f for f in result['fires']}
    for key in headers:
        if not key.startswith('HRR_E'):
            continue
        i = key[5:]; f = fire_by_id[ids[key]]
        assert units[key] == units['HRR_'+i] == 'W'
        f['expected_hrr'] = [r[key]/1000 for r in records]
        f['pyrolysis_kg_s'] = [r['PYROL_'+i] for r in records]
        fire_groups.setdefault(solver_for[f['room_key']], []).append(i)

    diagnostics = []
    for solver, indices in fire_groups.items():
        n = native_index[solver]
        expected = [sum(r['HRR_E'+i] for i in indices)/1000 for r in records]
        actual = [sum(r['HRR_'+i] for i in indices)/1000 for r in records]
        flags = [e > 1 and e-a > max(1., .01*e) for e, a in zip(expected, actual)]
        gas = lambda prefix: [r[prefix+n] for r in records]
        assert units['ULO2_'+n] == 'mol %'
        diagnostics.append(dict(solver_key=solver, room_keys=result['solver_members'][solver],
                                expected_kW=expected, actual_kW=actual,
                                limited=flags, intervals=sustained_intervals(times, flags),
                                upper_o2_percent=gas('ULO2_'),
                                lower_o2_percent=gas('LLO2_') if 'LLO2_'+n in records[0] else gas('ULO2_'),
                                unburned_upper_percent=gas('ULTUHC_')))

    def opening_centre(floor, oid):
        opening = next((o for o in floor_map[floor]['openings'] if o['id']==oid), None)
        if not opening:
            return None
        pts = [p for leaf in opening.get('leaves', []) for p in [leaf['hinge'], leaf['closed']]]
        if not pts:
            pts = [p for poly in opening.get('geometry_polys', []) for p in poly['o']]
        return [sum(p[d] for p in pts)/len(pts) for d in (0,1)] if pts else None

    jets = []
    for key in headers:
        if not key.startswith('DJET_'):
            continue
        assert units[key] == 'W'
        series = [r[key]/1000 for r in records]
        if max(series) <= .01:
            continue
        solver = ids[key]
        candidates = []
        for v in result['vents']:
            if v['fraction'] <= 0:
                continue
            a = solver_for.get(v['a'], v['a']); b = solver_for.get(v['b'], v['b'])
            if solver not in (a,b) or a == b:
                continue
            receiver = v['a'] if a == solver else v['b']
            donor = v['b'] if a == solver else v['a']
            donor_solver = solver_for.get(donor)
            n = native_index.get(donor_solver)
            score = max((r['ULTUHC_'+n] for r in records), default=0) if n else 0
            floor, oid = v['id'].split('_',1)
            point = opening_centre(floor, oid)
            if point and receiver in rooms:
                candidates.append(dict(vent_id=v['id'], room_key=receiver, donor_room=donor,
                                       floor=floor, position=point, top=v['top'], width=v['width'],
                                       donor_fuel_score=score))
        candidates.sort(key=lambda c:c['donor_fuel_score'], reverse=True)
        # A single illustrative anchor avoids implying that each candidate has the full DJET.
        anchor = candidates[0] if candidates and candidates[0]['donor_fuel_score']>0 else None
        jets.append(dict(solver_key=solver, room_keys=result['solver_members'].get(solver, []),
                         hrr=series, onset=next(t for t,q in zip(times,series) if q>.01),
                         peak_kW=max(series), peak_time=times[series.index(max(series))],
                         anchor=anchor, candidates=candidates,
                         location_basis='illustrative_opening_from_connectivity_and_donor_fuel; not native per-vent output'))
    summed = [sum(j['hrr'][i] for j in jets) for i in range(len(times))]
    assert all(abs(a-b)<.02 for a,b in zip(summed,result['vent_jet_hrr']))
    result['assumptions'] = [a.replace('문·천장을 따라 이어지는 국소 화염 형상은 아직 표시하지 않음',
                            '기본 모드는 구획별 수치를 표시하고 실감보기의 문·천장 방향 불꽃은 연출로 표시')
                             for a in result['assumptions']]
    result['combustion'] = dict(version=28, step=result['step'], rooms=diagnostics, jets=jets,
        criterion=dict(relative_deficit=.01, absolute_deficit_kW=1, minimum_expected_kW=1,
                       sustained_seconds=10, official_transition_threshold=False,
                       description='HRR_E−HRR > max(1 kW, HRR_E×1%)가 10초 지속: 앱의 산소제한 표시 기준; NIST 전환 임계값 아님'),
        interpretation='환기지배 표시는 등록 화원의 산소 제한 진단. DJET는 수신 구획별 합계. 실감보기 위치·형상·천장 방향 퍼짐은 연출이며 추가 착화가 아님.')
    return result
