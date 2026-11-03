"""Event-segmented SciPy BDF. Restarts at accepted event states, never time zero."""
import time
from types import SimpleNamespace
import numpy as np
from scipy.integrate import solve_ivp


def run(model, duration_s, output_s=10., budget_s=600., method='BDF'):
    if duration_s <= 0 or output_s <= 0 or budget_s <= 0:
        raise ValueError('Positive time limits required')
    started = time.perf_counter(); n = model.N
    atol = np.concatenate([np.full(n,1e-3), model.Vmin*.1,
        np.full(2*n,.05), np.full(4*n,1e-6), [1e3]])
    if hasattr(model,'integration_atol'):atol=model.integration_atol()
    sparsity = model.sparsity()
    t = 0.; y = model.y0(); grid = np.arange(0,duration_s+1e-9,output_s)
    if grid[-1] < duration_s: grid = np.append(grid,duration_s)
    samples_t = []; samples_y = []; segments = []; complete = False
    next_sample = 0; failure = None

    def rhs(ti,yi):
        # Trial evaluations are not accepted solver states. Keep that distinction
        # when diagnosing an exception inside SciPy's factorization.
        model.last_trial_state=(float(ti),yi.copy())
        if time.perf_counter()-started > budget_s:
            raise TimeoutError('L1 integration wall-time budget exceeded')
        return model.rhs(ti,yi)

    while t < duration_s:
        # Strictly positive initial conditions must not wait for a new crossing.
        keys = sorted({model.key(r) for r in model.pending})
        for key in keys:
            if model.trigger_value(key,t,y) > 0: model.activate(key,t)
        keys = sorted({model.key(r) for r in model.pending})
        events = []
        for key in keys:
            def event(ti,yi,key=key): return model.trigger_value(key,ti,yi)
            event.direction=1; event.terminal=True; events.append(event)
        # Do not step over a zero-HRR delay/ramp onset without notifying BDF.
        # These are prescribed input knots, not simulation-from-zero runs.
        future = [at+float(k) for room,at in model.activation.items()
                  for k in model.curves[room][0] if at+float(k)>t+1e-9]
        end = min([float(duration_s)]+future)
        try:
            sol = solve_ivp(rhs,(t,end),y,method=method,rtol=1e-4,atol=atol,
                            jac_sparsity=sparsity,events=events or None,dense_output=True)
        except (TimeoutError, RuntimeError, ValueError, FloatingPointError) as exc:
            failure = str(exc)
            model.failed_segment_start=(float(t),y.copy())
            break
        last = float(sol.t[-1])
        segments.append({'start_s':t,'end_s':last,'accepted_steps':len(sol.t)-1,
                         'nfev':sol.nfev,'njev':sol.njev,'nlu':sol.nlu,
                         'reason':'event' if sol.status==1 else 'input_knot' if end<duration_s else 'end'})
        while next_sample<len(grid) and grid[next_sample]<=last+1e-8:
            ts = float(grid[next_sample]); samples_t.append(ts); samples_y.append(sol.sol(ts))
            next_sample += 1
        y = sol.y[:,-1].copy(); t=last
        if not sol.success:
            failure = sol.message; break
        if sol.status==1:
            found = [j for j,a in enumerate(sol.t_events) if len(a)]
            if not found:
                failure = 'Terminal event without event state'; break
            for j in found: model.activate(keys[j],t)
        if t>=duration_s:
            complete=True; break
    elapsed=time.perf_counter()-started
    if not samples_t:
        samples_t=[0.];samples_y=[model.y0()]
    model.sol=SimpleNamespace(t=np.array(samples_t),y=np.array(samples_y).T,
                              success=complete,message=failure or 'Completed')
    model.integration={'complete':complete,'wall_seconds':elapsed,'segments':segments,'solver':method,
                       'from_zero_replays':0,'event_restarts':sum(x['reason']=='event' for x in segments),
                       'accepted_steps':sum(x['accepted_steps'] for x in segments),
                       'nfev':sum(x['nfev'] for x in segments),
                       'safe_output_end_s':samples_t[-1],'failure':failure}
    return model.sol


def results(model, post_started=None):
    from .montecarlo import KNOWN_BIAS,BIAS_SCOPE
    start=time.perf_counter() if post_started is None else post_started
    result=model.result()
    result['flags']={k:v.tolist() for k,v in result['flags'].items()}
    n=model.N; sol=model.sol
    diagnostics=[model.rhs(float(t),sol.y[:,j],diag=True) for j,t in enumerate(sol.t)]
    hrr=np.array([d['room_Q'] for d in diagnostics]).T/1000
    supply=np.array([d['room_Qf'] for d in diagnostics]).T/1000
    room_rows=[]
    for i,node in enumerate(model.nodes):
        pos=hrr[i]>0; longest=0.; beginning=None
        for j,flag in enumerate(pos):
            if flag and beginning is None: beginning=sol.t[j]
            if flag: longest=max(longest,float(sol.t[j]-beginning))
            else: beginning=None
        original=next(r for r in model.input_model['rooms'] if r['id']==node['id']).get('parent_room',node['id'])
        room_rows.append({'cell':node['id'],'original_room':original,
            'first_actual_positive_HRR_s':float(sol.t[np.flatnonzero(pos)[0]]) if pos.any() else None,
            'actual_peak_kW':float(hrr[i].max()),'longest_positive_HRR_s':longest,
            'upper_max_C':float(sol.y[2*n+i].max()-273.15),
            'upper_oxygen_min_vol_percent':float(sol.y[4*n+i].min()*29/32*100)})
        result['rooms'][i].update(actual_HRR_kW=hrr[i].tolist(),supply_HRR_kW=supply[i].tolist())
        result['rooms'][i]['upper_reaction_kg_s']=[float(d['upper_reaction_kg_s'][i]) for d in diagnostics]
        result['rooms'][i]['upper_HRR_kW']=[float(d['upper_HRR_W'][i])/1000 for d in diagnostics]
        result['rooms'][i]['door_jet_HRR_kW']=[float(d['door_jet_room_HRR_W'][i])/1000 for d in diagnostics]
        result['rooms'][i]['door_jet_lower_oxygen_kg_s']=[float(d['door_jet_room_oxygen_kg_s'][i]) for d in diagnostics]
    result.update(engine_kind='pyrocast_lite',revision='L1_exploration',lite_revision='L1e_section1.5',
        known_bias=KNOWN_BIAS,bias_scope=BIAS_SCOPE,engine_use='scenario_screening; final confirmation by CFAST r8',
        rule_revision=model.manifest['revision'],rule_settings=model.manifest['rule_settings'],
        physical_parameters=dict(model.P),shared_inputs=getattr(model,'shared',None),
        gas_radiation=model.contract.get('gas_radiation'),
        r8_manifest_sha256=model.manifest_sha256,trigger_basis=model.contract['trigger_basis'],
        omitted_features=['plate_sensors','window_breakage','vertical_zones','legacy_pyro_feedback'],
        inactive_settings=[],seed=None,events=model.events_log,
        integration=model.integration,room_summary=room_rows,
        balance_audit={'status':'not_evaluated','passed':None},
        limits=['condition indicators, not event probabilities or accurate ignition times',
                'upper temperature replaces plate temperature for both room and cell triggers',
                'cell threshold may be reached by incoming heat before its parent cell itself burns',
                'legacy plume/oxygen/heat-loss equations retained, not a NIST validated solver',
                'unburned fuel is advected; source has no secondary gas or CO combustion',
                'no soot/extinction transport in source; smoke layer height is not optical density',
                'density uses reference P0 and source bound clipping remains; conservation audit required',
                'r8 future window cap retained although lite window breakage is off',
                'shared material inputs; one capacity node per surface, not native 1D conduction',
                'fire radiation distributed to surfaces by area, not native view factors',
                'shared room leakage areas/geometry and Cd 0.70; simplified flow/plume models remain',
                'native oxygen mass-fraction tanhsmooth shared; this alone does not make the combustion models identical',
                'legacy FGI LFL uses global dHc; mixed fuel chemistry is not resolved',
                'conditions retain legacy thresholds: 873 K is 599.85 C, not exactly 600 C'])
    if model.P.get('gas_radiation_enabled',False):
        result['limits'].extend([
            'grey kappa=0.50/m is the native fgasabsorb-OFF fallback, not normal species-dependent absorption',
            'new upper radiative exchange replaces old gas-wall radiative term; lower gas absorption omitted',
            'wall capacity-node temperature approximates surface temperature; no native radiosity/view-factor solve'])
    enabled=model.P.get('upper_combustion_enabled',False)
    result['upper_combustion']={'enabled':enabled,'mixing_time_s':model.P.get('upper_mixing_time_s'),
        'ignition_C':model.P.get('gas_ignition_C'),'oxygen_gate':'native mass-fraction LOL tanh',
        'reaction_temperature_width_K':model.P.get('reaction_temperature_width_K'),
        'basis':'inventory mixing surrogate, not identical to native plume chemistry or door jets',
        'oxygen_reservation':'subtract plume upper oxygen rate times mixing horizon before reaction',
        'energy_destination':'upper sensible heat only; no duplicate radiation or solid HRR',
        'cumulative_heat_MJ':float(np.trapezoid([sum(d['upper_HRR_W']) for d in diagnostics],sol.t)/1e6)}
    if enabled:
        result['limits']=[x for x in result['limits'] if 'source has no secondary gas' not in x]
        result['limits'].append('upper inventory reaction uses prescribed mixing20s; no CO-specific chemistry or native vent jet combustion')
    result['gas_conditions_evaluable']=enabled
    jet_enabled=model.P.get('door_jet_enabled',False)
    directions=[];nv=len(model.vents)
    for k,v in enumerate(model.vents):
        if not model.door_jet_eligible[k]:continue
        for reverse in (False,True):
            ix=k+(nv if reverse else 0);src,dst=(v[1],v[0]) if reverse else (v[0],v[1])
            q=[float(d['door_jet_HRR_W'][ix])/1000 for d in diagnostics]
            directions.append({'vent':v[5],'from':model.nodes[src]['id'],'to':model.nodes[dst]['id'],
                'HRR_kW':q,'reaction_kg_s':[float(d['door_jet_reaction_kg_s'][ix]) for d in diagnostics],
                'fuel_in_kg_s':[float(d['door_jet_incoming_fuel_kg_s'][ix]) for d in diagnostics],
                'oxygen_consumption_kg_s':[float(d['door_jet_oxygen_kg_s'][ix]) for d in diagnostics],
                'peak_kW':max(q,default=0.),'cumulative_heat_MJ':float(np.trapezoid(q,sol.t)/1000),
                'basis':'project door-jet surrogate; not native DJET or rollover'})
    result['door_jet']={**model.contract['door_jet'],'directions':directions,
        'cumulative_heat_MJ':float(np.trapezoid([sum(d['door_jet_room_HRR_W']) for d in diagnostics],sol.t)/1e6),
        'separate_from_upper_reaction':True,'physical_model_unchanged_when_off':not jet_enabled}
    if jet_enabled:
        result['limits']=[x for x in result['limits'] if 'no CO-specific chemistry or native vent jet combustion' not in x]
        result['limits'].extend(['door jet burns transported upper fuel with shared receiving lower oxygen budget (tau10s), not native entrainment chemistry',
            'plume lower oxygen withdrawal is reserved before jets; advected upper fuel is reserved before local bulk reaction',
            'jet heat enters receiving upper layer; no additional entrained mass, separate species-resolved products, exterior jet or virtual-cell jet',
            'door-jet heat is separate from solid-source HRR and upper-layer reaction; does not itself count as a new burning room'])
    result['rollover_state_source']='shared_conditions.rooms.<cell>.FGI.rollover'
    result['numerical_bounds']={'softplus':model.P.get('smooth_state_bounds',False),'width':'10 times state atol; not a physical parameter'}
    if model.P.get('remove_cumulative_state'):
        # Reporting only: these sums never feed back into prescribed curves.
        def accumulated(key):
            rates=np.asarray([d[key] for d in diagnostics])
            return np.r_[0.,np.cumsum(.5*(rates[1:]+rates[:-1])*np.diff(sol.t))].tolist()
        result['cumulative_energy']={'basis':'trapezoid on saved output times; not integrated solver states',
            'supply_J':accumulated('Qp'),'actual_combustion_J':accumulated('Q'),
            'feeds_back_into_physics':False}
        result['state_layout']={'cumulative_states':0,'size':int(sol.y.shape[0]),
            'wall_offset':8*n,'removed_previous_index':8*n}
        result['lite_revision']='v5_cumulative_removed_trial'
    from .result_adapter import shared_conditions
    result['shared_conditions']=shared_conditions(model,result)
    result['postprocess_wall_seconds']=time.perf_counter()-start
    return result
