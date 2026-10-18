"""One-time v21 -> v22 UI migration; rebuild with restore_cad_ui.py afterwards."""
from pathlib import Path
p=Path(__file__).with_name('cad_cfast_multifloor_overlay.js')
s=p.read_text('utf8')
s=s.replace('표시 효과입니다。各 구획', '표시 효과입니다. 각 구획')
anchor=" for(const text of data.assumptions)"
insert=""" const hasSecondary=(data.fires||[]).some(f=>f.id!=='ExampleFire');$('cfIgnitionSection').hidden=!hasSecondary;
 const design=data.design_fire;$('cfDesign').hidden=!design;
 if(design){
  $('cfDesignText').textContent=`최대 ${design.peak_kW} kW · ${design.growth_seconds/60}분 t² 성장 · ${design.steady_seconds/60}분 유지 · 감쇠 ${design.decay_seconds/60}분. 화원 ${design.area_m2} m². 입력 열량 ${design.prescribed_energy_MJ.toFixed(1)} MJ / 환산 연료 ${design.equivalent_fuel_kg.toFixed(1)} kg. 비교용 가정이며 건물 평균 화재하중이 아닙니다.`;
  $('cfScenarioScope').textContent=hasSecondary?'실험용 추가 착화 설정 활성화':'기본: 지정 화재의 열·연기 전이. 다른 가연물의 착화는 미계산이며, 미착화 판정이 아닙니다.';
  const ns='http://www.w3.org/2000/svg',chart=$('cfHrrChart'),input=data.prescribed_hrr||data.hrr,actual=data.total_hrr||data.hrr,max=Math.max(1,...input,...actual);
  for(const [values,color] of [[input,'#e4bd65'],[actual,'#69c8ff']]){const line=document.createElementNS(ns,'polyline');line.setAttribute('points',values.map((v,i)=>`${25+250*i/(values.length-1)},${83-70*v/max}`).join(' '));line.setAttribute('stroke',color);line.setAttribute('fill','none');line.setAttribute('stroke-width','2');if(color==='#69c8ff')line.setAttribute('stroke-dasharray','5 3');chart.append(line)}
  for(const [x,y,value] of [[0,12,Math.round(max)],[10,85,0],[25,98,'0分'.replace('分','분')],[240,98,`${data.duration/60}분`]]){const text=document.createElementNS(ns,'text');text.setAttribute('x',x);text.setAttribute('y',y);text.setAttribute('fill','#c3d2df');text.setAttribute('font-size','10');text.textContent=value;chart.append(text)}
 }
"""
assert anchor in s
s=s.replace(anchor,insert+anchor,1)
s=s.replace('<span>최초 화점 1 MW + 조건부 2차 착화</span>', '<span>${hasSecondary?\'지정 화재 + 실험용 추가 착화\':\'지정 화재 · 추가 착화 미계산\'}</span>')
s=s.replace("realView?'갈색 상자: 기본 가연물 / 주황 고리: 현재 연소 위치. 입체 연기는 계산된 층 높이·농도에 연동. 화염은 착화한 가연물 위치에 표시. 연기 결·흔들림은 시각 효과입니다.':", "realView?(hasSecondary?'갈색 상자: 예시 가연물 / 주황 고리: 연소 위치. 조건부 착화 계산. 연기 결·불꽃 흔들림은 시각 효과입니다.':'지정 화점의 화염과 구획별 연기층을 표시합니다. 다른 방의 추가 착화는 미계산입니다. 연기 결·불꽃 흔들림은 시각 효과입니다.'):")
s=s.replace("duration:data.duration,smokeRooms", "calculationMode:data.calculation_mode,duration:data.duration,smokeRooms")
p.write_text(s,'utf8')
