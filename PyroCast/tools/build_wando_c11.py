"""C11 sections 1/2: dimension input and material/fuel data only. No solver."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'simulation/deps'))
from shapely.geometry import Polygon
OUT = ROOT / 'data/wando-coldstore'
SPEC = ROOT / 'specs/Claude지시-C11-완도저온창고사례-20261102.md'


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    table = json.loads((ROOT / 'simulation/pyrocast_lite/fire_load_table.json').read_text('utf-8'))
    specs = [('R1', '냉동실', 0, 0, 18, 18.4), ('R8', '동결실', 0, 0, 9, 6),
             ('R2', '저온(공실)', 18, 0, 9, 18.4), ('R3', '저온(생선)', 27, 0, 9, 18.4),
             ('R9', '기계실', 27, 18.4, 9, 5.5), ('R4', '저온(배추)', 36, 0, 9, 18.4),
             ('R5', '저온(공실·화점)', 45, 0, 8.75, 18), ('R6', '저온(미역)', 54, 0, 18, 18.4)]
    rooms, openings, fuels = [], [], []
    h = 6.405
    for rid, name, x, y, w, d in specs:
        p = [[x,y], [x+w,y], [x+w,y+d], [x,y+d]]
        if rid == 'R1':
            p = [[9,0],[18,0],[18,18.4],[0,18.4],[0,6],[9,6]]
        polygon = Polygon(p)
        usage = 'equipment' if rid == 'R9' else 'coldstore_pu_lining'
        rooms.append(dict(room_id=rid, name=name, usage=usage, core_kind=None,
                          polygon_m=p, holes_m=[], polygons_m=[dict(polygon_m=p, holes_m=[])],
                          floor_z_m=0, ceiling_z_m=h, cells=[]))
        # Non-overlapping R1 front is x=9..18. R9 has its own exterior rear door.
        door_x, door_y = (13.5,0) if rid == 'R1' else (x+w/2, y+d if rid == 'R9' else y)
        small = rid in ('R8','R9')
        width, height = (.9,2.1) if small else (2.5,3.)
        openings.append(dict(opening_id=f'D_{rid}', kind='door', door_class='ordinary',
                             door_class_basis='[가정] 내화 성능 미확인, 일반문 입력', user_override=False,
                             a=rid, b='OUTSIDE', center_m=[door_x,door_y,height/2], width_m=width,
                             sill_m=0, soffit_m=height, exterior=True, initial_fraction=0,
                             source_kind='dimension_input_report_R5' if rid=='R5' else 'dimension_input_assumption'))
        cls = table['classes'][usage]
        lining = polygon.length*h + polygon.area
        energy = (lining*cls['lining_thickness_m']*cls['lining_density_kg_m3']*cls['heat_of_combustion_MJ_kg']
                  if usage=='coldstore_pu_lining' else polygon.area*cls['mean'])
        fuels.append(dict(room_id=rid, name=name, fuel_class=usage, area_m2=polygon.area,
                          wall_lining_m2=polygon.length*h, ceiling_lining_m2=polygon.area,
                          lining_area_m2=lining if usage=='coldstore_pu_lining' else None,
                          energy_MJ=energy, fire_load_MJ_m2=energy/polygon.area,
                          coverage_fraction=.5, hrrpua_kW_m2=cls['rhrf'], t_alpha_s=cls['t_alpha'],
                          heat_of_combustion_kJ_kg=25000 if usage=='coldstore_pu_lining' else None,
                          basis=cls['basis'], note=cls.get('assumption', ''),
                          formula='(perimeter*height + floor_area)*0.1*35*25 / floor_area' if usage=='coldstore_pu_lining' else 'equipment provisional default'))
    notes = [
        '치수 출처는 C11 지시서. 사고조사 HWP 원본은 이번 작업에서 직접 확인하지 않음.',
        '1층만 모델링. R5 내부 8.75×18×6.405 m는 지시서의 보고서 수치. 다른 실 높이는 6.405 m로 확장한 가정.',
        'R1은 내부 R8을 뺀 L자형. 중복 체적 없음. R1 문은 노출 전면 x=9..18의 중앙 x=13.5로 이동한 가정.',
        'R9 외기문은 북측 y=23.9 중앙으로 가정. R8은 남측 중앙. 실내 문은 없음.',
        '실 내부 치수는 유지. 벽 시각화 두께 0.4 m(RC .3+PU .1) 가정. 지시서 좌표의 0.25 m 간극도 유지.',
        '72×18.4 m와 지시서의 1층 면적 1701.3 m²는 불일치. 돌출부·미제공 공간을 임의로 늘리지 않음.',
        f'R9 돌출부 포함 실 바닥면적 합 {sum(Polygon(r["polygon_m"]).area for r in rooms):.1f} m². 원 보고 면적을 충족하는 완전한 준공 모델이 아님.',
        '2층 공장 미모델. 상부는 슬래브 표시만. 초기 문은 닫힘 표시용이며 A/B/C 실행 상태는 아직 미작성.',
        '기계실 equipment 클래스 수치 미지정: 기존 default 500 MJ/m²·250 kW/m²·t_alpha 300 s 임시값.',
        '저온실의 생선·배추·미역 저장물은 연료에 더하지 않음. 지시서대로 PU 내장재만 바닥 등가로 환산.',
        '벽·천장 PU 열경계는 단일 재료 근사. RC·강판·에폭시 복합층 및 강판 뒤 산소 제한은 미모델.'
    ]
    building = dict(schema='pyrocast.building/1', building_id='wando-coldstore',
                    source_hash=hashlib.sha256(SPEC.read_bytes()).hexdigest(),
                    units=dict(length='m', origin=[0,0,0], up='z'),
                    floors=[dict(floor_id='1F',name='1F',elevation_m=0,height_m=h,rooms=rooms,openings=openings)],
                    errors=[],scope='C11 sections 1/2: geometry-only, no simulation',geometry_notes=notes)
    pu = dict(conductivity_W_mK=.025,density_kg_m3=35,specific_heat_kJ_kgK=1.4,
              thickness_m=.1,emissivity=.9,assumed=True,basis='C11 §2 PU; emissivity .9 project assumption')
    concrete = dict(conductivity_W_mK=1.75,density_kg_m3=2200,specific_heat_kJ_kgK=1.,
                    thickness_m=.15,emissivity=.94,assumed=True,basis='existing S09 concrete proxy; floor thickness unreported')
    write('building.json', building)
    write('fuel-inputs.json', dict(source='simulation/pyrocast_lite/fire_load_table.json',rooms=fuels,
                                  coverage_sensitivity_pending=[.3,.5,1.],simulation_executed=False))
    write('materials.json', dict(materials={'PU_LINING':pu,'CONCRETE_FLOOR':concrete},
                                 rooms={r['room_id']:dict(wall='PU_LINING',ceiling='PU_LINING',floor='CONCRETE_FLOOR') for r in rooms},
                                 note='기계실도 PU 마감으로 가정. 강판·RC 복합벽을 별도 열층으로 추가하지 않음.'))
    write('thermal-input.json', dict(wall_material=pu,surface_materials={'PU_LINING':pu,'CONCRETE_FLOOR':concrete},
                                    rooms=[dict(id=r['room_id'],surface_material_ids=dict(wall='PU_LINING',ceiling='PU_LINING',floor='CONCRETE_FLOOR')) for r in rooms],
                                    note='입력 합성용 조각. 독립 실행 덱/시나리오 아님.'))
    write('provenance.json', dict(spec_sha256=building['source_hash'],source='C11 specification, not independently verified HWP',
                                 assumptions=notes,reported_first_floor_m2=1701.3,modeled_floor_m2=sum(Polygon(r['polygon_m']).area for r in rooms),
                                 section3_executed=False,section4_building_switcher_implemented=False))
    return building


if __name__ == '__main__':
    print(json.dumps({'building':build()['building_id'],'simulation_runs':0}))
