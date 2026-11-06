"""Add display-only inputs from saved output/decks. No integration, no score edits."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'simulation'),str(ROOT/'simulation/deps')]
import numpy as np
from pyrocast_cfbt.room_rule_r8 import prepare
from pyrocast_cfbt.deck import make_deck
from pyrocast_lite.shared_inputs import records

def read(p):return json.loads(p.read_text('utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core_digest(p):
    d=deepcopy(p);d.pop('display_inputs',None)
    return hashlib.sha256(json.dumps(d,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def main():
    review=ROOT/'reviews/B5-20261103';review.mkdir(parents=True,exist_ok=True)
    cfg=read(ROOT/'simulation/config/lite-viewer.json')
    from runtime_storage import app_path
    paths=sorted({app_path(c['path']) for c in cfg['cases']}|{ROOT/'data/wando-coldstore/P1-playback.json'})
    report=[]
    for path in paths:
        p=read(path);before=core_digest(p);source=path.parent/'result.json';native=path.name=='P1-playback.json'
        if not native and not source.exists():
            report.append(dict(path=str(path.relative_to(ROOT)),status='no saved result; renderer uses declared fallback'));continue
        inputs=dict(revision='B5-display-inputs-v1',time_s=p['time_s'],fires={},rooms={},sources={},simulation_runs=0)
        if native:
            source=ROOT/'simulation/results/wando_C11_P1_20261102/case.in';deck=source.read_text('utf-8')
            chem={r['ID']:r for k,r in records(deck) if k=='CHEM'}
            for fire in p['fires']:
                fid='F_'+fire['id'];c=chem[fid]
                pairs=[(float(a),float(b)) for a,b in re.findall(r"&TABL ID='"+re.escape(fid)+r"' DATA=([^,]+),([^,]+),",deck)]
                assert pairs
                q=np.interp(p['time_s'],[x[0] for x in pairs],[x[1] for x in pairs]).tolist()
                inputs['fires'][fire['id']]=dict(Q_fuel_kW=q,soot_yield=c['SOOT_YIELD'],
                    heat_of_combustion_kJ_kg=c['HEAT_OF_COMBUSTION'],basis='saved case.in CHEM and prescribed TABL, linear interpolation on output grid')
            inputs['sources'][str(source.relative_to(ROOT))]=sha(source)
        else:
            result=read(source);assert p['time_s']==result['t']
            shared=result.get('shared_inputs',{}).get('fuels_by_room',{})
            model_path=path.parent/'sample.json';chems={};deck_verified=False
            if model_path.exists():
                raw=read(model_path)['scenario'];model,_,manifest=prepare(raw)
                deck=make_deck(model,[],model.get('explicit_candidates',[]))
                deck_verified=hashlib.sha256(deck.encode()).hexdigest()==result.get('shared_inputs',{}).get('deck_sha256')
                if deck_verified:chems={r['ID']:r for k,r in records(deck) if k=='CHEM'}
                inputs['sources'][str(model_path.relative_to(ROOT))]=sha(model_path)
            by_room={r['id']:r for r in result['rooms']}
            for fire in p['fires']:
                rid=fire.get('solver_id',fire['cad_key']);r=by_room.get(rid,{});c=chems.get('F_'+fire['id'],{})
                inputs['fires'][fire['id']]=dict(Q_fuel_kW=r.get('supply_HRR_kW'),
                    soot_yield=c.get('SOOT_YIELD'),heat_of_combustion_kJ_kg=shared.get(rid,{}).get('heat_of_combustion_J_kg',0)/1000 or None,
                    basis='saved supply_HRR_kW; '+('CHEM reconstructed with identical saved deck SHA' if deck_verified else 'soot unavailable: display-config fallback'))
            inputs['sources'][str(source.relative_to(ROOT))]=sha(source)
            inputs['deck_sha_verified']=deck_verified
        for room in p['rooms']:
            values=[v for f in p['fires'] if f['cad_key']==room['key'] for v in [inputs['fires'].get(f['id'],{})] if v.get('Q_fuel_kW') is not None]
            inputs['rooms'][room['solver_id']]={'Q_fuel_kW':[sum(v['Q_fuel_kW'][i] for v in values) for i in range(len(p['time_s']))] if values else None}
        p['display_inputs']=inputs;assert core_digest(p)==before
        # Keep old physical/index fields byte-equivalent after JSON decoding.
        path.write_text(json.dumps(p,ensure_ascii=False,separators=(',',':'),allow_nan=False),encoding='utf-8',newline='\n')
        report.append(dict(path=str(path.relative_to(ROOT)),status='display_inputs added',physical_and_conditions_digest=before,
            physical_and_conditions_unchanged=core_digest(read(path))==before,fire_count=len(inputs['fires']),
            missing_soot=sum(v['soot_yield'] is None for v in inputs['fires'].values()),sources=inputs['sources']))
    (review/'input-enrichment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
