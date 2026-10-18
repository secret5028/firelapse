"""Declared close-spaced fuel-package scenario, not calibrated building inventory."""
from pathlib import Path
import json,sys,math
from cfast_design_fire import interpolate
sys.path.insert(0,str(Path(__file__).resolve().parent/'cad-deps'))
from shapely.geometry import Polygon,Point,box
from shapely.ops import unary_union
p=Path(__file__).resolve().parent
design=json.loads((p/'cfast_nist_design_fire.json').read_text('utf8'))
curve=design['hrr_kW']
# Remove nominal initiating burner contribution instead of adding another burner.
ts=sorted({t for t,q in curve}|{199.999,200.0})
secondary=[[t,max(0,interpolate(curve,t)-(50 if t<200 else 0))] for t in ts]
assert len(secondary)<=200
preset=dict(preset_id='nist_paper_trigger_workstation',name='서류 표면으로 착화를 판단하는 작업대 묶음',
 description='서류 표면의 369°C 점화원 존재 조건으로 대표 가구 묶음의 지정 HRR을 시작하는 설계 시나리오. 묶음 내부의 개별 재료 연소를 예측한 것이 아님.',
 material=dict(id='NISTPAPER',conductivity_W_mK=.04184,density_kg_m3=500,specific_heat_kJ_kgK=2.092,thickness_m=.025,emissivity=.95),
 ignition=dict(criterion='TEMPERATURE',setpoint=369,unit='°C',pilot_assumed=True),
 growth=dict(hrr_kW=secondary,area_m2=5.95,base_height_m=0,heat_of_combustion_kJ_kg=18100,co_yield=.006171682,soot_yield=.015),
 evidence=dict(report='NCSTAR1-5C + SP1021',ignition_figure='A-16 printed p93 / PDF129',
  thermal_conversion='k=1e-4 cal/(cm s K)*418.4, rho=.50g/cm3*1000, cp=.50cal/(g K)*4.184',
  post_ignition_model='SP1021 Figure71 digitized HRR, nominal 50kW burner contribution removed before200s and clipped at0; time origin is conditional ignition',
  assumptions=['실제 재고가 아닌 밀집 가구 배치 시나리오; 점화원이 각 노출면에 존재한다고 가정',
   '북/남 서류 노출면 높이0.75/0.90m. 대칭 동시착화시 CFAST7.7.7의 IGN/HRR 불일치가 재현되어 서로 다른 높이의 배치를 선택; 엔진 수정이나 착화기준 변경은 하지 않음',
   '타깃은 서류 노출면, 화원은 묶음 중심. 서류 조건 충족 후 전체 묶음 지정 HRR 적용은 설계 가정이며 실제 내부 전이 검증 아님',
   '원 콘 시험의 후면 단열·수평 노출을 CFAST 양면 노출 PLATE로 근사. 작업실 타깃은 화원을 향한 수직 서류면',
   '가구 묶음 조성·CO/soot수율·연소열18.1MJ/kg·복사분율0.33은 기존 대리 가정',
   'R9만 CAD 경계 종횡비를 유지하는 등면적 직사각형 사용. 벽/문 도면 및 CAD 건물 높이 변경 없음',
   '다른 구획 화염의 직접 복사열과 문을 통한 국소 화염 접촉은 계산하지 않음; 다른 방은 구획 열환경으로만 착화 판단']),
 sources=[dict(url='https://nvlpubs.nist.gov/nistpubs/Legacy/NCSTAR/ncstar1-5c.pdf',use='그림A16 서류 열응답/369°C; 본문41쪽 서류의 초기 착화 역할'),
          dict(url='https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication1021.pdf',use='그림71 작업대 묶음 발열곡선'),
          dict(url='https://github.com/firemodels/cfast/blob/master/Manuals/CFAST_Users_Guide/Input_File_Chapter.tex',use='FIRE/TEMPERATURE/DEVC_ID 조건부 착화')])
(p/'cfast_spread_fuel_v26.json').write_text(json.dumps(preset,ensure_ascii=False,indent=2),'utf8')
targets=[]
for side,label in [(1,'북측'),(-1,'남측')]:
 targets.append(dict(id='WorkstationN' if side>0 else 'WorkstationS',name=label+' 별도 작업대 묶음',room_key='3F_R9',offset_xy_m=[0,side*2.6],target_offset_xy_m=[0,side*1.38],target_height_m=.75 if side>0 else .9,normal=[0,-side,0],width_m=2.44,depth_m=2.44))
d=json.loads((p.parent/'outputs/CAD-NIST가연물-v23/cfast-demo.json').read_text('utf8'))
for k,label in [('3F_R2','홀 가구 묶음'),('3F_R8','A/S실 가구 묶음')]:
 r=next(r for r in d['rooms'] if r['key']==k);poly=unary_union([Polygon(q['o'],q['h']) for q in r['polys']]);inside=poly.buffer(-1.75)
 assert not inside.is_empty
 pt=Point(r['c']) if inside.covers(Point(r['c'])) else inside.representative_point()
 x,y=pt.x,pt.y
 assert poly.covers(box(x-1.22,y-1.22,x+1.22,y+1.22))
 targets.append(dict(id='WorkstationHall' if k.endswith('R2') else 'WorkstationAS',name=label,room_key=k,position_xy_m=[x,y],solver_xy_m=[math.sqrt(r['area'])/2]*2,target_height_m=.75,normal=[0,0,1],width_m=2.44,depth_m=2.44,placement='CAD interior; equivalent compartment centre, upper-layer exposure'))
scenario=dict(defaults_file='cfast_spread_fuel_v26.json',evidence_based=True,preserve_aspect_rooms=['3F_R9'],
 description='3F 작업실에 최초1개+별도2개 작업대 묶음, 홀/A/S실에 각1개. 작업실 묶음 중심간2.6m, 등가 폭2.44m로 약0.16m 간격. 노출 서류면의 가열로 조건부 착화; 점화원 존재 가정. 문상태와 소화설비 미작동 조건은 v23과 동일.',targets=targets)
(p/'cfast_spread_scenario_v26.json').write_text(json.dumps(scenario,ensure_ascii=False,indent=2),'utf8')
print('Scenario prepared: primary +',len(targets),'conditional packages; criterion369C, primary unscaled')
