# 롤오버 재정의 검수

- 재계산: 0회. 저장된 FGI·HRR·개방률만 사용.
- 3F 지수 결과 24건 + 완도 P1/P2/P4/P5 3건 = 30사례, 원래 실 단위 684행. 최고값 변화 244행.
- 현재 개방률 > 0인 간선으로 원래 방 그래프를 구성. 모든 동거리 최소 간선 수 경로 포함. 화점실 포함 및 자체 실제 HRR 점화원 인정(사용자 확정).
- 셀별 FGI는 보존, 실별 보고는 기존 정책인 셀 최댓값/최초 시각. 온도·산소·HRR 및 FO·FGI·BD 불변.
- 경로·점화원 4시험 + 기존 조건/문 7시험 통과.
- 완도 P1 R5: 첫 100 도달 2120 s, 수신 jet 616.745 kW, 최고 114.097 @2305 s. 종전 최고 82.043 @2095 s.
- 원본 CSV/PNG는 보존. 예전 PNG의 롤오버 곡선은 이전 정의이며 이 보고의 CSV가 최신 비교표.
- 변경 전 파일: simulation/results/rollover_route_20261103/before.zip. 대용량 결과는 로컬 보존, 코드와 비교표를 커밋.

명세 4.1: 롤오버 = FGI × 현재 개방 상태 화점→외기 최단 경로 × (직전 상류 실제 HRR>0 또는 수신 jet>0); include_origin 기본 true이면 화점 자체 HRR 인정.

## 자료 부족 보관본 (31건)
기존 FGI 지수/실제 HRR가 없는 오래된 native 결과. 미평가이며 0으로 채우거나 현재 규칙으로 추정하지 않음.

| 사례 | 사유 |
|---|---|
| cad_exterior_risk_demo | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| cad_exterior_risk_demo_v2 | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| cad_exterior_risk_demo_v3 | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| cad_exterior_risk_demo_v4_ceiling | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| cad_floor | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| cad_interactive/cee3fee4fdeb019a | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| cad_low_threshold | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| cad_opening_30min | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| cad_practical_30min | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| cad_whole_verified | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| condition_display_v1 | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| floor_spread_20261022/r1_30mw | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| floor_spread_20261022/r1_50mw | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| floor_spread_20261022/r2_ventilated | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| floor_spread_20261022/r4_uniform_bounded | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| mixture_r2_20261022/cad30_view_legacy | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| mixture_r2_20261022/cad30_view_mixture | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| mixture_r2_20261022/enriched_floor60 | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| mixture_r2_20261022/enriched_floor60_v2 | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| mixture_r2_20261022/enriched_floor60_v3 | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| mixture_r2_20261022/enriched_floor60_v4 | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| mixture_r2_20261022/enriched_floor60_v5 | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| mixture_r2_20261022/enriched_floor60_v6 | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| mixture_r2_20261022/enriched_floor60_v7 | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| mixture_r3f_cache_20261023/floor60 | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| topology_audit_20261022/floor_corrected_30min | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| topology_audit_20261022/vertical_corrected_30min | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| window_r8_20261022/floor_no_windows_30min | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| window_r8_20261022/floor_windows_30min | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| window_r8_20261022/floor_windows_30min_ventilated | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
| window_r8_20261022/floor_windows_60min_ventilated | saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero |
