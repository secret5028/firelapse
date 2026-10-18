from pathlib import Path
import json,math
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'outputs/CAD-가연물묶음-v30'
cases={'기존 v27':ROOT/'outputs/CAD-속도검증-v27/final/cfast-demo.json','배치만 변경':OUT/'placement-only/cfast-demo.json','배치 + 반자고':OUT/'ceiling/cfast-demo.json'}
data={k:json.loads(p.read_text('utf8')) for k,p in cases.items()}
def integral(values,dt=5):return sum((a+b)*dt/2 for a,b in zip(values,values[1:]))/1000
def summarize(d):
 rooms={r['key']:r for r in d['rooms']};o={}
 for k in ['3F_R9','3F_R2','3F_R8']:
  r=rooms[k];s=r['series'];fs=[f for f in d['fires'] if f['room_key']==k and 'target_series' in f]
  o[k]=dict(height_m=r['height'],upper_peak_C=max(x[1] for x in s),lower_peak_C=max(x[2] for x in s),min_layer_m=min(x[3] for x in s),
   observer_1_5m_peak_C=max(x[1] if 1.5>=x[3] else x[2] for x in s),
   observer_1_5m_peak_OD=max(x[4] if 1.5>=x[3] else x[5] for x in s),
   smoke_first_s=next((x[0] for x in s if max(x[4:])>=.001),None),
   targets=[dict(id=f['id'],ignition_s=f['ignition_time'],surface_peak_C=max(x[1] for x in f['target_series']),radiation_peak_kW_m2=max(x[2] for x in f['target_series'])) for f in fs])
 floor={fn:dict(smoke_rooms_at_30min=sum(max(r['series'][-1][4:])>=.001 for r in d['rooms'] if r['floor']==fn),first_smoke_s=min((x[0] for r in d['rooms'] if r['floor']==fn for x in r['series'] if max(x[4:])>=.001),default=None)) for fn in d['floors']}
 return dict(rooms=o,floors=floor,peak_total_hrr_kW=max(d['total_hrr']),actual_30min_energy_MJ=integral(d['total_hrr']),elapsed_seconds=d['elapsed_seconds'],ignitions=[dict(id=f['id'],time=f['ignition_time']) for f in d['fires'] if f['id']!='ExampleFire'])
summary={k:summarize(d) for k,d in data.items()}
baseline=data['기존 v27'];new=data['배치만 변경'];oldrooms={r['key']:r for r in baseline['rooms']}
delta={name:max(abs(a[idx]-b[idx]) for r in new['rooms'] for a,b in zip(oldrooms[r['key']]['series'],r['series'])) for name,idx in [('upper_C',1),('lower_C',2),('interface_m',3),('upper_OD',4),('lower_OD',5)]}
report=dict(cases=summary,placement_vs_baseline_max_absolute_difference=delta,notes=['30분 저장 출력 비교. 런타임은 두 실행 일부 병행으로 성능 비교용이 아님.','반자고 사례는 전층 실별 높이를 변경. 최초 화재실, 홀, A/S는 도면 표기 3.0m.','총 지정 곡선·환산 연료량 보존. 실제 방출 열량은 산소/착화 시점에 따라 달라짐.','다른 실 직접 화원복사·문 근처 국소 화염 접촉은 여전히 미계산.','원격 병합실은 체적을 보존하는 평균 높이로 계산. 경계 열물성은 기존 대리 콘크리트 유지.'])
(OUT/'기존대비-비교.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
lines=['가연물 단위 격자·대표 묶음·반자고 비교 v30','',*report['notes'],'', '보존 검증: 총 지정 곡선 7887.644669 MJ / 환산 연료 435.781473 kg. 실측 재고량 아님.','']
for name,s in summary.items():
 lines += [name, f"최대 총 HRR {s['peak_total_hrr_kW']:.2f} kW / 실제 30분 열량 {s['actual_30min_energy_MJ']:.2f} MJ / 실행 {s['elapsed_seconds']:.2f}초"]
 for k,r in s['rooms'].items():
  lines.append(f"{k}: 계산높이 {r['height_m']:.2f}m / 상부 최고 {r['upper_peak_C']:.2f}°C / 최저 층경계 {r['min_layer_m']:.3f}m / 1.5m 최고 {r['observer_1_5m_peak_C']:.2f}°C, OD {r['observer_1_5m_peak_OD']:.4f}/m")
  for t in r['targets']:lines.append(f"  {t['id']}: 표면 최고 {t['surface_peak_C']:.2f}°C / 입사복사 최고 {t['radiation_peak_kW_m2']:.3f}kW/m² / 착화 {t['ignition_s']}초")
 lines.append('층별 연기 표시: '+json.dumps(s['floors'],ensure_ascii=False));lines.append('')
lines+=['배치만 변경 vs 기존 전체 시계열 최대 차이',json.dumps(delta,ensure_ascii=False),'','가구 표시: 20개 단위(책상 0.75m, 수납장 1.2/1.8m), 최초 포함 대표 화원 7개.','R9 기존 세 화원 위치/곡선 유지; 홀과 A/S 각 재고를 문 근처/안쪽 50%씩 분배. 각 시각 단위는 대표 묶음의 에너지·질량 지분을 가지며 독립 착화 계산 아님.','실별 높이 근거: 반자고-도면대조.json. 태그 미확인 실은 같은 건물 3.0m·위생실2.4m 추정, 수직 동선/기계실 등은 구조 높이.','미해결: 실제 연료 재고/물성·점화원 가정, R9 근접 판정면 가정, 반자 재료의 열응답, 미세 국소 전파. 강제 착화/엔진 변경 없음.']
(OUT/'비교결과.txt').write_text('\n'.join(lines),'utf8')
from html import escape
headers=''.join('<th>'+escape(n)+'</th>' for n in summary)
metrics=[('3층 화재실 계산 높이 (m)',lambda s:s['rooms']['3F_R9']['height_m']),('화재실 상부 최고 (°C)',lambda s:s['rooms']['3F_R9']['upper_peak_C']),('홀 상부 최고 (°C)',lambda s:s['rooms']['3F_R2']['upper_peak_C']),('홀 가연물 표면 최고 (°C)',lambda s:max(t['surface_peak_C'] for t in s['rooms']['3F_R2']['targets'])),('A/S 가연물 표면 최고 (°C)',lambda s:max(t['surface_peak_C'] for t in s['rooms']['3F_R8']['targets'])),('홀 최저 연기층 경계 (m)',lambda s:s['rooms']['3F_R2']['min_layer_m']),('최대 총 HRR (kW)',lambda s:s['peak_total_hrr_kW']),('실제 30분 방출 열량 (MJ)',lambda s:s['actual_30min_energy_MJ'])]
trs=''.join('<tr><th>'+label+'</th>'+''.join(f'<td>{fn(s):,.2f}</td>' for s in summary.values())+'</tr>' for label,fn in metrics)
html='''<!doctype html><meta charset="utf-8"><title>가연물 묶음·반자고 비교 v30</title><style>body{font:16px/1.65 system-ui,Malgun Gothic;background:#eef2f5;color:#173044;margin:0}main{max-width:1100px;margin:auto;background:white;padding:36px}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}th,td{border-bottom:1px solid #d6dfe4;padding:10px;text-align:right}th:first-child{text-align:left}img{max-width:100%;border:1px solid #dde3e8}h1{font-size:28px}.note{background:#eef4f7;padding:18px}a{color:#225f9a}</style><main><h1>가연물 단위 격자·대표 묶음·반자고 비교</h1><p>같은 건물과 CFAST 7.7.7 원 엔진으로 30분 계산. 기존 조건 → 배치만 변경 → 배치와 실별 반자고 변경을 비교했습니다.</p><p class="note">지정 열량 <b>7,887.64 MJ</b>와 환산 연료 <b>435.78 kg</b> 보존. 이 값은 시나리오의 화재곡선에서 환산한 양입니다. 실제 30분 방출량은 착화 시점과 산소 조건에 따라 달라집니다.</p><table><tr><th>비교 항목</th>'''+headers+'</tr>'+trs+'''</table><p>가연물 표면의 착화 기준은 기존 369°C를 유지했습니다. 표면 최고값은 해당 실 대표 대상 중 최댓값입니다. 문 근처는 CAD상 배치 구분이며, 문을 통과하는 국소 화염 접촉을 새로 계산한 것은 아닙니다.</p><h2>도면 반자고 근거</h2><img src="3층-원본-반자고표기.png" alt="원본 CAD: A/S실 315 / 3000, 공작실·설비보관실 316 / 3000"><p>3층 두 실과 홀은 3.0m 표기를 적용했습니다. 표기가 없는 실은 같은 건물의 용도별 값을 추정 적용했습니다. 계단·승강로·램프 연결 공간은 구조 높이를 유지합니다. 반자 경계의 열물성은 비교를 위해 기존 콘크리트 대리값을 유지했습니다.</p><h2>가연물 단위와 계산의 연결</h2><p>표시 단위 20개 → 대표 화원 7개. 기존 화재실 세 묶음은 유지하고, 홀과 A/S의 재고를 각각 문 근처·안쪽에 50%씩 나눴습니다. 단위별 폭·깊이·높이·열량 지분·환산 질량·대표 화원 ID를 저장했습니다. 가구 외형은 책상 0.75m, 수납장 1.2/1.8m이며 실측 재고가 아닙니다. 착화 판정면 높이는 별도 입력입니다.</p><p><a href="비교결과.txt">상세 비교</a> · <a href="기존대비-비교.json">시계열 요약</a> · <a href="반자고-도면대조.json">실별 높이 근거</a> · <a href="검증결과.json">입력 보존·출력 검사</a></p></main>'''
(OUT/'비교보고서.html').write_text(html,'utf8')
print(json.dumps(report,ensure_ascii=False))
