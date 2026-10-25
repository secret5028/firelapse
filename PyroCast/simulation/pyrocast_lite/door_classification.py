"""User-prescribed screening classification, not a building-code determination."""
from copy import deepcopy
import json,re,math
from pathlib import Path
CONFIG=Path(__file__).with_name('door_class_rules.json')

def core_evidence(room,config):
    """Rule 2: area gate AND a core kind or leading core-name token."""
    text=' '.join([str(room.get('name') or ''),*map(str,room.get('cad_names',[]))]).strip()
    value=room.get('area_m2')
    if value is None:
        size=room.get('size_m',[])
        value=size[0]*size[1] if len(size)>=2 else None
    valid=isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>0
    area_ok=bool(valid and value<=config['core_max_area_m2'])
    kind=room.get('core_kind');kind_ok=kind in config['core_kinds']
    match=re.match(config['vertical_first_token'],text)
    return {'room':room['id'],'name':text,'area_m2':value if valid else None,
            'area_limit_m2':config['core_max_area_m2'],'area_ok':area_ok,
            'core_kind':kind,'core_kind_match':kind_ok,'leading_core_token':match.group(0) if match else None,
            'eligible':area_ok and (kind_ok or bool(match))}

def classify_doors(raw,overrides=None):
    config=json.loads(CONFIG.read_text('utf-8'));model=deepcopy(raw);rows=[]
    rooms={r['id']:r for r in model['rooms']};overrides=overrides or {}
    def names(r):return ' '.join([str(r.get('name','')),*map(str,r.get('cad_names',[]))])
    def area(r):return r.get('area_m2',r['size_m'][0]*r['size_m'][1])
    for v in model['openings']:
        if 'door' not in v.get('kind','').lower():continue
        connected=[rooms[k] for k in (v['a'],v['b']) if k in rooms]
        texts=[names(r) for r in connected]
        core_checks=[core_evidence(r,config) for r in connected]
        explicit={k:val for k,val in v.items() if any(q in k.lower() for q in ('layer','block','symbol','label','text','evidence','topology_correction'))}
        evidence=json.dumps(explicit,ensure_ascii=False)
        rule=6;label='ordinary';confidence='default';reason='일반문 기본값'
        # Previously inferred classifier output is not new drawing evidence.
        source_fire_flag=v.get('door_source_fire_flag',bool(v.get('fire_door') and 'door_class_basis' not in v))
        if source_fire_flag or re.search(config['explicit'],evidence):
            rule=1;label='fire';confidence='confirmed';reason='도면 명시: '+evidence
        elif any(row['eligible'] for row in core_checks):
            rule=2;label='fire';confidence='confirmed'
            reason='80㎡ 이하 코어 연결: '+' / '.join(
                f"{r['room']} {r['area_m2']:.2f}㎡ ({r['core_kind'] if r['core_kind_match'] else r['leading_core_token']})"
                for r in core_checks if r['eligible'])
        elif any(re.search(config['service'],text) for text in texts):
            rule=3;label='fire';confidence='inferred';reason='설비·샤프트·창고 연결: '+' / '.join(texts)
        elif len(connected)==2:
            corridor=[bool(re.search(config['corridor'],s)) for s in texts]
            lobby=[bool(re.search(config['lobby'],s)) for s in texts]
            sprinkler=model.get('sprinkler_enabled') is True or all(r.get('sprinkler') is True for r in connected)
            limit=config['sprinkler_compartment_area_m2'] if sprinkler else config['compartment_area_m2']
            if ((corridor[0] and (corridor[1] or lobby[1])) or (corridor[1] and lobby[0])) and sum(map(area,connected))>limit:
                rule=4;label='fire';confidence='inferred';reason=f'인접 공간 면적 합 {sum(map(area,connected)):.2f} > {limit} m2; 실제 구획선 미확인'
        if rule==6 and 'OUTSIDE' in (v['a'],v['b']):rule=5;label='external';confidence='not_applicable';reason='외기 개구부'
        if v['id'] in overrides:
            label=overrides[v['id']]
            if label not in ('fire','ordinary','external'):raise ValueError('Invalid door class override')
            confidence='user';reason='사용자 저장값 우선';rule=0
        v.update(door_class=label,door_class_basis=rule,door_class_confidence=confidence,
                 door_class_reason=reason,fire_door=label=='fire',door_type='fire_door' if label=='fire' else 'ordinary')
        if label!='fire':v.pop('fire_rating_minutes',None)
        v['door_class_revision']=config['revision']
        v['door_source_fire_flag']=source_fire_flag
        rows.append({'id':v['id'],'a':v['a'],'b':v['b'],'connected_names':texts,
            'door_class':label,'rule':rule,'confidence':confidence,'reason':reason,
            'core_checks':core_checks,
            'probability':config['inferred_fire_door_probability'] if label=='fire' and confidence=='inferred' else .2 if label=='fire' else .5,
            'position_m':v.get('cad_geometry',{}).get('center_m')})
    if set(overrides)-{r['id'] for r in rows}:raise ValueError('Unknown/non-door override ID')
    return model,{'revision':config['revision'],'rows':rows,
        'limitations':['rule2 confirmed is prescribed classification confidence, not verified fire rating or legal compliance',
            'rule3/4 inferred; no thickness/fire-resistance survey',
            'missing sprinkler metadata uses1000m2; area sum is only a screening proxy',
            'rule2 area<=80m2 AND configured core_kind or leading core keyword; generic shaft is not a rule2 core',
            'area threshold is a project assumption; R4 above80m2 receives no exception',
            'r8 removes all fire-door spread edges including opened fire doors; native flow still follows sampled opening; preserved rule limitation']}
