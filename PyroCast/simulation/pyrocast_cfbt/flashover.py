"""Threshold-triggered, finite room fuel supply; CFAST still computes combustion.

This is a prescribed-fire extension, not a material pyrolysis/phase-change model.
The switch and supply ramp are scenario assumptions, not NIST universal constants.
"""
import numpy as np


def integral(knots, values, time):
    """Exact integral of a nonnegative, piecewise-linear, finite supply curve."""
    x = np.asarray(knots, float); y = np.asarray(values, float)
    age = np.clip(np.asarray(time, float), x[0], x[-1])
    pos = np.clip(np.searchsorted(x, age, side='right') - 1, 0, len(x)-2)
    accumulated = np.r_[0., np.cumsum(np.diff(x)*(y[:-1]+y[1:])/2)]
    delta = age-x[pos]
    return accumulated[pos]+y[pos]*delta+.5*(y[pos+1]-y[pos])/np.diff(x)[pos]*delta**2


def source_curves(model, ignitions, transitions):
    """Global-time curves; after a ramp only one active FIRE per transitioned room.

    Existing FIRE IDs/locations remain stable. Their prescribed supply before the
    switch is unchanged, including every original interpolation knot. Secondary
    fires taper to zero while the chosen source takes over the pooled fuel.
    """
    from .deck import active_fuels, fire_curve
    rooms = {r['id']: r for r in model['rooms']}
    start = {g['id']: g['initial_time_s'] for g in model['fuel_groups'] if 'initial_time_s' in g}
    start.update({e['group']: e['t_ign_s'] for e in ignitions})
    active = active_fuels(model, ignitions)
    curves = {}
    for g in active:
        room = rooms[g['room']]
        t, q, area = fire_curve(g, room['size_m'][0]*room['size_m'][1])
        curves[g['id']] = {'t': np.asarray(t)+start[g['id']], 'q': np.asarray(q),
                           'area': np.asarray(area), 'start_s': start[g['id']]}
    pools = {}
    for event in transitions:
        rid = event['room']; at = event['t_ign_s']; room = rooms[rid]
        groups = [g for g in model['fuel_groups'] if g['room'] == rid]
        sources = [g for g in active if g['room'] == rid and start[g['id']] <= at]
        if not sources:
            raise ValueError('Room transition requires an already activated source')
        owner = min(sources, key=lambda g: start[g['id']])['id']
        if any(g['room'] == rid and start[g['id']] > at for g in active):
            raise ValueError('A separate ignition cannot follow fuel pooling in the same room')
        remaining = {}
        for g in groups:
            used = float(integral(curves[g['id']]['t'], curves[g['id']]['q'], at)) if g['id'] in curves else 0.
            remaining[g['id']] = max(0., g['energy_MJ']*1000-used)
        energy = sum(remaining.values())
        if energy <= 1e-9:
            raise ValueError('Room transition has no remaining solid fuel')
        prefix = {}; q0 = {}
        for g in sources:
            key = g['id']; c = curves[key]
            keep = c['t'] < at
            prefix[key] = (np.r_[c['t'][keep], at], np.r_[c['q'][keep], np.interp(at, c['t'], c['q'], right=0)],
                           np.r_[c['area'][keep], np.interp(at, c['t'], c['area'])])
            q0[key] = float(prefix[key][1][-1])
        settings = model['flashover']
        area = room['size_m'][0]*room['size_m'][1]
        if settings.get('area_basis','floor') == 'fuel':
            area = min(area, sum(g.get('fuel_area_m2',0.) for g in groups) or settings['occupancy_fraction']*area)
        hrrpua = settings['hrrpua_kW_m2']
        if hrrpua is None:
            hrrpua = sum(g['hrrpua_kW_m2']*g['energy_MJ'] for g in groups)/sum(g['energy_MJ'] for g in groups)
        target = max(sum(q0.values()), area*hrrpua)
        supply_cap=settings.get('max_supply_by_room_kW',{}).get(rid,settings.get('max_supply_kW'))
        if supply_cap is not None:
            target=max(sum(q0.values()),min(target,supply_cap))
        decay_energy = settings['decay_fraction']*energy
        ramp = min(settings['transition_s'], 2*(energy-decay_energy)/(sum(q0.values())+target))
        ramp_energy = .5*(sum(q0.values())+target)*ramp
        hold = max(0., (energy-ramp_energy-decay_energy)/target)
        decay = 2*decay_energy/target
        for g in sources:
            key = g['id']; t, q, prefix_area = prefix[key]
            if key == owner:
                tail_t = [at+ramp]; tail_q = [target]
                if hold > 1e-10:
                    tail_t.append(at+ramp+hold); tail_q.append(target)
                tail_t.append(at+ramp+hold+decay); tail_q.append(0.)
            else:
                tail_t = [at+ramp]; tail_q = [0.]
            t = np.r_[t, tail_t]; q = np.r_[q, tail_q]
            curves[key] = {'t': t, 'q': q, 'start_s': start[key],
                           'area': np.r_[prefix_area, np.minimum(area, np.maximum(.1, np.asarray(tail_q)/hrrpua))]}
        final_energy = sum(float(integral(curves[g['id']]['t'], curves[g['id']]['q'], curves[g['id']]['t'][-1])) for g in sources)
        total_energy = sum(g['energy_MJ']*1000 for g in groups)
        if not np.isclose(final_energy, total_energy, rtol=1e-10, atol=1e-5):
            raise ValueError('Room transition changed the total prescribed fuel energy')
        pools[rid] = {'owner_group': owner, 'time_s': at, 'ramp_end_s': at+ramp,
                      'supply_end_s': at+ramp+hold+decay, 'target_supply_kW': target,
                      'remaining_at_switch_kJ': energy, 'remaining_by_group_kJ': remaining,
                      'total_allocated_kJ': total_energy, 'ramp_s': ramp,
                      'area_m2': area, 'hrrpua_kW_m2': hrrpua,
                      'basis': 'prescribed_room_supply_not_predicted_solid_pyrolysis'}
    return curves, pools


def proposals(model, result, states, ignitions, transitions, views):
    settings = model['flashover']
    if not settings['enabled']:
        return []
    t = np.asarray(result['zone']['Time']); output = []
    starts = {g['id']: g['initial_time_s'] for g in model['fuel_groups'] if 'initial_time_s' in g}
    starts.update({e['group']: e['t_ign_s'] for e in ignitions})
    done = {e['room'] for e in transitions}
    groups_by_room = {}
    for g in model['fuel_groups']:
        groups_by_room.setdefault(g['room'], []).append(g)
    for rid, groups in groups_by_room.items():
        active_starts = [starts[g['id']] for g in groups if g['id'] in starts]
        if rid in done or not active_starts:
            continue
        start = min(active_starts)
        temperature = np.asarray(states[rid]['T_upper_C'])
        signals = [('upper_temperature', temperature, model['criteria']['fo_temperature_C'])]
        if settings['criterion'] == 'temperature_or_flux':
            floor = [np.asarray(v['q_inc_kW_m2']) for v in views if v.get('status','ok')=='ok' and v['room'] == rid and v['normal'][2] > .99]
            if floor:
                signals.append(('evaluated_floor_incident_flux', np.max(floor, axis=0), model['criteria']['fo_flux_kW_m2']))
        events = []
        for trigger, values, threshold in signals:
            hits = np.flatnonzero((t >= start) & (values >= threshold))
            if not len(hits):
                continue
            i = hits[0]; when = float(t[i])
            if i and values[i-1] < threshold:
                when = max(start, float(t[i-1]+(t[i]-t[i-1])*(threshold-values[i-1])/(values[i]-values[i-1])))
            # Ignore exhausted rooms. Supply is deducted, not merely actual HRR.
            curves, _ = source_curves(model, ignitions, [])
            remaining = sum(g['energy_MJ']*1000-(float(integral(curves[g['id']]['t'], curves[g['id']]['q'], when)) if g['id'] in curves else 0.) for g in groups)
            if remaining > 1e-6:
                events.append({'event_id': 'FO_'+rid, 'kind': 'fo_transition', 'room': rid,
                               't_ign_s': when, 'trigger': trigger, 'threshold': threshold,
                               'basis': 'user_threshold_room_fuel_participation_not_physical_phase_change'})
        if events:
            output.append(min(events, key=lambda e: e['t_ign_s']))
    return output


def pool_inventory(model, result, ignitions, transitions):
    """One pooled ledger per room, retaining original group shares for reporting."""
    curves, pools = source_curves(model, ignitions, transitions)
    t = result['zone']['Time']
    for rid, pool in pools.items():
        groups = [g for g in model['fuel_groups'] if g['room'] == rid]
        supplied = np.zeros(len(t))
        for g in groups:
            if g['id'] in curves:
                c = curves[g['id']]; supplied += integral(c['t'], c['q'], t)
        pool['remaining_solid_kg'] = np.maximum(0., pool['total_allocated_kJ']-supplied)/groups[0]['heat_of_combustion_kJ_kg']
        pool['post_transition'] = t >= pool['time_s']
        pool['mass_basis'] = 'all pooled groups have identical effective chemistry and heat of combustion'
    return pools
