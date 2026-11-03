"""Verify and report B5 display follow-up; no simulation or stored-result edits."""
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reviews/B5-followup-20261103'

def main():
    read=lambda p:json.loads(p.read_text('utf-8'))
    before=read(OUT/'protected-before.json')
    preserved={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in before.items()}
    captures=read(OUT/'after/capture.json')
    frames=captures['defaults']+captures['options']
    assert all(preserved.values()) and not captures['errors']
    assert len(captures['options'])==12
    assert all(f['stats']['lowerVolumeCount']==0 for f in frames)
    a=np.asarray(Image.open(OUT/'after/roundtrip-before.png'))
    b=np.asarray(Image.open(OUT/'after/roundtrip-after.png'))
    changed=int(np.any(a!=b,axis=-1).sum());assert changed==0
    old=read(OUT/'before/jet-diagnostic.json');new=read(OUT/'after/jet-diagnostic.json')
    jets=[]
    for x in new['geometry']:
        prior=next(y for y in old['geometry'] if y['name']==x['name'])
        assert x['values']['q_kW']==prior['values']['q_kW']
        assert x['scale']==prior['scale']
        jets.append(dict(name=x['name'],q_kW=x['values']['q_kW'],scale=x['scale'],mask_pass=x['maskPass'],HRR_and_size_unchanged=True))
    payload=dict(protected_files_unchanged=preserved,lower_smoke_mesh_count=0,frames_checked=len(frames),
                 browser_errors=captures['errors'],option_roundtrip_changed_pixels=changed,jets=jets,recalculations=0)
    (OUT/'verification.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n','utf-8',newline='\n')
    text=['# B-5 표시 보완 검수 — 2026-11-03','',
          '5개 보완을 한 커밋으로 반영했습니다. 그을음·4단계는 계속 검수용 옵션이며 기본 선택은 현재입니다. 하층 연기는 사용자의 최종 지시에 따라 모든 모드에서 제거했습니다. 토글·임계값은 없습니다.',
          '', '## 반영 내용', '',
          '| 항목 | 적용 |','|---|---|',
          '| 바탕 밝기 | `0.48−3.2×soot`: .015→.432, .1→.160. 가장자리 추가 밝기는 정규화 노이즈 밀도 n<.3에만, 갈색 가중 .5 |',
          '| 온도 발광 | n>.3부터, 450→600 ℃에서 붉은 내부 표현을 강화. 600 ℃ 이상에서 명확한 적색. 주황·노랑은 화염에만 사용 |',
          '| 그을음 캡 | 레이 전체 누적 불투명도 최대 .5, 방사형 분포 반경 계수 1.5, 부드러운 가장자리와 위쪽 소멸. 기존 메쉬·실 마스크 안에서 표현 |',
          '| 분출 화염 | 공동 벽면 발광 r19 → 화염 r20 순으로 가림 해소. 개구부 분출은 격자 혀 대신 연속 원뿔형 프로파일. HRR·단면 크기·Heskestad 길이 유지 |',
          '| 2존 | 상층 메쉬만 생성. 상층 하단 경계 흐림 최대 3 cm. 하층 ODl·온도·산소 계산값은 그대로 보존 |',
          '', '## 완도 분출 수치 확인', '',
          '저장된 원본 `case_compartments.csv`의 ROOM 수신 열은 `DJET_1`입니다. 6.5 MW를 1,400초의 발열량으로 대입하지 않았습니다.',
          '', '| 항목 | 값 |','|---|---:|',
          '| ROOM 수신 분출 최고 | 6,461.767 kW @ 약 1,325 s |',
          '| ROOM 수신 분출 @ 1,400 s | 902.533 kW |',
          '| CUT 표시 배분 @ 1,400 s | 799.995 kW |',
          '| TOP_GAP 표시 배분 @ 1,400 s | 102.538 kW |',
          '| CUT 단면 폭 × 높이 | 1.427 × 1.427 m |',
          '| CUT Heskestad 수평 길이(고정 clock 맥동 포함) | 1.943 m |',
          '', '개구부별 HRR은 기존 표시용 배분이며 순정 CFAST 개구부별 직접 출력이 아닙니다. 배분 합계·저장값·크기는 수정하지 않았습니다. 마스크 통과율은 CUT 100%, TOP_GAP 93.75%입니다. 기존 가림은 화염 생성 실패가 아니라 공동 벽면 발광의 합성 순서 문제였습니다.',
          '', '## 검증', '',
          f'- 엔진·조건표·서버·렌더 순서 파일·재생 데이터·원본 CSV 등 **{len(preserved)}개 SHA 불변**.',
          f'- 기본 4장면 + 옵션 12장면 총 **{len(frames)}장면에서 하층 메쉬 0개**. 브라우저 오류 0. 옵션 왕복 변경 픽셀 0.',
          '- 기존 기본 캡처와의 픽셀 0은 이번 변경의 합격 조건이 아닙니다. 하층 삭제·선명한 경계·분출 가림 해소는 현재 모드에도 적용되는 승인된 차이입니다.',
          '- 시뮬레이션 재실행 0회. 저장된 지수·연소량·산소·광학밀도·경계 높이 변경 없음.',
          '- 색상·발광·그을음 캡은 표시 효과입니다. 시뮬레이션의 공간별 온도장·그을음 이동을 추가 계산하지 않습니다.',
          '', '## 같은 6시점 캡처', '', '| 사례·시각 | 비스듬히 | 실 확대 |','|---|---|---|']
    for case,times in [('S09',[600,1420,2400]),('Wando-P1',[1000,1400,2100])]:
        for t in times:text.append(f'| {case} {t} s | [캡처](after/{case}-{t}-iso.png) | [캡처](after/{case}-{t}-room.png) |')
    text += ['', '## 파일별 변경량', '', '[diff-lines.txt](diff-lines.txt). 기본 색 옵션 전환과 push는 하지 않았습니다.']
    (OUT/'report.md').write_text('\n'.join(text)+'\n','utf-8',newline='\n')
    print(f'PASS: {len(preserved)} protected files, {len(frames)} upper-only frames, 12 captures, roundtrip pixels {changed}')

if __name__=='__main__':main()
