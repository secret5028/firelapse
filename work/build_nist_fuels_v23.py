"""Traceable PDF-vector digitization, not original instrument CSV."""
from pathlib import Path
from pypdf import PdfReader
from pypdf.generic import ContentStream
from collections import defaultdict
import json, hashlib, csv, bisect
root=Path(__file__).resolve().parent
src=root/'nist-fuels'
pdf=PdfReader(src/'SP1021.pdf'); page=pdf.pages[58]
ops=ContentStream(page.get_contents(),pdf).operations
red=False; groups=defaultdict(list)
for i,(v,op) in enumerate(ops):
    if op==b'SCN':red=len(v)==3 and float(v[0])>.8 and float(v[1])<.1
    if red and op==b'm' and [o for a,o in ops[i+1:i+6]]==[b'c']*4+[b'h']:
        x,y=float(ops[i+1][0][4]),float(v[1])
        if 490<y<700:
            groups[x].append(max(0,(y-495.66)/(698.94-495.66)*3500))
raw=[[round((x-162)/(401.88-162)*1800,6),sum(q)/len(q)] for x,q in sorted(groups.items())]
raw.append([1800,raw[-1][1]])
assert 3250<max(q for t,q in raw)<3350
# Keep the largest deviations first; preserves extrema and integral, <=200 table rows.
keep={0,len(raw)-1,max(range(len(raw)),key=lambda i:raw[i][1])}
while len(keep)<190:
    best=(-1,None)
    for a,b in zip(sorted(keep),sorted(keep)[1:]):
        for j in range(a+1,b):
            y=raw[a][1]+(raw[b][1]-raw[a][1])*(raw[j][0]-raw[a][0])/(raw[b][0]-raw[a][0])
            err=abs(raw[j][1]-y)
            if err>best[0]:best=(err,j)
    if best[1] is None or best[0]<10:break
    keep.add(best[1])
curve=[[round(raw[i][0],6),round(raw[i][1],6)] for i in sorted(keep)]
energy=lambda a:sum((b[0]-c[0])*(b[1]+c[1])/2000 for c,b in zip(a,a[1:]))
assert abs(energy(curve)/energy(raw)-1)<.01
with (src/'SP1021-figure71-digitized.csv').open('w',newline='',encoding='utf8') as f:
    w=csv.writer(f);w.writerow(['time_s','HRR_kW']);w.writerows(raw)
manifest=dict(source='NIST SP 1021, Figure 71, printed p54 / PDF p59',
    url='https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication1021.pdf',
    pdf_sha256=hashlib.sha256((src/'SP1021.pdf').read_bytes()).hexdigest(),method='red vector circle centres; duplicate x averaged; largest-error piecewise-linear reduction',
    axes_pdf_points=dict(x0=162,x1800=401.88,y0=495.66,y3500=698.94),
    raw_points=len(raw),input_points=len(curve),raw_energy_MJ=energy(raw),input_energy_MJ=energy(curve),
    energy_relative_error=energy(curve)/energy(raw)-1,peak_kW=max(q for t,q in raw),
    peak_time_s=max(raw,key=lambda p:p[1])[0],last_point_extension_s=1800-raw[-2][0],
    note='Figure digitization; not original measurement CSV. No amplitude multiplication or duration stretching. Original 50kW/200s igniter included in measured package; no second igniter added.')
(src/'SP1021-digitization.json').write_text(json.dumps(manifest,indent=2),'utf8')
design=dict(id='NIST_SP1021_workstation',name='NIST 작업대·컴퓨터·의자·서류 묶음',curve_type='tabulated',
    basis='NIST SP1021 그림71의 실측 발열곡선을 PDF 벡터 좌표에서 복원. 원 계측 CSV가 아닌 도표 수치화. 개방 연소시험을 이 건물에 옮긴 대표 시나리오.',
    peak_kW=max(q for t,q in curve),hrr_kW=curve,max_duration_seconds=1800,area_m2=5.95,base_height_m=0,
    heat_of_combustion_kJ_kg=18100,radiative_fraction=.33,formula={'CARBON':6,'HYDROGEN':10,'OXYGEN':5},co_yield=.006171682,soot_yield=.015,
    footprint_m=[2.44,2.44],height_m=1.04,
    fuel_basis='복합 시험체 전체 질량273.2kg에는 금속 등 비가연물이 포함. 연소열18.1MJ/kg·조성·CO/soot수율·복사분율0.33은 기존 대리연료 가정이며 이 실험의 측정값이 아님. 화원면적5.95m²는 시험 플랫폼의 등가 면적.',
    evidence=manifest,sources=[manifest['url']],secondary_ignition='explicit_targets')
(root/'cfast_nist_design_fire.json').write_text(json.dumps(design,ensure_ascii=False,indent=2),'utf8')
# Appendix A-2: desk at 45 kW/m2, total 212MJ/m2, whole-burn mean duration1739s.
# Square-wave equivalent is explicitly described in that report; it is not a full-scale desk HRR trace.
area=1.2;burn=1739.;q=212000*area/(burn+.0005)
preset=dict(preset_id='nist_ncstar_desk_A13',name='NIST 시험 책상 상판 대리재료',
    description='NCSTAR1-5C 표A-2·그림A-13의 점화원 존재 조건: 407°C. 1차원 열응답 보정 물성 사용. 실제 건물의 모든 목재 공통값이나 자연발화 온도가 아님.',
    material=dict(id='NISTDESK',conductivity_W_mK=.100416,density_kg_m3=700,specific_heat_kJ_kgK=5.8576,thickness_m=.028,emissivity=.95),
    ignition=dict(criterion='TEMPERATURE',setpoint=407,unit='°C',pilot_assumed=True),
    growth=dict(hrr_kW=[[0,q],[burn,q],[burn+.001,0],[3600,0]],area_m2=area,base_height_m=.75,
        heat_of_combustion_kJ_kg=14000,co_yield=.006171682,soot_yield=.015),
    evidence=dict(report='NIST NCSTAR1-5C',table='A-2 printed p73',ignition_figure='A-13 printed p91',
        ignition_uncertainty_C=10,ignition_basis='piloted cone tests; effective 1D conduction fit; not full-scale CFAST validation',
        thermal_conversion='k:2.4e-4 cal/(cm s K)*418.4; rho:0.70g/cm3*1000; cp:1.4cal/(g K)*4.184kJ/(kg K)',
        reference_flux_kW_m2=45,total_energy_MJ_m2=212,energy_uncertainty_MJ_m2=4.3,mean_burn_duration_s=1739,
        post_ignition_model='square-wave whole-burn equivalent at the 45kW/m2 test exposure; prescribed after ignition, not dynamically responding to changing exposure',
        assumptions=['상판 면적1.2m²·높이0.75m·위치는 시나리오 가정','점화원 존재 가정','원 시험 후면은 단열. CFAST는 양면 노출 PLATE로 근사하므로 시험 열경계의 정확한 재현이 아님','CO/soot 수율은 실측되지 않은 대리값']),
    sources=[dict(url='https://nvlpubs.nist.gov/nistpubs/Legacy/NCSTAR/ncstar1-5c.pdf',use='표A-2 및 그림A-13: 열응답, 점화조건, 연소열, 평균연소와 총열량')])
(root/'cfast_nist_desk.json').write_text(json.dumps(preset,ensure_ascii=False,indent=2),'utf8')
scenario=dict(description='작업실과 인접 A/S실에 별도 목재 상판을 놓은 비교 시나리오. 위치·수량은 현장 조사값 아님. 최초 작업대 묶음에 이미 포함된 가구를 중복 계상하지 않음.',
    defaults_file='cfast_nist_desk.json',evidence_based=True,targets=[
        dict(id='DeskA',name='별도 작업대 상판 A',room_key='3F_R9',offset_xy_m=[0,2.8],target_height_m=.75,normal=[0,0,1],width_m=2,depth_m=.6,back='CFAST_TWO_SIDED'),
        dict(id='DeskB',name='A/S실 별도 상판 B',room_key='3F_R8',offset_xy_m=[0,0],target_height_m=.75,normal=[0,0,1],width_m=2,depth_m=.6,back='CFAST_TWO_SIDED')])
(root/'cfast_nist_ignition.json').write_text(json.dumps(scenario,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(manifest));print('secondary HRR',q,'energy',energy(preset['growth']['hrr_kW']))
