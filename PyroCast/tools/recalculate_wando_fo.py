"""Saved-output diagnostic refresh. No native engine execution or raw overwrite."""
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'simulation'))
from pyrocast_cfbt.thermal_fo import temperature_scores

OUT=ROOT/'simulation/results/wando_FO_thermal_20261102'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    summaries={}
    for case in ('P1','P2','P4'):
        src=ROOT/f'simulation/results/wando_C11_{case}_20261102'
        read=lambda name:json.loads((src/name).read_text(encoding='utf-8'))
        model=read('model.json');raw=read('timeseries.json');t=raw['time_s']
        scores={rid:temperature_scores(raw[rid]['T_upper_C'],model['criteria']['fo_temperature_C']) for rid in ('ROOM','CAVITY')}
        def stats(sc):
            a=sc['degree'];j=max(range(len(t)),key=lambda i:a[i])
            first=lambda limit:next((t[i] for i,x in enumerate(a) if x>=limit),None)
            return dict(peak=a[j]*100,peak_time_s=t[j],first_70_s=first(.7),first_100_s=first(1),
                        at_2100=a[min(range(len(t)),key=lambda i:abs(t[i]-2100))]*100)
        summary={rid:stats(s) for rid,s in scores.items()};summaries[case]=summary
        evidence=dict(scenario=case,diagnostic_revision='upper_layer_temperature_only_v1',
            time_s=t,scores=scores,summary=summary,simulation_runs=0,floor_flux='not_evaluated',
            source_sha256={name:hashlib.sha256((src/name).read_bytes()).hexdigest()
                for name in ('model.json','case.in','case_compartments.csv','timeseries.json','condition-scores.json')})
        (OUT/f'{case}-thermal-fo.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    # Threshold and unavailable-data handling, no fuel/oxygen gate.
    check=temperature_scores([0.,300.,600.,None,float('nan')],600.)
    assert check['degree']==[0.,.5,1.,None,None]
    assert check['all_met']==[False,False,True,None,None]
    assert check['factors']['fuel']==[None]*5
    def at(x):
        if x is None:return '미도달'
        s=round(x);return f'{s//60:02d}:{s%60:02d}'
    lines=['# 완도 FO 열적 조건 표시 수정 — 2026-11-03','',
        'R5 자체 벽의 강판 뒤 우레탄 화재를 CAVITY라는 별도 계산 구획으로 분리했다. 외부 화재가 아니다.',
        '기존 자체 화원 HRR·산소·온도 최솟값 지수는 ROOM 자체 화원이 없다는 이유로 0이 됐다. 이번 완도 사례 표시에서는 FO를 상층 온도/기존 설정 600℃ ×100으로 재산출했다.',
        '이는 온도 기준 접근도이며 종합 FO 예측·발생 확률·실내 연료 추가 착화가 아니다. 섭씨 비율은 표시용 정규화다. 바닥 복사열은 저장되지 않아 미평가로 남겼다.','',
        '| 사례 | R5 최고 FO 온도 점수 | 시각 | ≥70 | ≥100 | 35분 점수 |','|---|---:|---|---|---|---:|']
    for c,s in summaries.items():
        r=s['ROOM'];lines.append(f"| {c} | {r['peak']:.2f} | {at(r['peak_time_s'])} | {at(r['first_70_s'])} | {at(r['first_100_s'])} | {r['at_2100']:.2f} |")
    lines+=['','- P1 웹 화면의 FO 점수·이력·주의 표시·경로 위험 요약은 수정 점수를 읽는다. FGI·백드래프트·롤오버는 원값 그대로다.',
        '- P1·P2·P4의 원본 입력·CSV·과거 요약·조건표는 보존했다. 새 지수는 별도 `*-thermal-fo.json`으로 저장했고 P1 playback의 이전 FO는 `legacy_combustion_support_scores`에 보존했다.',
        '- CAVITY 고온 점수는 벽체 공동의 열 상태다. R5 실내 전실화재로 합산하거나 동일시하지 않는다.',
        '- CFAST 엔진·공통 conditions.py·화원·산소·연소식·셰이더 불변. 재적분 0회. 다른 건물의 기존 점수는 변경하지 않았다.',
        '- P2·P4는 독립 저장 결과를 후처리했다. 웹 재생 선택기 연결은 이번 수정 범위가 아니므로 현재 화면은 P1이다.','',
        '[P1 화면](../simulation/results/wando_FO_thermal_20261102/R5-1815-FO73.jpg) · [화면 어댑터 검증](../simulation/results/wando_FO_thermal_20261102/verification.json)','']
    (ROOT/'specs/웹앱-완도-FO열적조건-20261103.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(summaries,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
