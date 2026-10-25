"""Read-only comparison of existing FO-temperature and FGI-potential criteria."""
import argparse,json,re,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'simulation'))
from pyrocast_cfbt.native import read_diagnostic,read_native_csv

def fields(block):
    return dict(re.findall(r"(\w+)\s*=\s*'([^']*)'",block))

def load(folder,until,criteria):
    deck=(folder/'case.in').read_text('ascii')
    rooms=[fields(b)['ID'] for b in re.findall(r'&COMP\s+(.*?)/',deck,re.S)]
    fires=[]
    for b in re.findall(r'&FIRE\s+(.*?)/',deck,re.S):
        f=fields(b)
        if f.get('IGNITION_CRITERION')!='TIME':raise ValueError('Only prescribed TIME fires in this comparison')
        f['start']=float(re.search(r'SETPOINT\s*=\s*([\d.Ee+\-]+)',b)[1]);fires.append(f)
    data,_,units=read_native_csv(folder/'case_compartments.csv',until)
    native_times=np.asarray(data['Time'])
    mixture={(r['time_s'],int(r['room_index'])):r for r in read_diagnostic(folder/'case_cfbt_mixture.csv',until)}
    result={}
    for r in read_diagnostic(folder/'case_cfbt_rooms.csv',until):
        t=r['time_s'];ri=int(r['room_index']);rid=rooms[ri-1];key=(t,ri)
        ni=int(np.argmin(abs(native_times-t)))
        if abs(native_times[ni]-t)>1e-6:raise ValueError('Native HRR timestamp mismatch')
        relevant=[i for i,f in enumerate(fires,1) if f['COMP_ID']==rid]
        actual=False
        for i in relevant:
            col=f'HRR_{i}'
            if units[col]!='W':raise ValueError('Unexpected solid HRR unit')
            actual|=data[col][ni]>1000
        active=any(t>=fires[i-1]['start'] for i in relevant)
        yf=mixture[key]['combustible_upper_kg']/max(r['upper_mass_kg'],1e-12)
        if abs(t-round(t))>1e-3:raise ValueError('Output outside nominal comparison grid')
        result[(float(round(t)),ri)]={'room':rid,'fo':bool(active and r['T_upper_C']>=criteria['fo_temperature_C']),
            'fgi':bool(yf>=criteria['fgi_fuel_mass_fraction'] and r['o2_upper_vol']>=criteria['fgi_oxygen_vol_percent']/100
                and not actual and r['bulk_HRR_W']<=1e-6)}
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scope',choices=['small','stalled'],required=True)
    parser.add_argument('--output-root',type=Path,default=ROOT/'simulation/results/mixture_r3c_20261023')
    args=parser.parse_args();base=args.output_root.resolve()/args.scope
    report=json.loads((base/'comparison.json').read_text('utf-8'))
    until=report['differences']['old_vs_smooth']['common_until_s']
    model=json.loads((ROOT/'simulation/results/floor_spread_20261022/r2_ventilated/scenario.json').read_text('utf-8'))
    c={k:model['criteria'][k] for k in ('fo_temperature_C','fgi_fuel_mass_fraction','fgi_oxygen_vol_percent')}
    old=load(ROOT/'simulation/results/mixture_r3b_20261023'/args.scope/'old',until,c)
    new=load(base/'smooth',until,c);keys=old.keys()&new.keys()
    results={'scope':args.scope,'common_until_s':until,'criteria':c,
        'basis':'FO: scheduled active fire AND upper temperature. FGI: FUEL+CO fraction, O2, no actual solid >1kW, no bulk. No event-loop feedback evaluated.',
        'criteria_origin':'3F scenario criteria; same declared criteria used on the synthetic small case','comparisons':{}}
    for name in ('fo','fgi'):
        entry={'different_room_time_samples':sum(old[k][name]!=new[k][name] for k in keys),'rooms':[]}
        for ri in sorted({k[1] for k in keys}):
            kk=sorted(k for k in keys if k[1]==ri)
            row={'room':old[kk[0]]['room']}
            for label,items in [('old',old),('new',new)]:
                hit=[k[0] for k in kk if items[k][name]]
                row[label]={'first_met_s':min(hit) if hit else None,
                    'duration_s':sum(kk[i+1][0]-k[0] for i,k in enumerate(kk[:-1]) if items[k][name])}
            if row['old']['first_met_s'] is not None or row['new']['first_met_s'] is not None:entry['rooms'].append(row)
        results['comparisons'][name]=entry
    (base/'condition-comparison.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(results,ensure_ascii=False))

if __name__=='__main__':main()
