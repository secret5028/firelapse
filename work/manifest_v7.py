import pathlib,json
W=pathlib.Path(__file__).resolve().parent;I=W/'cad-v7-inventory'
rows=json.loads((I/'cad_inventory.json').read_text(encoding='utf8'))
for r in rows:
 num=int(r['name'].split('-')[1]);floor=f'{num-5}F' if 6<=num<=12 else {13:'ROOF',14:'PH',15:'B1'}[num]
 r.update(floor=floor,floors=[floor],role='roof_plan' if num==13 else 'architectural_plan',review='all_loaded_layers_geometry_scanned',revision='drawing_date_not_verified')
 if floor=='B1':r['secondary_views']=[dict(floor='1F',title='계단실#3 지상1층 평면도',status='inset_context_not_registered',note='주 평면과 다른 배치 좌표의 부분도; 1층 전체에 자동 합성하지 않음')]
pdf=json.loads((I/'pdf_inventory.json').read_text(encoding='utf8'))
titles=['도면목록표, 범례','장비일람표','소화배관 계통도','지하층 펌프실 소화배관 평면도','지하층 소화설비 평면도','도면목록표(소방)','소방범례 및 주기사항','소방설비 간선계통도(변경후)','지하1층 소방시설(전기) 평면도(변경전)','지하1층 소방간선(전기) 평면도(변경후)']
allfloors=['B1']+[f'{i}F' for i in range(1,8)]+['PH']
for i,title in enumerate(titles,1):
 rows.append(dict(name=pdf['name'],sha256=pdf['sha256'],page=i,title=title,role='raster_reference',
                  floors=['B1'] if i in (4,5,9,10) else allfloors if i in (3,8) else [],
                  review='visually_reviewed',registered=False,geometry_use=False,revision='before_change' if i==9 else 'after_change' if i in (8,10) else 'unspecified',
                  note='스캔 PDF. 좌표 정합 전에는 벽·문·감지기·유도등의 자동 확정 근거로 사용하지 않음'))
manifest=dict(building='28-200-2026-00000010',drawings=rows,
 coverage_note='확보된 건축 CAD 10장 및 소방 PDF 10쪽 확인. B1·1F~7F·PH 9개 층 추출. 지붕도는 참고도이며 실내 층으로 생성하지 않음. 별도 창호일람·입면·단면·1F~7F 소방 평면 원본은 이 폴더에서 확보되지 않음. B1 도면의 1F 계단실 부분도와 PDF는 좌표 미정합 참고자료로 기록. 범례와 계통도를 평면으로 겹치지 않음.')
(W/'drawing-manifest-v7.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
