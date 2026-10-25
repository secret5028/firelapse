"""Package saved CFAST results for the interactive 3D view; no simulation rerun."""
from pathlib import Path
import argparse
import json
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def build(source,destination):
    result=json.loads(Path(source).read_text(encoding='utf-8'))
    t=result['time_s']; config=result['scenario']; n=len(t)
    data={'time':t,'rooms':[],'openings':config['openings'],'fires':[],
          'ignitions':result['ignitions'],'source_sha256':result['final_input_sha256'],
          'status':result['terminated'],'flow':{},'gas_rate_profile':config['gas']['profile_id']}
    mapping={'Tu':'T_upper_C','Tl':'T_lower_C','h':'interface_m','Ou':'o2_upper_vol',
             'Ol':'o2_lower_vol','Fu':'fuel_upper_kg','Fl':'fuel_lower_kg'}
    for room in config['rooms']:
        state=result['rooms'][room['id']]
        item={**room,**{short:state[key] for short,key in mapping.items()}}
        p=result['phenomena'][room['id']]
        item.update(Qgas=[q/1000 for q in p['gas_HRR_W']],Oin=p['oxygen_in_kg_s'],Fin=p['fuel_in_kg_s'])
        data['rooms'].append(item)
    event_by_group={e['group']:e for e in result['ignitions']}
    for group in config['fuel_groups']:
        event=event_by_group.get(group['id'])
        if event is None and 'initial_time_s' not in group:continue
        inventory=result['solid_fuel_inventory'][group['id']]
        data['fires'].append({'group':group['id'],'room':group['room'],
            'time':group['initial_time_s'] if event is None else event['t_ign_s'],
            'position':group['position_m'] if event is None else event['xyz'],
            'Q':[v/1000 for v in inventory['actual_HRR_W']],
            'kind':'initial' if event is None else 'additional'})
    for opening in config['openings']:
        data['flow'][opening['id']]={'ab':np.zeros((n,5)), 'ba':np.zeros((n,5))}
    for row in result['directional_flow_slabs']:
        index=int(np.argmin(np.abs(np.array(t)-row['time_s'])))
        vi=int(row['vent_index'])-1
        opening=config['openings'][vi]
        source_name='OUTSIDE' if row['room_from']>len(config['rooms']) else config['rooms'][int(row['room_from'])-1]['id']
        direction='ab' if source_name==opening['a'] else 'ba'
        slot=data['flow'][opening['id']][direction][index]
        mass=row['mass_kg_s']
        slot+=np.array([mass,row['o2_kg_s'],row['fuel_kg_s'],
                       mass*(row['bottom_m']+row['top_m'])/2,mass*row['temperature_C']])
    for opening in data['flow'].values():
        for key,array in opening.items():
            positive=array[:,0]>1e-10
            array[positive,3:]/=array[positive,0:1]
            opening[key]=array.tolist()
    def rounded(value):
        if isinstance(value,dict):return {k:rounded(v) for k,v in value.items()}
        if isinstance(value,list):return [rounded(v) for v in value]
        if isinstance(value,float):return round(value,5)
        return value
    template=(ROOT/'viewer/scene-fragment.html').read_text(encoding='utf-8')
    html=template.replace('__SCENE_DATA__',json.dumps(rounded(data),ensure_ascii=False,separators=(',',':')))
    destination=Path(destination); destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(html,encoding='utf-8')
    if len(html.encode('utf-8'))>=1_000_000:raise ValueError('Inline 3D payload exceeds budget')
    print(f'{destination} ({len(html.encode("utf-8")):,} bytes)')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('source',type=Path)
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    build(args.source,args.destination)
