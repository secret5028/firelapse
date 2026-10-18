from pathlib import Path
p=Path('work/app.js');s=p.read_text(encoding='utf-8')
a=s.index('for(const [x,z] of [[.55,10.5]');b=s.index('const tex=',a)
s=s[:a]+'''// D동 20/21쪽의 AV 기호와 범례로 확인되는 기계설비만 표시.
const mechanicalColor={hydrant:'#e94653',alarmValve:'#e94653'};
const eg=new THREE.Group();g.add(eg);
const valveInfo={name:'알람밸브 (AV) · '+f+'층',body:(f===1?'20':'21')+'쪽 평면도의 AV 기호와 알람밸브 범례를 근거로 표시했습니다. 위치는 근사이며 표식은 실제 외형·높이를 뜻하지 않습니다. 배관과 공급 구역은 표시하지 않습니다.'};
box(eg,31.0,H*(f-1)+.5,12.55,.42,.7,.35,mat(mechanicalColor.alarmValve),valveInfo);
label(eg,'AV · 알람밸브',31.0,H*(f-1)+1.6,12.55,'#ff8b92',.72);equipMeshes.push(eg);
''' + s[b:]
s=s.replace("known?'#ffc45f':'#e59e51'", "known?'#f45b62':'#be656a'").replace('노란 문짝','적색 문짝')
s=s.replace('camera.lookAt(target);const n=', 'camera.lookAt(target);camera.updateMatrixWorld(true);const n=')
s=s.replace('cam.theta=.15;', 'cam.theta=0;').replace('cam.theta=.7;', 'cam.theta=-Math.PI/4;')
p.write_text(s,encoding='utf-8')
p=Path('work/viewer.html');s=p.read_text(encoding='utf-8')
s=s.replace('소화전 위치 단서','도면에 표시된 기계설비').replace('background:#ffc45f','background:#f45b62').replace('노란 문짝','적색 문짝')
s=s.replace('표시된 소화전 후보는 전기도면의 ‘소화전 상부 수동발신기 세트’ 위치 단서입니다.','표시 항목: D동 1·2층 알람밸브(AV). 소화전은 직접 확인되지 않아 표시하지 않습니다.')
s=s.replace('설비 후보 표식은 소화전 상부 발신기 표기를 근거로 한 위치 단서입니다. 소화전 사양·송수구·배관 연결을 확정하지 않았습니다.','기계설비는 20·21쪽의 AV 기호와 범례로 확인한 알람밸브만 표시합니다. 발신기를 소화전으로 대체하지 않습니다. 확인된 소화전을 추가할 경우 적색 계열로 표시합니다.')
s=s.replace('<p><b>회전 중심:</b>', '<p><b>시점 복원:</b> 전체 배치와 D동 상세 모두 도면의 정북 방향이 화면 위를 향하도록 복원합니다.</p><p><b>회전 중심:</b>')
p.write_text(s,encoding='utf-8')
print('North-up reset; removed inferred hydrants; AV-only mechanical markers; red door/equipment palette.')
