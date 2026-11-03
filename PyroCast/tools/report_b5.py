"""Summarize saved UI captures; no simulations or data corrections."""
import json
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reviews/B5-20261103'

def main():
    captured=json.loads((OUT/'after/capture.json').read_text('utf-8'))
    comparisons=[]
    pairs=[(p,OUT/'after'/p.name) for p in sorted((OUT/'before').glob('*.png'))]
    pairs.append((OUT/'after/roundtrip-before.png',OUT/'after/roundtrip-after.png'))
    for before,after in pairs:
        a=np.asarray(Image.open(before));b=np.asarray(Image.open(after));d=np.abs(a.astype('int16')-b.astype('int16'))
        comparisons.append(dict(scene=before.stem,pixels=int(np.any(d,axis=-1).sum()),maximum=int(d.max())))
    (OUT/'pixel-comparison.json').write_text(json.dumps(comparisons,ensure_ascii=False,indent=2)+'\n','utf-8')
    assert not captured['errors'] and all(r['pixels']==0 for r in comparisons)
    text=['# B-5 옵션 검수 — 2026-11-03','',
          '새 옵션만 추가했습니다. 표시 탭에서 연기 표현 **그을음·온도**, 화염 표현 **4단계**를 선택합니다. 기본값은 둘 다 **현재**입니다. 검수 후 기본 전환은 별도입니다.',
          '', '## 검증', '', '| 기본 장면 / 왕복 | 변경 픽셀 | 최대 채널 차이 |','|---|---:|---:|']
    text += [f"| {r['scene']} | {r['pixels']} | {r['maximum']} |" for r in comparisons]
    text += ['', '브라우저 오류 0. clock=180000 ms, 1280×720, DPR 1. 비교는 3D 캔버스 전체이며 옵션 캡처는 패널 포함입니다. `app/tests/b5_classification.mjs`는 경계 0.8·15%, 공급값 미확인, source/receiver 분리, 옵션 왕복을 검사했습니다.',
             '', '## 판정 자료', '',
             'O₂는 각 화염이 공기를 받는 층의 체적분율입니다. R2는 합성 평균이 아닌 셀별 값입니다. Q는 kW, 온도는 ℃. 표의 r은 현재 실제 HRR/이 화원의 저장 실제 HRR 최고값입니다.',
             '', '| 사례·초 | 화염 위치 | 상층 T | 사용 O₂ % | Q 실제 | Q 공급 | 실제/공급 | r | 단계 |','|---|---|---:|---:|---:|---:|---:|---:|---|']
    num=lambda v: '미확인' if v is None else f'{v:.3f}'
    for r in captured['options']:
        if not r['name'].endswith('-iso'):continue
        s=r['stats'];case=r['name'].removesuffix('-iso')
        rows=[(c['room'].replace('CAD_3F_','3F '),c) for c in s['combustion'] if c['room'] in ['CAD_3F_R2_C0','CAD_3F_R2_C1','CAD_3F_R2_C2']]
        rows += [('공동 벽면',w['combustion']) for w in s['wallGlows']]
        rows += [('R5 수신 '+j['vent'],j['combustion']) for j in s['doorJets'] if case.startswith('Wando')]
        for name,c in rows:
            values=[c['Tu'],c['oxygen_vol_percent'],c['q_kW'],c['supply_kW'],c['supply_ratio'],c['ratio']]
            text.append('| '+case+' | '+name+' | '+' | '.join(map(num,values))+' | '+c['label']+' |')
    text += ['',
        '- 완도 1,000초: 공동 하층 O₂는 **20.5579%**, 상층 O₂는 **0.3616%**입니다. “공동 하층 0.4%”와 저장 자료가 다릅니다. 상층을 하층으로 바꾸어 읽지 않았습니다. 공동 실제/공급=172.323/2930.692=**5.88%**로 ④입니다.',
        '- 1,000초 R5 수신 분출 HRR=0이므로 분출 화염은 없습니다. 1,400·2,100초 분출은 받는 실 하층 O₂ 약 **20.56%**, HRR 비율에 따른 ①로 표시됩니다. **안전 판정이 아닙니다.**',
        '- 순정 완도 출력에는 개구부별 유입 미연 연료 공급량이 없어 분출 actual/supply는 **미확인**입니다. 공동 화원의 공급량을 대신 쓰지 않습니다. 산소 항과 저장 HRR 단계로만 표시하며 `partial:true`를 남깁니다.',
        '- 간략 분출은 저장 `fuel_in_kg_s × heat_of_combustion_kJ_kg`가 있을 때만 분출 공급 발열량을 계산합니다. 엔진에 되먹임하지 않습니다.',
        '- 3F 600초 R2_C0은 r≈0.416으로 ②, 2,400초 R2_C0/C2는 r=1로 ③입니다. 요청 캡처 시각의 “초기·쇠퇴” 별칭에 맞추어 단계를 강제하지 않았습니다.',
        '', '## 색·입력 출처와 한계', '',
        '- CHEM soot yield: S09 **0.02**, 완도 P1 **0.1**. S09 CHEM은 저장 sample로 덱을 재구성한 SHA가 저장 덱 SHA와 일치할 때만 사용합니다. .015 또는 .1을 건물에 임의 대입하지 않았습니다.',
        '- 연기 색 지배 화원: 같은 실 실제 HRR 최대 → 수신 분출의 공급 실 → 건물 내 실제 HRR 최대의 대용값 순입니다. 연료 성분별 이송을 계산하지 않으므로 마지막 단계는 `proxy`로 기록합니다. CHEM 미확인 시만 config 기본 .1입니다.',
        '- `config/display.json`이 표시 상수의 원본입니다. 번들 빌드가 기존 served shader 모듈의 표시 상수 블록을 생성합니다. 새 서버 경로는 없습니다.',
        '- 그을음 캡 계수 [.32,.20,.10,.45]는 **시각화 가정**이며 질량 계산값이 아닙니다. 두께는 이 계수×(1−산소/공급 충분도)입니다. HRR 크기·CAD 마스크·OD 불투명도·renderOrder는 유지합니다.',
        '- 온도 발광은 450~800℃의 RGB 표현 규칙이며 실제 흑체 방사량 계산이 아닙니다. ④는 암적, 느린 맥동·1.4배 흔들림, 조명/벽면 발광 강도 절반입니다.',
        '- 저장 12건에 `display_inputs`만 추가했습니다. 모든 기존 수치·조건표의 디코딩 후 해시는 불변이며 재계산은 **0회**입니다. 상세 증거: [input-enrichment.json](input-enrichment.json). 앞으로 다른 저장 결과를 보강할 때도 같은 도구를 사용합니다. 값이 없으면 미확인으로 남습니다.',
        '- `protected-files.json`: 엔진·조건표·서버·렌더 순서 등 54파일의 HEAD 본문과 일치. 8개는 작업 이전 체크아웃 간 줄바꿈 차이가 있어 바이트 SHA와 줄바꿈 정규화 비교를 구분했습니다. 이 작업에서 해당 파일 수정은 없습니다.',
        '', '## 검수 캡처', '', '| 사례·초 | 비스듬히 | 실 확대 |','|---|---|---|']
    for case,times in [('S09',[600,1420,2400]),('Wando-P1',[1000,1400,2100])]:
        for t in times:text.append(f'| {case} {t} s | [캡처](after/{case}-{t}-iso.png) | [캡처](after/{case}-{t}-room.png) |')
    text += ['', '## 수정 파일·줄 수', '', '커밋 범위의 파일별 추가/삭제 줄 수는 [diff-lines.txt](diff-lines.txt)를 참조합니다. 기본값 전환·새 시뮬레이션·push는 하지 않았습니다.']
    (OUT/'report.md').write_text('\n'.join(text)+'\n','utf-8')
    print(json.dumps(comparisons,ensure_ascii=False))

if __name__=='__main__':main()
