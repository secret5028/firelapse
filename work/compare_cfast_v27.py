"""Compare native outputs at shared timestamps, without rerunning the reference."""
from pathlib import Path
import argparse,csv,json,math,re,hashlib
ROOT=Path(__file__).resolve().parent.parent
BASE=ROOT/'outputs/CAD-조건부전이-v26'
OUT=ROOT/'outputs/CAD-속도검증-v27'

def read_csv(path,headers=2):
    with path.open() as stream:
        rd=csv.reader(stream)
        if headers==2:next(rd);head=next(rd)
        else:
            head=next(rd)
            for _ in range(headers-1):next(rd)
        return [dict(zip(head,map(float,row))) for row in rd if row]

def stats(pairs):
    if not pairs:return {}
    errors=sorted(abs(a-b) for a,b,*_ in pairs)
    worst=max(pairs,key=lambda x:abs(x[0]-x[1]))
    return dict(count=len(errors),mae=sum(errors)/len(errors),max=errors[-1],p95=errors[int(.95*(len(errors)-1))],worst=worst)

def compare(folder,stem='case'):
    base=read_csv(BASE/'multifloor_zone.csv');cand=read_csv(folder/f'{stem}_zone.csv')
    assert all(math.isfinite(v) for row in cand for v in row.values())
    bd={r['Time']:r for r in base};cd={r['Time']:r for r in cand}
    times=sorted(cd);assert all(t in bd for t in times)
    manifest=json.loads((BASE/'connection-manifest.json').read_text('utf8'))
    rooms=list(manifest['rooms'])
    groups={name:[] for name in ['upper_C','lower_C','layer_m','upper_OD','lower_OD','hrr_kW','flame_m','flow_kg_s']}
    patterns={'ULT_':'upper_C','LLT_':'lower_C','HGT_':'layer_m','ULOD_':'upper_OD','LLOD_':'lower_OD','HRR_':'hrr_kW','FLHGT_':'flame_m','VVENT_':'flow_kg_s','VSLABF_':'flow_kg_s'}
    byroom={k:[] for k in rooms}
    for t in times:
        for prefix,g in patterns.items():
            for k,b in bd[t].items():
                if k.startswith(prefix) and k in cd[t]:
                    a=cd[t][k];groups[g].append((a,b,t,k))
                    if prefix=='ULT_':byroom[rooms[int(k.split('_')[1])-1]].append((a,b,t,k))
    def events(path):
        return {m.group(1):int(m.group(2)) for m in re.finditer(r'Object #\d+ \(([^)]+)\) ignited at\s+(\d+) seconds',path.read_text(errors='replace'))}
    comp=read_csv(folder/f'{stem}_compartments.csv',4)
    oldcomp=read_csv(BASE/'multifloor_compartments.csv',4)
    oc={r['Time']:r for r in oldcomp}
    native_groups={}
    for prefix in ['HRR_','HRR_E','IGN_','DJET_']:
        native_groups[prefix]=stats([(r[k],oc[r['Time']][k],r['Time'],k) for r in comp for k in r if k.startswith(prefix)])
    dev=read_csv(folder/f'{stem}_devices.csv',4);olddev={r['Time']:r for r in read_csv(BASE/'multifloor_devices.csv',4)}
    target=stats([(r[k],olddev[r['Time']][k],r['Time'],k) for r in dev for k in r if k.startswith('TRGSURT_')])
    # Diagnostic smoke arrival threshold, not a tenability standard.
    arrival=[]
    for i,k in enumerate(rooms,1):
        col=f'ULOD_{i}'
        a=next((t for t in times if cd[t][col]>=.01),None)
        b=next((t for t in times if bd[t][col]>=.01),None)
        if a!=b:arrival.append(dict(room=k,candidate=a,baseline=b))
    result=dict(duration=times[-1],samples=len(times),metrics={k:stats(v) for k,v in groups.items()},
        native_metrics=native_groups,target_C=target,ignition_candidate=events(folder/f'{stem}.log'),
        ignition_baseline={k:v for k,v in events(BASE/'multifloor.log').items() if v<=times[-1]},
        upper_temperature_by_room={k:stats(v) for k,v in byroom.items()},smoke_arrival_threshold_OD_per_m=.01,
        smoke_arrival_differences=arrival,physical_validation=False)
    (folder/'comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='upper_temperature_by_room'},ensure_ascii=False))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--stem',default='case');a=p.parse_args()
    compare(OUT/a.name,a.stem)
