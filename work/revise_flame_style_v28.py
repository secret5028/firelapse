from pathlib import Path
import shutil

root = Path(__file__).resolve().parent.parent
backup = root / 'outputs/CAD-연소표현-v28/수정전-긴불꽃'
backup.mkdir(exist_ok=True)
for name in ['cad_cfast_combustion.js', 'cad_cfast_realistic.js', 'cad_cfast_multifloor_overlay.js']:
    src = root / 'work' / name
    if not (backup/name).exists():
        shutil.copy2(src, backup/name)

p = root/'work/cad_cfast_combustion.js'
s = p.read_text(encoding='utf8')
start = s.index(' const vertex=')
end = s.index(' const jetObjects=', start)
s = s[:start]+s[end:]
start = s.index('  if(j.anchor){for(')
end = s.index('jetObjects.push', start)
s = s[:start]+'  '+s[end:]
start = s.index('  animate(now){')
end = s.index('  stats(){', start)
s = s[:start]+'  animate(){},\n'+s[end:]
s = s.replace('active&&!s.realView','active')
s = s.replace('기본: 구획별 계산값 · 실감: 문 주변 불꽃 형상은 연출','개구부 연소: 구획별 계산값 · 화염: 기존 화점의 크기·패턴 변화')
s = s.replace("${s.realView&&e.j.anchor?' / '+e.j.anchor.vent_id+' 위치 연출':''}", '')
s = s.replace('illustrative:s.realView','illustrative:false')
p.write_text(s,encoding='utf8')

p = root/'work/cad_cfast_realistic.js'
s = p.read_text(encoding='utf8')
start=s.index(' float z=p.z;vec3 npos=')
end=s.index(' float d=max(0.,body)',start)
s=s[:start]+''' // Three variations of the original compact flame; no detached ribbons.
 float variant=mod(floor(uPhase/2.17+.1),3.);
 float speed=mix(2.8,2.3+variant*.55,uStyle);
 float z=p.z;vec3 npos=vec3(p.xy*(5.+uStyle*variant*.6),z*5.-uTime*speed+uPhase);float n=billow(npos);
 vec2 drift=vec2(sin(z*8.-uTime*(2.+variant*.15)+uPhase),cos(z*9.-uTime*2.3+uPhase))*.07*z;
 float radius=length((p.xy-.5+drift)*2.);float width=.8*pow(max(.001,1.-z),.75+uStyle*(variant-1.)*.12);
 float body=1.-radius/max(.01,width)+(n-.5)*(1.1+uStyle*variant*.12);
'''+s[end:]
s=s.replace('function sizeFlame(e){','function sizeFlame(e,now=0){')
s=s.replace('const h=Math.min(e.maxHeight,Math.max(e.physicalHeight,metresPerPixel*32));', '''const phase=flame.material.uniforms.uPhase.value,variant=Math.round(phase/2.17)%3;
   const pulse=state?.realView?1+.07*Math.sin(now*.003+phase)+.035*Math.sin(now*.007+phase*2):1;
   const h=Math.min(e.maxHeight,Math.max(e.physicalHeight,metresPerPixel*32)*(state?.realView?[1,.88,1.12][variant]:1)*pulse);''')
s=s.replace('const width=Math.max(.3,footprint,Math.min(2,e.physicalHeight*.62),metresPerPixel*22);','const width=Math.max(.3,footprint,Math.min(2,e.physicalHeight*.62),metresPerPixel*22)*(state?.realView?[1,1.12,.9][variant]:1)*(2-pulse);')
s=s.replace('sizeFlame(e);updateMesh(e.flame,now)','sizeFlame(e,now);updateMesh(e.flame,now)')
p.write_text(s,encoding='utf8')

p=root/'work/cad_cfast_multifloor_overlay.js'
s=p.read_text(encoding='utf8').replace('실감 연출 · 계산된 연소 시점과 발열량에 맞춰 불꽃을 펼칩니다. 문·천장 방향 퍼짐, 갈라짐·색·흔들림은 연출이며 실제 화염 경로 예측이나 새 가구 착화가 아닙니다. 화염은 연기 너머로 표시합니다.','실감 보기 · 기존 화염의 크기와 일렁임을 여러 패턴으로 표시합니다. 크기 변화·흔들림은 시각 효과이며, 착화 여부와 발열량은 계산값을 따릅니다. 화염은 연기 너머로 표시합니다.')
p.write_text(s,encoding='utf8')
