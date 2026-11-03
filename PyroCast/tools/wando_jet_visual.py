"""Saved-flow allocation for rendering only; never changes a combustion ledger."""
import numpy as np

def add_jet_visuals(playback,model,vents):
    rooms={r['id']:r for r in model['rooms']};directions=[]
    for target in rooms:
        candidates=[]
        for j,op in enumerate(model['openings'],1):
            if target not in (op['a'],op['b']) or 'OUTSIDE' in (op['a'],op['b']):continue
            source=op['b'] if target==op['a'] else op['a'];owner=list(rooms).index(op['a'])+1
            # CSV WT is from the first compartment's perspective.
            sign='outflow' if source==op['a'] else 'inflow'
            upper=np.maximum(0,vents[f'WT_{owner}_u_{sign}_{j}']);lower=np.maximum(0,vents[f'WT_{owner}_l_{sign}_{j}'])
            fraction=playback['opening_states'][op['id']]['fraction'];opened=np.asarray(fraction)>0
            a=rooms[op['a']];x,y,z=a['origin_m']
            if op['face']!='FRONT':raise ValueError('Wando display export expects FRONT opening')
            # Native ROOM origin maps to CAD x=45; existing playback geometry is authoritative.
            geometry={'center_m':[45+x+op['offset_m']+op['width_m']/2,y,z+(op['bottom_m']+op['top_m'])/2],
                'span_direction':[1,0],'width_m':op['width_m'],'bottom_m':op['bottom_m'],'top_m':op['top_m']}
            candidates.append((op,source,upper*opened,lower*opened,geometry))
        if not candidates:continue
        total_upper=sum(c[2] for c in candidates);total_all=sum(c[2]+c[3] for c in candidates)
        q=np.asarray(playback['solvers'][target]['Qvent_kW']);allocated=np.zeros(len(q))
        for op,source,upper,lower,geometry in candidates:
            numerator=np.where(total_upper>0,upper,upper+lower);denominator=np.where(total_upper>0,total_upper,total_all)
            share=np.divide(numerator,denominator,out=np.zeros(len(q)),where=denominator>0);power=q*share;allocated+=power
            directions.append({'vent':op['id'],'from':source,'to':target,'HRR_kW':power.tolist(),
                'visual_opening':geometry,'fraction':playback['opening_states'][op['id']]['fraction'],
                'basis':'DISPLAY ONLY: receiver aggregate DJET allocated by saved upper outflow (total outflow fallback); not native per-vent HRR'})
        if not np.allclose(allocated,q,atol=1e-6):raise ValueError('Positive DJET has no saved inflow path; cannot allocate display')
    playback['door_jet']={'directions':directions,'display_only_allocation':True,'basis':'saved receiver total preserved; no energy/oxygen change'}
    for f in playback['fires']:
        if f['cad_key']=='CAD_1F_CAVITY':f['visual_mode']='cavity_wall_glow'
    note='분출 화염 위치별 크기는 저장된 상층 유출 유량 비율로 실별 DJET 합계를 나눈 표시용 근사이며, 개구부별 연소 계산값이 아니다.'
    if note not in playback['limits']:playback['limits'].append(note)
    return playback
