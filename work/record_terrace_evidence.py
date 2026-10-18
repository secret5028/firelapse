from pathlib import Path
import json
p=Path('work/cad-web/cad_engine/cad_model_transport.py')
s=p.read_text('utf8');start=s.index('def apply_outdoor_semantics(');end=s.index('def prepare_model(',start);s=s[:start]+s[end:]
s=s.replace("        apply_outdoor_semantics(f,plan)\n",'')
s=s.replace("        sky=unary_union([geometry(t['open_sky_polys']) for t in f.get('outdoor_spaces',[])])\n        covered=geometry(f['slab']).difference(sky)\n        exposed=covered", "        exposed=geometry(f['slab'])")
s=s.replace("ceiling_polys=parts(covered.difference(","ceiling_polys=parts(geometry(f['slab']).difference(")
p.write_text(s,'utf8')
out=Path('outputs/CAD-테라스-v13')
(out/'상태-미적용.txt').write_text('미적용 검토 초안. 실제 앱은 v12 유지.\n3F 원본 CAD 문자 368개 및 레이어명 검토: 테라스·발코니·난간 직접 표기 없음. 휴게실 문자는 다른 위치.\n곡선 경계 일부는 WINE 레이어이며 현재 추출 창 W0의 일부에 포함. 레이어명만으로 실내 창/테라스 난간을 확정할 수 없음.\n이 폴더의 building.json과 cad_model_transport.py는 사용자 형태 해석을 적용해 본 초안이며 도면으로 확인된 정답 또는 설치본이 아님. 작업 소스도 v12로 복원함.\n1.1m는 표시용 가정이며 도면 측정값이 아님.\n','utf8')
record=Path('outputs/작업기준-복구-20261014.txt')
text=record.read_text('utf8')
record.write_text('최신 확인 — 3F 돌출부 용도 (2026-10-14)\n- 사용자 질문: 도면에 테라스라는 정보가 있었나? 3F DXF 문자 368개와 레이어명에서 테라스/발코니/난간 직접 표기를 찾지 못했다. 형태에 따른 해석과 도면 명시를 구분한다.\n- CAD-테라스-v13은 미적용 검토 초안. 실제 앱/작업 소스는 v12 유지. 돌출 곡선 일부 WINE 레이어를 테라스로 확정하거나 1.1m를 실측값으로 취급하지 않는다.\n\n'+text,'utf8')
print('working source equals installed:',p.read_bytes()==Path('C:/Users/예방/Desktop/소방 크로키 업-로컬웹앱/_internal/cad_engine/cad_model_transport.py').read_bytes())
