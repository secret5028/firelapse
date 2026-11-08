"""Screen native output before exposing operational indices (project acceptance limits)."""
from pathlib import Path
import re
import numpy as np
from .physics_config import defaults

SPECIES = ('N2','O2','CO2','CO','HCN','HCL','TUHC','H2O','OD')


def model_from_deck(deck):
    """Fallback for legacy callers: actual native boundaries, without normalization."""
    model=dict(rooms=[],openings=[],mechanical_vents=[])
    for kind,body in re.findall(r'&(COMP|VENT)\b([^/]+)/',deck,re.I):
        ident=re.search(r"\bID\s*=\s*'([^']+)'",body,re.I)
        if not ident:continue
        if kind.upper()=='COMP':
            leak=re.search(r'LEAK_AREA_RATIO\s*=\s*([\d.Ee+,-]+)',body,re.I)
            model['rooms'].append(dict(id=ident[1],shaft=bool(re.search(r'SHAFT\s*=\s*\.TRUE\.',body,re.I)),leak_area_ratio=[float(v) for v in leak[1].split(',')] if leak else [0,0]))
        else:
            sides=re.search(r"COMP_IDS\s*=\s*'([^']+)'\s*,\s*'([^']+)'",body,re.I)
            if sides and "'MECHANICAL'" in body.upper():
                model['mechanical_vents'].append(dict(id=ident[1],comp=sides[2] if sides[1]=='OUTSIDE' else sides[1],direction='supply' if sides[1]=='OUTSIDE' else 'exhaust'));continue
            if sides:model['openings'].append(dict(id=ident[1],a=sides[1],b=sides[2],type='FLOOR' if "'CEILING'" in body.upper() or "'FLOOR'" in body.upper() else 'WALL'))
    return model


def validate_native(result, model, folder=None):
    from .native import read_native_csv
    cfg = {**defaults('validation'), **model.get('validation', {})}
    if any(not np.isfinite(v) or v <= 0 for v in cfg.values()):
        raise ValueError('Physical acceptance limits must be finite and positive')
    c = result['compartments']; t = np.asarray(c['Time']); n=len(t)
    folder = Path(folder or result['run']['folder'])
    reasons=[]; unknown=[]; metrics={}
    def check(name, value, limit, lower=False):
        metrics[name]=float(value)
        if (value < limit if lower else value > limit):
            reasons.append(dict(check=name,value=float(value),limit=limit))
    pressures=[a for k,a in c.items() if k.startswith('PRS_')]
    if pressures: check('max_abs_pressure_Pa',max(np.max(np.abs(a)) for a in pressures),cfg['max_pressure_Pa'])
    else: unknown.append('pressure_missing')
    try:
        masses,_,units=read_native_csv(folder/'case_masses.csv',float(t[-1]))
        if not np.array_equal(masses['Time'],t):raise ValueError('Mass timestamps differ')
        indices=sorted({k.split('_')[-1] for k in masses if k.startswith('ULMN2_')})
        total=np.zeros(n); ratios=[]
        for i in indices:
            upper=sum(masses[f'ULM{s}_{i}'] for s in SPECIES)
            shaft = int(i)<=len(model.get('rooms',[])) and model['rooms'][int(i)-1].get('shaft',False)
            lower=sum(masses.get(f'LLM{s}_{i}',np.zeros(n)) if shaft else masses[f'LLM{s}_{i}'] for s in SPECIES)
            if any(units.get(f'{layer}M{s}_{i}','kg' if shaft and layer=='LL' else None)!='kg' for s in SPECIES for layer in ('UL','LL')):
                raise ValueError('Mass units must be kg')
            total+=upper+lower
            ratios.append(np.divide(masses[f'ULMTUHC_{i}'],upper,out=np.zeros(n),where=upper>0))
        if not indices:raise ValueError('Missing species ledger')
        check('max_upper_fuel_fraction',max(np.max(a) for a in ratios),cfg['max_upper_fuel_fraction'])
        # OD is total soot mass; ODF/ODS are its components, TS is a tracer.
        # Do not sum them again. External OUTflow must be subtracted as well.
        pyro=sum((a for k,a in c.items() if k.startswith('PYROL_')),np.zeros(n))
        inflow=np.zeros(n);outflow=np.zeros(n)
        vents=result.get('native_vents',{}); ids=result.get('native_vents_ids',{})
        external=[v for v in model.get('openings',[]) if 'OUTSIDE' in (v['a'],v['b'])]
        flows_known=all(not any(r.get('leak_area_ratio',[.00017,.000052])) for r in model.get('rooms',[]))
        for v in model.get('mechanical_vents',[]):
            external.append(dict(id=v['id'],a='OUTSIDE' if v.get('direction','supply')=='supply' else v['comp'],b=v['comp'] if v.get('direction','supply')=='supply' else 'OUTSIDE',mechanical=True))
        for v in external:
            keys=[k for k in vents if ids.get(k)==v['id'] and k.startswith('MT_' if v.get('mechanical') else 'CFT_' if v.get('type')=='FLOOR' else 'WT_')]
            if len(keys)!=4:flows_known=False;continue
            for k in keys:
                incoming='inflow' in k
                # CFAST labels flows relative to room1 for WALL/MECHANICAL,
                # room2 (bottom) for FLOOR. The CSV key identifies that endpoint.
                if k.split('_')[1].lower()=='outside':incoming=not incoming
                if incoming:inflow+=np.abs(vents[k])
                else:outflow+=np.abs(vents[k])
        if flows_known:
            supplied=float(np.trapezoid(pyro+inflow,t));removed=float(np.trapezoid(outflow,t))
            change=float(total[-1]-total[0]);residual=change-supplied+removed
            metrics.update(mass_change_kg=change,mass_supplied_kg=supplied,mass_removed_kg=removed,mass_residual_kg=residual)
            if supplied>0:check('mass_balance_error',abs(residual)/supplied,cfg['max_mass_balance_error'])
            elif abs(residual)>np.finfo(float).eps:unknown.append('mass_balance_zero_source')
            else:metrics['mass_balance_error']=0.
        else:unknown.append('mass_balance_external_flow_ledger_unavailable')
    except (OSError,ValueError,KeyError) as exc:
        unknown.append('species_ledger_unavailable: '+str(exc))
    actual=sum((a for k,a in c.items() if re.fullmatch(r'HRR_\d+',k)),np.zeros(n))
    expected=sum((a for k,a in c.items() if re.fullmatch(r'HRR_E_?\d+',k)),np.zeros(n))
    denominator=float(np.trapezoid(expected,t))
    if denominator>0:check('burned_fraction',float(np.trapezoid(actual,t))/denominator,cfg['min_burned_fraction'],True)
    else:unknown.append('prescribed_hrr_unavailable_or_zero')
    return dict(revision='native_physical_validation_v1',status='physically_invalid' if reasons else 'unverified' if unknown else 'valid',
                passed=not reasons and not unknown,reasons=reasons,unknown=unknown,metrics=metrics,thresholds=cfg)


def protect_playback(playback, validation):
    """Keep computed quantities for diagnosis; remove tactical screening of invalid runs."""
    playback['physical_validation']=validation
    if validation['status']=='unverified':
        playback.setdefault('limits',[]).append('물리 타당성 일부 미확인: '+', '.join(validation.get('unknown',[]))+' · 검증 통과 결과가 아닙니다.')
    if validation['status']=='physically_invalid':
        playback['status']='physically_invalid'
        message='물리 타당성 검사 실패: '+', '.join(f"{r['check']}={r['value']:.4g}" for r in validation['reasons'])
        if any(r['check']=='max_abs_pressure_Pa' for r in validation['reasons']):
            message+=' · 최소 누기 면적 또는 실제 환기 경로를 확인하고 다시 계산하세요.'
        playback.setdefault('limits',[]).append(message)
        for solver in playback.get('solvers',{}).values():
            for condition in solver.get('conditions',{}).values():
                condition.clear();condition.update(status='physically_invalid',scores={'degree':[None]*len(playback['time_s'])})
        playback.pop('briefing',None)
