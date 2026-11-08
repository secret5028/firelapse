"""User-authorized equivalent relief sizing, not a measured building leakage model.

Orifice flow Q=Cd*A*sqrt(2*abs(dP)/rho) gives A_new=A*sqrt(P/P_target).
Re-run the mass/energy solver after resizing; never clip its pressure output.
"""
import math
import re
from .physics_config import defaults

REVISION = 'basement_pressure_relief_v2'


def below_grade(room, model):
    if isinstance(room.get('below_grade'), bool): return room['below_grade']
    # CAD conversion shifts elevations to a nonnegative solver datum. Retain
    # the generic basement floor designation when the survey datum is absent.
    floor = str(room.get('cad_floor', '')).strip().upper()
    if re.fullmatch(r'B\d+|지하\s*\d+층?', floor): return True
    return room.get('origin_m', [0, 0, 0])[2] < model.get('grade_m', 0)


def configure(model):
    cfg = {**defaults('basement_pressure'), **model.get('basement_pressure_settings', {})}
    if type(cfg['enabled']) is not bool: raise ValueError('Relief enabled must be boolean')
    if type(cfg['early_resize']) is not bool: raise ValueError('Early resize must be boolean')
    for key in ('limit_Pa', 'target_Pa', 'max_area_m2', 'max_scale', 'max_attempts','probe_interval_s'):
        v=cfg[key]
        if type(v) not in (int,float) or not math.isfinite(v) or v <= 0:
            raise ValueError('Invalid basement pressure setting: '+key)
    if cfg['target_Pa'] >= cfg['limit_Pa'] or int(cfg['max_attempts']) != cfg['max_attempts'] or cfg['max_scale'] <= 1:
        raise ValueError('Invalid basement pressure sizing bounds')
    rooms={r['id']:r for r in model['rooms']};below={k for k,r in rooms.items() if below_grade(r,model)}
    if not cfg['enabled'] or not below:
        model.pop('basement_pressure',None);return
    vents=[v for v in model['openings'] if v.get('minimum_leakage') and v['a'] in below]
    if not vents:
        # Real specified exterior routes retain their geometry. Only an already
        # declared aggregate assumption can be sized automatically.
        model.pop('basement_pressure',None);return
    for v in vents:v['basement_pressure_relief']=True
    previous=model.get('basement_pressure',{})
    model['basement_pressure']=dict(revision=REVISION,**cfg,
        basis='assumed aggregate route through omitted building/ducts; pressure bound is a project assumption, not measured or statutory',
        formula='Q=Cd*A*sqrt(2*abs(dP)/rho); A_next=A*sqrt(P_peak/P_target)',
        history=previous.get('history',[]))
    describe(model)


def describe(model):
    policy=model['basement_pressure']
    vents=[v for v in model['openings'] if v.get('basement_pressure_relief')]
    policy['area_m2']=sum(v['width_m']*(v['top_m']-v.get('bottom_m',0)) for v in vents)
    byid={v['a']:v for v in vents}
    for row in model.get('minimum_leakage',[]):
        if row['room'] in byid:
            v=byid[row['room']];row['area_m2']=v['width_m']*(v['top_m']-v.get('bottom_m',0))
            row['basis']='pressure-bounded equivalent building path; not measured'
    model['limits']=[s for s in model.get('limits',[]) if not s.startswith(('지하 압력 간략식:', '최소 누기 가정 적용:'))]
    checked=f" · 계산 최고 {policy['verified_peak_Pa']:.1f} Pa" if policy.get('passed') else ''
    model['limits'].append(f"지하 압력 간략식: 상한 {policy['limit_Pa']:g} Pa{checked} · 등가 배출 면적 {policy['area_m2']:.4g} m² · 생략한 건물·덕트 경로의 가정, 실측 아님 · 팬 가동과 별도")


def record_and_resize(model, pressure):
    """Return True only if a fresh solver run with changed vent areas is needed."""
    p=model.get('basement_pressure')
    if not p:return False
    if not math.isfinite(pressure):raise ValueError('Nonfinite basement pressure')
    p['history'].append(dict(peak_abs_pressure_Pa=float(pressure),area_m2=p['area_m2']))
    p['verified_peak_Pa']=float(pressure);p['passed']=pressure <= p['limit_Pa']
    if p['passed']:
        describe(model)
        return False
    if len(p['history']) >= p['max_attempts']:raise ValueError('지하 압력 상한 미충족: 등가 경로 자동 보정 한도 도달')
    factor=min(p['max_scale'],math.sqrt(pressure/p['target_Pa']))
    vents=[v for v in model['openings'] if v.get('basement_pressure_relief')]
    if p['area_m2']*factor > p['max_area_m2']:
        raise ValueError('지하 압력 상한 미충족: 등가 배출 면적 가정 한도 초과')
    rooms={r['id']:r for r in model['rooms']}
    if any(v['width_m']*factor+v.get('offset_m',0)>rooms[v['a']]['size_m'][0] for v in vents):
        raise ValueError('등가 배출 경로가 구획 너비를 초과합니다')
    for v in vents:v['width_m']*=factor
    describe(model)
    return True


def rewrite_deck(deck, model):
    for v in model['openings']:
        if not v.get('basement_pressure_relief'):continue
        pattern=r"(&VENT\b[^\n]*\bID='"+re.escape(v['id'])+r"'[^\n]*\bWIDTH=)[^\s,/]+"
        deck,count=re.subn(pattern,lambda m:m[1]+format(v['width_m'],'.12g'),deck)
        if count!=1:raise ValueError('Relief vent missing from native deck: '+v['id'])
    return deck
