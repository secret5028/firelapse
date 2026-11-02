"""Convert saved P1 output only; never imports or calls a simulation runner."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'simulation'), str(ROOT/'simulation/deps')]
from pyrocast_cfbt.native import read_native_csv
from pyrocast_cfbt.conditions import fo_required_hrr
from pyrocast_cfbt.fo_hrr import apply_fo_hrr, REVISION
from copy import deepcopy

DATA = ROOT/'data/wando-coldstore'
SRC = ROOT/'simulation/results/wando_C11_P1_20261102'

def read(p): return json.loads(p.read_text(encoding='utf-8'))
def write(p,v): p.write_text(json.dumps(v,ensure_ascii=False,allow_nan=False),encoding='utf-8')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    original=read(DATA/'building.json'); floor=original['floors'][0]
    building={'building_id':'wando-coldstore','name':'완도 저온창고','floors':[],
              'core_nodes':[],'vertical_connections':[],'obstacles':original.get('obstacles',[]),
              'route_entry_id':'CAD_1F_ENTRY_R5',
              'route_targets':{'CAD_1F_R5':[46.75,17.95,0]}}
    rooms=[]
    for r in floor['rooms']:
        poly=r['polygon_m']; xs=[p[0] for p in poly];ys=[p[1] for p in poly]
        rooms.append(dict(id=r['room_id'],names=[r['name']],c=[(min(xs)+max(xs))/2,(min(ys)+max(ys))/2],
                          polys=[{'o':poly,'h':r.get('holes_m',[])}],tags=[]))
    rooms.append(dict(id='CAVITY',names=['강판 뒤 공동 (0.1 m)'],c=[49.375,18.05],
                      polys=[{'o':[[45,18],[53.75,18],[53.75,18.1],[45,18.1]],'h':[]}],tags=[]))
    ops=[];connections=[]
    for r in rooms[:-1]:
        v=next(v for v in floor['openings'] if v['a']==r['id'])
        x,y=v['center_m'][:2];w=v['width_m'];ident='ENTRY_'+r['id']
        ops.append(dict(id=ident,kind='door',connection_status='exterior',door_h=v['soffit_m'],
                        leaves=[{'hinge':[x-w/2,y],'closed':[x+w/2,y]}],polys=[],display_frame=True))
        connections.append(dict(id=ident,kind='door',sides=[r['id'],'OUTSIDE'],boundary='exterior',dimensions={'area_m2':w*v['soffit_m']}))
    ops.append(dict(id='CUT',kind='door',connection_status='interior',door_h=2.5,sill_m=.5,
                    leaves=[{'hinge':[45.75,18],'closed':[47.75,18]}],polys=[],
                    display_schedule=[[0,0],[1320,.5],[1800,1]],display_label='절단 개구'))
    # The cavity is not a person-accessible route. Its thermal openings are
    # preserved in playback, never promoted into hose/person passage edges.
    building['floors']=[dict(name='1F',z=0,h=6.405,rooms=rooms,openings=ops,
        slab=[{'o':[[0,0],[72,0],[72,23.9],[0,23.9]],'h':[]}],
        simulation_graph={'connections':connections})]
    write(DATA/'operating-building.json',building); bsha=sha(DATA/'operating-building.json')
    c,_,cu=read_native_csv(SRC/'case_compartments.csv')
    z,_,zu=read_native_csv(SRC/'case_zone.csv')
    v,vid,_=read_native_csv(SRC/'case_vents.csv')
    saved=read(SRC/'timeseries.json');scores=read(SRC/'condition-scores.json');model=read(SRC/'model.json')
    times=c['Time'].tolist();assert len(times)==len(z['Time']) and times[-1]==3595
    assert max(abs(a-b) for a,b in zip(times,z['Time']))<1e-7
    # Retain exact native time separately; labels snap floating-point solver
    # print noise (<0.0001 s) to the requested five-second output grid.
    grid=[round(t/5)*5 for t in times];assert max(abs(a-b) for a,b in zip(times,grid))<.001
    mapped=[];solvers={}
    for i,(native,cad) in enumerate([('ROOM','R5'),('CAVITY','CAVITY')],1):
        r=next(r for r in rooms if r['id']==cad);key='CAD_1F_'+cad
        mapped.append(dict(key=key,original_room=key,solver_id=native,cad_floor='1F',cad_room=cad,
                           cad_center_m=r['c'],cad_polys=r['polys'],z_m=0,height_m=6.405,
                           area_m2=157.5 if cad=='R5' else .875,
                           display_name='저온창고' if cad=='R5' else '강판 뒤 공동',fuel_class='coldstore_pu_lining'))
        assert cu[f'ULO2_{i}']=='mol_frac' and zu[f'ULOD_{i}']=='1/m'
        s={k:c[f'{src}_{i}'].tolist() for k,src in [('Tu','ULT'),('Tl','LLT'),('h','HGT'),('Ou','ULO2'),('Ol','LLO2')]}
        s.update(height_m=6.405,ODu=z[f'ULOD_{i}'].tolist(),ODl=z[f'LLOD_{i}'].tolist(),
                 Fu=saved[native]['fuel_upper_mass_fraction'],Qsolid_kW=saved[native]['source_HRR_kW'],
                 Qvent_kW=saved[native]['door_jet_kW'],Qbulk_kW=[0]*len(grid))
        s['conditions']={key:{'scores':scores[native][old],'status':'evaluated'} for old,key in [('FO','FO'),('FGI','FGI'),('BD','backdraft'),('rollover','rollover')]}
        s['conditions']['FO']={
            'scores':deepcopy(scores[native]['FO']),
            'status':'evaluated',
            'legacy_combustion_support_scores':scores[native]['FO'],
            'scope':'shared three-factor FO; own HRR plus receiving door jet; no ignition feedback'}
        openings={op['id']:{'fraction':v[next(k for k in v if k.startswith('WF_') and vid[k]==op['id'])]} for op in model['openings']}
        required=fo_required_hrr(model,{'time_s':c['Time'],'opening_states':openings},model['rooms'][i-1],c['Time'])
        apply_fo_hrr(s['conditions']['FO'],s['Qsolid_kW'],s['Qvent_kW'],required)
        solvers[native]=s
    p=dict(schema='pyrocast-cad-playback-1',engine_kind='cfast_native',case_id='wando-P1',
        native_mapping='wando-c11-p1-v1',building_sha256=bsha,label='완도 P1 · 순정 CFAST · 마지막 5 s 미출력',
        complete=True,simulation_output_complete=False,requested_end_s=3600,t_end_s=3595,
        output_step_s=5,time_s=grid,native_time_s=times,rooms=mapped,solvers=solvers,
        fire_key='CAD_1F_CAVITY',route_target_room_id='CAD_1F_R5',events=[],
        fires=[dict(id='PU',kind='initial',cad_key='CAD_1F_CAVITY',cad_floor='1F',time_s=0,
                    position_m=[46.75,18.05,0],Q_kW=saved['CAVITY']['source_HRR_kW'],
                    visuals={'base_height_m':0,'flame_height_m':z['FLHGT_1'].tolist(),'area_m2':z['FAREA_1'].tolist(),'radiative_fraction':.35})],
        limits=['마지막 5 s 미출력: 재생 종료 3,595 s. 3,600 s 값 보간·외삽 없음.',
                '순정 CFAST P1 저장 CSV 재생. R5·공동만 계산; 나머지 실은 미평가.',
                '0.1 m 공동의 2존 근사. 위험 지수는 발생 확률이 아님.',
                'CAVITY는 R5 자체 벽의 강판 뒤 우레탄 연소 공간을 분리한 계산 구획이며 외부 화재가 아님.',
                'FO는 온도·연료·산소 세 요인의 최솟값. 연료 항 = (자체 HRR + 수신 문 분출 HRR)/Thomas 필요 발열량. 발생 확률·실제 FO 확정 아님.',
                '공동의 FO 지수는 얇은 벽체 공간의 온도 진단이며 R5 전체 플래시오버를 뜻하지 않음.',
                '문 분출 발열은 ROOM 합계이며 틈과 절단 개구별로 분리 불가.',
                '3D 절단 표시는 입력 일정의 우측값. native CSV는 다음 5 s 표본부터 반영.',
                '경로는 등록 장애물 평면 외곽 0.5 m 회피. 미등록 적재물·호스 굴곡 미반영.'],
        provenance={'engine_sha256':sha(ROOT/'simulation/build/baseline/cfast-baseline.exe'),
                    'source_files':{f:sha(SRC/f) for f in ['case.in','case_zone.csv','case_compartments.csv','case_vents.csv','condition-scores.json']},
                    'mapping':{'temperature':'C','O2':'mol_frac (volume fraction)','OD':'case_zone.csv 1/m','HRR':'case_compartments W / 1000','indices':'FO: fo_own_plus_received_door_jet_v1; FGI/BD/rollover: saved condition-scores.json unchanged'},
                    'fo_display':{'revision':REVISION,'threshold_C':model['criteria']['fo_temperature_C'],
                        'module_sha256':sha(ROOT/'simulation/pyrocast_cfbt/fo_hrr.py'),
                        'old_score_preserved':'solvers.*.conditions.FO.legacy_combustion_support_scores','floor_flux':'not_evaluated'},'simulation_runs':0},
        opening_states={op['id']:{'schedule':op['schedule'],
            'fraction':v[next(k for k in v if k.startswith('WF_') and vid[k]==op['id'])].tolist()} for op in model['openings']})
    write(DATA/'P1-playback.json',p)
    write(DATA/'playback-evidence.json',dict(building_sha256=bsha,playback_sha256=sha(DATA/'P1-playback.json'),
        samples=len(grid),last_sample_s=grid[-1],native_time_snap_max_s=max(abs(a-b) for a,b in zip(times,grid)),
        recalculations=0,source=p['provenance']))
    print(json.dumps({'samples':len(grid),'end_s':grid[-1],'bytes':(DATA/'P1-playback.json').stat().st_size,'recalculations':0}))

if __name__=='__main__':main()
