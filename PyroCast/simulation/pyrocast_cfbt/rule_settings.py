"""Frozen r8 settings, shared by the native mode and future screening clients.
Bounds and preset values are project assumptions, not validated NIST limits.
"""
from copy import deepcopy
import math
FIELDS={
 'temperature_C':('실간 기준 · T4b 판(상층 대용)','℃',600.,450.,700.),
 'open_delay_s':('열린 문 착화 지연','s',60.,15.,300.),
 'ramp_s':('착화 후 상승 시간','s',60.,30.,300.),
 'closed_delay_s':('닫힌 일반문 관통 지연','s',600.,180.,1800.),
 'cell_temperature_C':('셀 간 기준 · 화원 위 판','℃',300.,200.,500.),
 'v_spread_m_s':('실내 화염 확산 속도','m/s',.05,.01,.2),
 'coverage_default':('전실 공급 연료 피복률','fraction',.5,.2,1.),
 'vent_cap_k':('수치 공급 상한 계수','',1.,.5,1.5)}
PRESETS={
 'standard':dict(temperature_C=600.,open_delay_s=60.,ramp_s=60.,closed_delay_s=600.,cell_temperature_C=300.,v_spread_m_s=.05),
 'conservative':dict(temperature_C=650.,open_delay_s=120.,ramp_s=120.,closed_delay_s=1200.,cell_temperature_C=400.,v_spread_m_s=.02),
 'aggressive':dict(temperature_C=500.,open_delay_s=30.,ramp_s=30.,closed_delay_s=300.,cell_temperature_C=250.,v_spread_m_s=.1)}
LABELS={'standard':'표준','conservative':'보수','aggressive':'공격'}
ASSUMPTION='허용 범위·프리셋·전이 규칙은 프로젝트 가정이며 문헌으로 검증된 기준 또는 발생확률이 아닙니다. 실간 기준은 상층 온도 자체가 아닌 T4b 판 온도입니다.'

def resolve(options=None):
 if options is None:options={}
 if not isinstance(options,dict):raise ValueError('r8 설정은 객체여야 합니다. 허용 프리셋: standard, conservative, aggressive')
 unknown=set(options)-set(FIELDS)-{'preset','room_supply'}
 if unknown:raise ValueError('지원하지 않는 r8 설정: '+', '.join(sorted(unknown)))
 preset=options.get('preset','standard');supply=options.get('room_supply','item_peak')
 if not isinstance(preset,str) or preset not in PRESETS:raise ValueError('프리셋 허용값: standard, conservative, aggressive')
 if not isinstance(supply,str) or supply not in ('item_peak','room_involvement'):raise ValueError('공급 방식 허용값: item_peak, room_involvement')
 defaults={k:v[2] for k,v in FIELDS.items()};defaults['vent_cap_k']=.7 if supply=='room_involvement' else 1.
 values={**defaults,**PRESETS[preset],**{k:v for k,v in options.items() if k in FIELDS}}
 records={}
 for key,value in values.items():
  label,unit,_,lo,hi=FIELDS[key]
  if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not lo<=value<=hi:
   raise ValueError(f'{label} ({key}): 허용 범위 {lo:g}~{hi:g} {unit}, 유한한 숫자를 입력하세요. 받은 값: {value!r}')
  records[key]={'value':value,'label':label,'unit':unit,'minimum':lo,'maximum':hi,
   'default_value':defaults[key],'is_default':value==defaults[key],
   'source':'user_override' if key in options else 'preset' if key in PRESETS[preset] and preset!='standard' else 'default',
   'applicable':key!='coverage_default' or supply=='room_involvement'}
 return {'revision':'room_rule_r8_frozen','frozen_structure':'r7','preset':preset,'preset_label':LABELS[preset],
   'room_supply':supply,'values':values,'parameters':records,'assumption':ASSUMPTION,
   'supply_is_default':supply=='item_peak'}

def schema():
 return {'fields':{k:{'label':v[0],'unit':v[1],'default':v[2],'minimum':v[3],'maximum':v[4]} for k,v in FIELDS.items()},
  'presets':deepcopy(PRESETS),'preset_labels':LABELS,'default_preset':'standard','default_supply':'item_peak',
  'supply_defaults':{'item_peak':{'vent_cap_k':1.},'room_involvement':{'vent_cap_k':.7}},'assumption':ASSUMPTION}

def comparison_options(options):
 """Exactly one alternate: aggressive timing/temperature, same supply/coverage/k.
 Custom overrides on the six preset fields do not leak into the alternate.
 """
 selected=resolve(options)
 return {'preset':'aggressive','room_supply':selected['room_supply'],
  'coverage_default':selected['values']['coverage_default'],'vent_cap_k':selected['values']['vent_cap_k']}
