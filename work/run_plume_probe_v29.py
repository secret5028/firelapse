from pathlib import Path
import json,csv
from cfast_runtime import run_native
root=Path(__file__).resolve().parent.parent
out=root/'outputs/CAD-공식플룸-v29/probe';out.mkdir(exist_ok=True)
points=[(r,z) for r in [0,.5,1,2,4] for z in [.5,2,4,4.6,4.9,4.99]]
lines=["&HEAD VERSION=7500 TITLE='Official plume postprocess verification only' /",
"&TIME SIMULATION=31 PRINT=0 SMOKEVIEW=5 SPREADSHEET=5 /",
"&INIT PRESSURE=101325 RELATIVE_HUMIDITY=50 INTERIOR_TEMPERATURE=20 EXTERIOR_TEMPERATURE=20 /",
"&MATL ID='C' CONDUCTIVITY=1.75 DENSITY=2200 SPECIFIC_HEAT=1 THICKNESS=.15 EMISSIVITY=.94 /",
"&COMP ID='R' WIDTH=12 DEPTH=12 HEIGHT=5 ORIGIN=0,0,0 CEILING_MATL_ID='C' WALL_MATL_ID='C' FLOOR_MATL_ID='C' LEAK_AREA_RATIO=.00017,.000052 /",
"&FIRE ID='F' COMP_ID='R' FIRE_ID='Fuel' LOCATION=6,6 /",
"&CHEM ID='Fuel' CARBON=6 HYDROGEN=10 OXYGEN=5 HEAT_OF_COMBUSTION=18100 RADIATIVE_FRACTION=.33 /",
"&TABL ID='Fuel' LABELS='TIME','HRR','HEIGHT','AREA','CO_YIELD','SOOT_YIELD' /",
"&TABL ID='Fuel' DATA=0,0,0,2,.0062,.015 /",
"&TABL ID='Fuel' DATA=1,1000,0,2,.0062,.015 /",
"&TABL ID='Fuel' DATA=31,1000,0,2,.0062,.015 /"]
for i,(r,z) in enumerate(points,1):lines.append(f"&DEVC ID='P{i}' COMP_ID='R' TYPE='PLATE' LOCATION={6+r},6,{z} NORMAL=0,1,0 MATL_ID='C' THICKNESS=.01 /")
lines.append('&TAIL /');(out/'probe.in').write_text('\n'.join(lines),encoding='ascii')
timing=run_native(root/'work/smokeview-demo/firemodels/cfast7/cfast.exe',out,'probe',flags=('-k','-o:CD'),timeout=90)
def read(name):
    with (out/name).open() as fp:
        rows=list(csv.reader(fp));return [dict(zip(rows[0],map(float,r))) for r in rows[4:] if r]
cases=[]
for comp,dev in zip(read('probe_compartments.csv'),read('probe_devices.csv')):
    for i,(r,z) in enumerate(points,1):cases.append(dict(time=comp['Time'],r=r,z=z,q=comp['HRR_1'],tu=comp['ULT_1']+273.15,tl=comp['LLT_1']+273.15,layer=comp['HGT_1'],native=dev[f'TRGGAST_{i}']))
(out/'cases.json').write_text(json.dumps(cases),encoding='utf8')
print(timing['wall_seconds'],len(cases))
