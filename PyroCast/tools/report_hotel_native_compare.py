"""Read saved lite/native output only; shared scoring, no simulation or tuning."""
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation'),str(ROOT/'simulation/deps')]
from pyrocast_cfbt.native import read_native_csv, digest
from pyrocast_cfbt.conditions import _finite
from pyrocast_cfbt.criteria import evaluate_cell, CONDITION_VERSION
from pyrocast_cfbt.native_criteria import evaluate_native
from run_hotel_native_compare import OUT, SOURCE


def read(p):return json.loads(p.read_text('utf-8'))
def save(p,v):p.write_text(json.dumps(_finite(v),ensure_ascii=False,indent=2,allow_nan=False),'utf-8')
def peak(t,a):
    a=np.asarray(a,dtype=float);valid=np.isfinite(a)
    if not valid.any():return None
    j=np.flatnonzero(valid)[np.argmax(a[valid])]
    return dict(value=float(a[j]),time_s=float(t[j]))
def first(t,a,threshold):
    hits=np.flatnonzero(np.asarray(a,dtype=float)>=threshold)
    return float(t[hits[0]]) if len(hits) else None


def main():
    status=read(OUT/'comparison-run-status.json')
    complete=status['state']=='complete'
    if not complete and '--allow-partial' not in sys.argv:
        raise ValueError('Native comparison incomplete; use explicit --allow-partial for common-prefix analysis only')
    horizon=3600. if complete else read(OUT/'partial-analysis.json')['horizon_s']
    model=read(OUT/'scenario.json');lite=read(SOURCE/'result.json')
    native_safe_horizon=horizon
    horizon=max(float(at) for at in lite['t'] if at<=native_safe_horizon)
    evidence=read(OUT/'comparison-input-evidence.json')
    assert all(digest(SOURCE/name)==sha for name,sha in evidence['source_hashes'].items())
    assert digest(Path(evidence['native_engine']))==evidence['engine_sha256']
    # Compare saved solver fields with the CURRENT formula; keep provenance of both.
    previous_conditions_sha256=evidence['conditions_sha256']
    c,cids,cu=read_native_csv(OUT/'case_compartments.csv',horizon)
    m,_,mu=read_native_csv(OUT/'case_masses.csv',horizon);v,vid,_=read_native_csv(OUT/'case_vents.csv',horizon)
    assert np.array_equal(c['Time'],m['Time']) and np.array_equal(c['Time'],v['Time'])
    mask=c['Time']<=horizon;t=c['Time'][mask];lmask=np.array(lite['t'])<=horizon;lt=np.array(lite['t'])[lmask]
    openings={}
    for op in model['openings']:
        key=next(k for k in v if k.startswith('WF_') and vid[k]==op['id'])
        openings[op['id']]={'fraction':v[key][mask]}
        assert np.allclose(openings[op['id']]['fraction'],op['schedule'][0][1],atol=1e-8),op['id']
    shared=evaluate_native(model,c,m,openings)
    series={};summary=[]
    for i,room in enumerate(model['rooms'],1):
        rid=room['id'];lr=next(r for r in lite['rooms'] if r['id']==rid)
        assert cids[f'ULT_{i}']==rid and cu[f'ULO2_{i}']=='mol_frac' and mu[f'ULMTUHC_{i}']=='kg'
        mass=sum(m[f'ULM{s}_{i}'][mask] for s in ('N2','O2','CO2','CO','HCN','HCL','TUHC','H2O','OD'))
        fuel=m[f'ULMTUHC_{i}'][mask]
        yf=np.divide(fuel,mass,out=np.full(len(t),np.nan),where=mass>0)
        q=np.zeros(len(t))
        for j,g in enumerate(model['fuel_groups'],1):
            if g['room']==rid:
                assert cu[f'HRR_{j}']=='W'
                assert cids[f'HRR_{j}'].strip()=='F_'+g['id']
                q+=c[f'HRR_{j}'][mask]/1000
        def column(name):
            # Native single-zone compartments omit lower-layer fields.
            return c[name][mask] if name in c else np.full(len(t),np.nan)
        T=c[f'ULT_{i}'][mask];Ou=c[f'ULO2_{i}'][mask]*100;Ol=column(f'LLO2_{i}')*100
        jet=c[f'DJET_{i}'][mask]/1000
        records={label:shared[rid][key]['scores'] for label,key in [('FO','FO'),('FGI','FGI'),('BD','backdraft')]}
        ns=dict(T_upper_C=T,T_lower_C=column(f'LLT_{i}'),O2_upper_percent=Ou,O2_lower_percent=Ol,
            fuel_upper_fraction=yf,fuel_upper_kg=fuel,actual_HRR_kW=q,received_jet_kW=jet,interface_m=column(f'HGT_{i}'))
        ls=dict(T_upper_C=np.array(lr['T_u']),T_lower_C=np.array(lr['T_l']),O2_upper_percent=np.array(lr['O2_u']),
            fuel_upper_fraction=np.array(lr['Yf_u']),actual_HRR_kW=np.array(lr['actual_HRR_kW']),
            supply_HRR_kW=np.array(lr['supply_HRR_kW']),received_jet_kW=np.array(lr['door_jet_HRR_kW']),
            upper_reaction_kW=np.array(lr['upper_HRR_kW']),interface_m=np.array(lr['z_int']))
        ls={k:a[lmask] for k,a in ls.items()}
        parent=room.get('parent_room',rid)
        siblings={r['id'] for r in model['rooms'] if r.get('parent_room',r['id'])==parent}
        own=sum((np.asarray(r['actual_HRR_kW'])[lmask] for r in lite['rooms'] if r['id'] in siblings),np.zeros(len(lt)))
        lc=evaluate_cell(model,room,lt,ls['T_upper_C'],ls['interface_m'],ls['O2_upper_percent'],ls['fuel_upper_fraction'],
            ls['actual_HRR_kW'],ls['upper_reaction_kW'],ls['received_jet_kW'],own_fire=own)
        for label,lkey in [('FO','FO'),('FGI','FGI'),('BD','backdraft')]:
            ns[label]=100*np.asarray(records[label]['degree'],dtype=float)
            ls[label]=100*np.asarray(lc[lkey]['scores']['degree'],dtype=float)
        series[rid]=dict(native=ns,lite=ls)
        entry=dict(room=rid)
        for engine,times,values in [('native',t,ns),('lite',lt,ls)]:
            entry[engine]={k:peak(times,values[k]) for k in ('T_upper_C','T_lower_C','fuel_upper_fraction','actual_HRR_kW','received_jet_kW','FO','FGI','BD')}
            entry[engine]['O2_upper_min_percent']=float(np.nanmin(values['O2_upper_percent']))
            entry[engine]['indices']={k:dict(first_70_s=first(times,values[k],70),first_100_s=first(times,values[k],100),known_samples=int(np.isfinite(values[k]).sum())) for k in ('FO','FGI','BD')}
            entry[engine]['burning']=bool(np.any(values['actual_HRR_kW']>0))
            entry[engine]['actual_source_energy_MJ']=float(np.trapezoid(values['actual_HRR_kW'],times)/1000)
            entry[engine]['received_jet_energy_MJ']=float(np.trapezoid(values['received_jet_kW'],times)/1000)
            entry[engine]['peak_bottleneck']={}
            for label,lkey in [('FO','FO'),('FGI','FGI'),('BD','backdraft')]:
                p=entry[engine][label]
                if p is None:continue
                j=int(np.flatnonzero(times==p['time_s'])[0])
                weakest=records[label]['weakest'] if engine=='native' else lc[lkey]['scores']['weakest']
                entry[engine]['peak_bottleneck'][label]=weakest[j]
        summary.append(entry)
    prior=next(r for r in read(SOURCE.parents[1]/'progress.json')['rows'] if r['building']=='parkmarine' and r['floor']=='5F')
    output=dict(condition_version=CONDITION_VERSION,previous_conditions_sha256=previous_conditions_sha256,complete=complete,compared_horizon_s=float(t[-1]),native_safe_horizon_s=native_safe_horizon,source='same frozen raw input and identical r8 manifest; different solvers and ignition observables',
        native_run=status, lite_wall_s=prior['wall_s'],lite_integration_s=lite['integration'].get('wall_seconds'),
        conditions_sha256=digest(ROOT/'simulation/pyrocast_cfbt/conditions.py'),native_last_s=float(t[-1]),lite_last_s=float(lt[-1]),
        shared_FGI_BD_series_verified=2*len(summary),fixed_opening_series_verified=len(openings),
        native_burning=[r['room'] for r in summary if r['native']['burning']],lite_burning=[r['room'] for r in summary if r['lite']['burning']],rooms=summary,
        limits=['one fixed ventilation scenario, not all hotel conditions',
                'native plate triggers versus lite gas-temperature triggers',
                'stock TUHC and lite effective unburned fuel are model quantities, not measured composition',
                'unknown zero-upper-mass samples and omitted native single-zone lower-layer fields preserved as null; no interpolation in threshold times',
                'native HRR is per fire, DJET per receiving compartment; mass sum excludes duplicate diagnostics'])
    save(OUT/'comparison.json',output);save(OUT/'comparison-series.json',dict(native_time_s=t,lite_time_s=lt,rooms=series))
    rid=read(SOURCE/'request.json')['room'];snapshots=[]
    for at in (300,600,620,690,900,1800,3600):
        if at>min(t[-1],lt[-1]):continue
        row=dict(time_s=at)
        for engine,times in [('native',t),('lite',lt)]:
            hits=np.flatnonzero(np.isclose(times,at,rtol=0,atol=1e-6))
            if len(hits)!=1:continue
            j=int(hits[0]);row[engine]={k:float(series[rid][engine][k][j]) for k in ('T_upper_C','O2_upper_percent','fuel_upper_fraction','actual_HRR_kW','FO','FGI','BD')}
        snapshots.append(row)
    save(OUT/'origin-same-time.json',dict(room=rid,samples=snapshots,interpolated=False))
    sys.path.append(str(ROOT/'simulation/plot_deps'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    origin=read(SOURCE/'request.json')['room']
    for rid in (origin,'CAD_5F_R1'):
        fig,axes=plt.subplots(4,2,figsize=(13,12),sharex=True)
        for ax,key in zip(axes.flat,('T_upper_C','T_lower_C','O2_upper_percent','fuel_upper_fraction','actual_HRR_kW','FO','FGI','BD')):
            ax.plot(lt/60,series[rid]['lite'][key],label='Lite',color='#2474b5')
            ax.plot(t/60,series[rid]['native'][key],label='Stock CFAST',color='#d94f30')
            if key=='actual_HRR_kW':ax.plot(lt/60,series[rid]['lite']['supply_HRR_kW'],'--',label='Lite supply',color='#777777')
            if key in ('FO','FGI','BD'):ax.axhline(100,color='black',ls=':',lw=.8)
            ax.set_ylabel(key);ax.grid(alpha=.2);ax.legend(fontsize=8)
        for ax in axes[-1]:ax.set_xlabel('Time (min)')
        fig.suptitle(rid+(' | COMPLETE' if complete else ' | PARTIAL COMMON PREFIX')+' | distinct ignition observables');fig.tight_layout()
        fig.savefig(OUT/(rid+'-comparison.png'),dpi=150);plt.close(fig)
    lines=['# 호텔 5F 순정 CFAST 1회 대조','',
        f"상태: {'3600 s 완료' if complete else '미완료 · 공통 부분 구간만 비교'} / 비교 끝 {t[-1]:g} s. 이후 구간은 미평가.",'',
        '같은 저장 입력·r8 manifest. 문·창 상태 고정, 창 파괴 OFF. 간략 재실행·baseline 실행 없음. 운영 재생은 자동 교체하지 않음.','',
        '|실|상층 최고 ℃ 간략 / CFAST|미연 연료 최고 kg/kg 간략 / CFAST|FGI 최고 간략 / CFAST|BD 최고 간략 / CFAST|','|---|---:|---:|---:|---:|']
    for r in summary:
        def display(engine,key):
            value=r[engine][key]
            return f"{value['value']:.5g}" if value else '—'
        vals=[display('lite',k)+' / '+display('native',k) for k in ('T_upper_C','fuel_upper_fraction','FGI','BD')]
        lines.append('|'+r['room']+'|'+'|'.join(vals)+'|')
    lines+=['','세부 최고 시각·70/100 최초 표본 시각: comparison.json. 시각 보간 없음.',
        '지수는 공통 조건식의 사후 계산이다. 상층 TUHC 재고는 순정 CSV 질량으로 환산하며, 간략 재고는 간략 엔진의 유효 미연 연료이다. 실제 발생 확률이나 검증된 농도라는 뜻은 아니다.']
    (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n','utf-8')
    print(json.dumps(next(r for r in summary if r['room']==origin),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
