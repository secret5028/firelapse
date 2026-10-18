from pathlib import Path
import json,re,sys,math
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'work/cad-deps'))
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
from cfast_fuel_inventory import energy_mj
OUT=ROOT/'outputs/CAD-가연물묶음-v30'
def read_input(path):
    text=path.read_text('utf8');blocks={}
    for kind,body in re.findall(r'&(\w+)\s+(.*?)/',text,re.S):
        m=re.search(r"\bID='([^']+)'",body)
        if m:blocks.setdefault((kind,m[1]),[]).append(body)
    def field(body,name):return re.search(r'\b'+name+r"=('[^']*'|[^\s]+)",body)[1].strip("'")
    fires={}
    for (kind,fid),items in blocks.items():
        if kind!='FIRE':continue
        definition=field(items[0],'FIRE_ID')
        curve=[list(map(float,field(x,'DATA').split(','))) for x in blocks['TABL',definition] if 'DATA=' in x]
        hoc=float(field(blocks['CHEM',definition][0],'HEAT_OF_COMBUSTION'))
        fires[fid]=dict(curve=curve,heat_of_combustion=hoc,definition=definition)
    return text,blocks,fires
bt,bb,bf=read_input(ROOT/'outputs/CAD-속도검증-v27/final/multifloor.in')
pt,pb,pf=read_input(OUT/'placement-only/multifloor.in')
ct,cb,cf=read_input(OUT/'ceiling/multifloor.in')
for kind in ['COMP','VENT','DEVC']:
    for key,items in bb.items():
        if key[0]!=kind:continue
        if kind=='DEVC' and key[1] not in ['T_WorkstationN','T_WorkstationS']:continue
        assert pb[key]==items,(kind,key,'placement-only unexpectedly changed')
for kind in ['FIRE','DEVC','CHEM','TABL','VENT']:
    assert {k:v for k,v in pb.items() if k[0]==kind}=={k:v for k,v in cb.items() if k[0]==kind},kind
for fid in ['ExampleFire','WorkstationN','WorkstationS']:assert bf[fid]==pf[fid]
for parent in ['WorkstationHall','WorkstationAS']:
    for idx,old in enumerate(bf[parent]['curve']):
        a=pf[parent+'Door']['curve'][idx];b=pf[parent+'Inner']['curve'][idx]
        assert old[0]==a[0]==b[0]
        assert math.isclose(old[1],a[1]+b[1],abs_tol=1e-9)
        assert math.isclose(old[3],a[3]+b[3],abs_tol=1e-9)
        assert old[2]==a[2]==b[2] and old[4:]==a[4:]==b[4:]
def budgets(fs):
    energy=sum(energy_mj(f['curve']) for f in fs.values())
    mass=sum(energy_mj(f['curve'])/(f['heat_of_combustion']/1000) for f in fs.values())
    return dict(energy_MJ=energy,equivalent_fuel_kg=mass,peak_sum_kW=sum(max(v[1] for v in f['curve']) for f in fs.values()))
a,b=budgets(bf),budgets(pf)
assert all(math.isclose(a[k],b[k],abs_tol=1e-7) for k in a)
report=dict(input_validation='passed',baseline_budget=a,new_budget=b,energy_meaning='All prescribed curves at their own ignition age, not necessarily released energy within the global 30-minute run',threshold_and_material_unchanged=True,native_engine_unchanged=True)
for name in ['placement-only','ceiling']:
    p=OUT/name/'cfast-demo.json'
    if not p.exists():continue
    data=json.loads(p.read_text('utf8'))
    assert len(data['rooms'])==156 and data['solver_compartments']==100 and len(data['vertical_connections'])==36
    assert all(len(f['hrr'])==361 and all(math.isfinite(v) and v>=0 for v in f['hrr']) for f in data['fires'])
    if 'fuel_inventory' in data:
        assert math.isclose(data['fuel_inventory']['prescribed_energy_MJ'],a['energy_MJ'],abs_tol=1e-5)
        assert data['fuel_inventory']['unit_count']==20
        rooms={r['key']:r for r in data['rooms']}
        for f in data['fires']:
            shape=unary_union([Polygon(p['o'],p['h']) for p in rooms[f['room_key']]['polys']])
            assert math.isclose(sum(u['energy_MJ'] for u in f['fuel_units']),f['inventory_energy_MJ'])
            for u in f['fuel_units']:
                x,y=u['position'];w=u['width_m']/2;d=u['depth_m']/2
                assert shape.covers(box(x-w,y-d,x+w,y+d)),u['id']
    report[name]=dict(duration=data['duration'],fires=[dict(id=f['id'],ignition_time=f['ignition_time'],peak_kW=max(f['hrr']),max_surface_C=max((v[1] for v in f.get('target_series',[])),default=None)) for f in data['fires']])
(OUT/'검증결과.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(report,ensure_ascii=False))
