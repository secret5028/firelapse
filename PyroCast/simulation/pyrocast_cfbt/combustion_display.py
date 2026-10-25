"""Display-only classification: activation is not evidence of positive source HRR."""
import numpy as np

LABELS={
    'inactive':'착화 조건 미충족',
    'burning':'연소 중',
    'supply_without_burning':'착화 조건 충족, 산소·혼합 제한으로 화원 연소 미발생',
    'activated_no_supply':'착화 조건 충족, 현재 연료 공급 없음(성장 시작·소진 등)',
}

def classify_source(q_W,supply_kg_s,activated):
    q=np.asarray(q_W);supply=np.asarray(supply_kg_s);active=np.asarray(activated,dtype=bool)
    if q.shape!=supply.shape or q.shape!=active.shape:raise ValueError('Source display series shapes differ')
    states=np.full(q.shape,'inactive',dtype=object)
    states[active]='activated_no_supply'
    states[active&(supply>0)&(q<=0)]='supply_without_burning'
    states[q>0]='burning'
    return states.tolist()

def group_display(inventory,t,at):
    q=inventory.get('actual_HRR_W',np.zeros(len(t)))
    supply=inventory.get('pyrolysis_supply_kg_s',np.zeros(len(t)))
    return {'combustion_state':classify_source(q,supply,np.asarray(t)>=at),
            'actual_source_HRR_kW':(np.asarray(q)/1000).tolist(),
            'native_pyrolysis_kg_s':list(supply),
            'combustion_basis':'source HRR > 0; positive native pyrolysis with zero HRR indicates oxygen/mixing restriction; vent combustion reported separately'}
