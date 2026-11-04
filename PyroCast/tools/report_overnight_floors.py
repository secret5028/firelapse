"""Read finished batch outputs without running or changing a simulation."""
from datetime import datetime, timezone
import math
from pathlib import Path
from run_overnight_floors import OUT, ROOT, read, save

DEST=ROOT/'reviews/overnight-20261104'

def report():
    progress=read(OUT/'progress.json') or read(OUT/'plan.json')
    rows=[]
    for item in progress['rows']:
        folder=Path(item['folder'])
        row={k:item.get(k) for k in ('building','floor','origin','state','engine','opening_state','wall_s','error','isolated_rooms','input_sha256')}
        row.update(burning_rooms=None,integration_s=None,peaks=None,partial_conditions=[])
        if row['state']=='complete':
            summary=read(folder/'summary.json');pb=read(folder/'playback.json')
            row['burning_rooms']=[rid for rid,v in summary['rooms'].items() if v['burning']]
            row['integration_s']=summary['integration_s'];row['peaks']={}
            for phenomenon in ('FO','FGI','backdraft'):
                candidates=[]
                for room in pb['rooms']:
                    sid=room['solver_id'];condition=pb['solvers'][sid]['conditions'].get(phenomenon,{})
                    if condition.get('status') not in ('evaluated','partially_evaluated'):continue
                    if condition.get('status')=='partially_evaluated':
                        row['partial_conditions'].append(dict(cell=sid,phenomenon=phenomenon,coverage=condition.get('score_coverage')))
                    values=condition.get('scores',{}).get('degree',[])
                    for t,value in zip(pb['time_s'],values):
                        if isinstance(value,(float,int)) and not isinstance(value,bool) and math.isfinite(value):
                            candidates.append((value,t,room['original_room'],sid))
                if candidates:
                    value,t,rid,sid=min(candidates,key=lambda r:(-r[0],r[1],r[2],r[3]))
                    row['peaks'][phenomenon]=dict(index=100*value,time_s=t,room=rid,cell=sid)
                else:row['peaks'][phenomenon]=None
        rows.append(row)
    save(DEST/'floor-status.json',dict(updated_utc=datetime.now(timezone.utc).isoformat(),rows=rows))
    def number(value):return '—' if value is None else f'{value:.2f}'
    def peak(row,key):
        v=(row['peaks'] or {}).get(key)
        return '—' if v is None else f"{v['index']:.1f} @ {v['time_s']:g}s ({v['room']})"
    lines=['# 층별 진행 현황','', '간략 엔진, 3600 s, 기존 후보 점수 1위. 최악 급기 탐색 결과가 아닌 대표 시나리오. 미실행/실패는 —. 최고값은 평가된 표본 범위만 사용하며, 일부 미평가 시각과 셀은 JSON의 partial_conditions에 기록.','',
           '|건물|층|화점|상태|적분 s|전체 s|연소 실 수|FO 최고|FGI 최고|BD 최고|',
           '|---|---|---|---|---:|---:|---:|---|---|---|']
    for r in rows:
        count='—' if r['burning_rooms'] is None else str(len(r['burning_rooms']))
        lines.append('|'+ '|'.join([r['building'],r['floor'],r['origin'] or '—',r['state'],number(r['integration_s']),number(r['wall_s']),count,peak(r,'FO'),peak(r,'FGI'),peak(r,'backdraft')])+'|')
    (DEST/'floor-status.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    return {state:sum(r['state']==state for r in rows) for state in sorted({r['state'] for r in rows})}

if __name__=='__main__':print(report())
