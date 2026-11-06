"""Register prior models without modifying their source or simulation results."""
import hashlib,json,re,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OLD=Path('C:/Users/<user>/Documents/Codex/2026-09-07/2')
def read(p):return json.loads(p.read_text('utf8'))
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8')

def main():
    models=[]
    def add(id,label,source,kind,proof,operation=None,enabled=False,review_url=None,imported=None):
        path=source
        if imported is not None or not source.is_relative_to(ROOT):
            path=ROOT/'data/model-library'/id/'building.json';path.parent.mkdir(parents=True,exist_ok=True)
            if imported is None:shutil.copyfile(source,path)
            else:save(path,imported)
        b=read(path);floors=b.get('floors',[])
        note='기존 운영 화면에서 실행' if enabled else ('스캔 기반 · 개구부 미검증 · 시뮬레이션 금지' if kind=='scan' else '저장 모델 열람 · 계산 실행 연결 없음')
        models.append(dict(id=id,label=label,path=path.relative_to(ROOT).as_posix(),source_name=source.name,
            source_kind=kind,source_evidence=proof,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            original_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),floor_count=len(floors),
            room_count=sum(len(f.get('rooms',[])) for f in floors) if kind!='scan' else None,
            simulation_enabled=enabled,execution_note=note,operation_url=operation,review_url=review_url))
    add('ganghwa','강화 공장',ROOT/'simulation/results/github-publish-20261026/PyroCast/cad-project/building.json','cad','기존 CAD 운영 building.json','http://127.0.0.1:8780/model.html',True)
    add('parkmarine','파크마린호텔 · 보정본',ROOT/'data/parkmarine-hotel/building.json','cad','원본 DWG·층별 DXF 및 공리 보정 기록',review_url='http://127.0.0.1:8840/data/parkmarine-hotel/review.html')
    add('wando','완도 저온창고',ROOT/'data/wando-coldstore/operating-building.json','reconstructed','C11 자료·사진·명세 기반 재구성, 기존 입력/결과 보존','http://127.0.0.1:8832/data/wando-coldstore/model.html')
    for id,label,folder in [('showroom','견본주택 · 과거 CAD','28-710-2025-00000016')]:
        add(id,label,OLD/'CAD3D/out'/folder/'building.json','cad','층별 src .dxf 및 CAD3D 인계 기록')
    src=OLD/'output/model-trial/final-state.json';state=read(src)
    scan={'schema':'pyrocast.scan-view/1','model_provenance':{'source_kind':'scan','simulation_allowed':False},
          'floors':[dict(name=p.get('levelLabel',str(p['floor'])),scan_page=p,rooms=[]) for p in state['pages'] if p.get('included') and p.get('shapes')],
          'notes':['101동 2층 시범 모델만 저장됨. 2~22층 전체를 생성한 모델로 표시하지 않음.']}
    add('apartment-scan','강화 공동주택 101동 · 스캔 시범',src,'scan','test-result.json: PDF 194쪽, 텍스트층 0. final-state: 스캔 배경선 수동 근사 추적.',imported=scan)
    src=OLD/'tmp/new-drawing/result-with-heads.html';html=src.read_text('utf8')
    m=re.search(r'window.REVIEW_DATA\s*=\s*',html);d,_=json.JSONDecoder().raw_decode(html[m.end():])
    scan={'schema':'pyrocast.scan-view/1','model_provenance':{'source_kind':'scan','simulation_allowed':False},
          'floors':[dict(name=p['initial'].get('building','')+' '+p['initial'].get('levelLabel',str(p['initial'].get('floor'))),scan_page=p['initial'],rooms=[]) for p in d['pages'] if p.get('initial',{}).get('included') and p['initial'].get('shapes')],
          'notes':['저장된 이미지 판독 초기 형상·층고 가정을 열람용으로 사용. 개구부는 계산 입력으로 사용 금지.']}
    add('modori-scan','모도리 267 · 1~4동 스캔 판독',src,'scan','저장 REVIEW_DATA 이미지와 initial 수동 판독 형상. 원본 result-with-heads.html 보존.',imported=scan)
    for row in models:
        if row['id']=='showroom':
            prepared=ROOT/'data/model-library/showroom/prepared/building.json'
            if prepared.exists():
                row['path']=prepared.relative_to(ROOT).as_posix()
                row['sha256']=hashlib.sha256(prepared.read_bytes()).hexdigest()
        if row['id'] in ('parkmarine','showroom'):
            row.update(simulation_enabled=True,execution_mode='library_lite',
                       operation_url='http://127.0.0.1:'+str(8842 if row['id']=='parkmarine' else 8843)+'/model.html',
                       execution_note='검증된 층에서 간략 시뮬레이션 · 화점·급기 선택')
        elif row['id']=='wando':
            row['execution_note']='완도 공동·절단·배풍기 전용 CFAST 입력: 기존 P1~P5 결과 보기 (일반 CAD 계산 대상 아님)'
    save(ROOT/'config/model-library.json',{'schema':'pyrocast.model-library/1','models':models})
    print(json.dumps([{k:e[k] for k in ('id','label','floor_count','room_count','source_kind','simulation_enabled')} for e in models],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
