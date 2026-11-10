# r18 배포 검증 보고서

2026-11-10 · 최종 판정: PASS (제외 항목은 아래 별도 기록)

## 수정과 보존

- 집에서 변경한 원격 main `f2006d4`에서 시작했습니다. 새 CFAST 계산과 외부 AI 요청은 실행하지 않았습니다.
- 압축 보관된 회귀 입력을 안전하게 복원하는 도구와 전체 시험 실행기를 추가했습니다. 이미 존재하는 결과는 덮어쓰지 않습니다.
- 옛 간략 입력의 물성 조회가 불필요한 바닥 센서 개수 제한으로 실패하던 경로를 분리했습니다. 실제 CFAST의 센서 제한과 계산식은 그대로입니다.
- 수관 레이어의 DOM 의존을 host factory로 분리했습니다. 실제 WebGL 장면과 50회 생성·해제 시험을 통과했습니다.
- 읽기 전용 완도/층 미선택 견본주택의 설정·개구부 조회 오류를 수정했습니다.
- 초기 CFAST 결과의 내부 `new-run` 이름을 실제 저장 사례 ID로 전달하여 결과 요약 400 오류를 수정했습니다. 원본 playback 바이트는 불변입니다.
- r17에서 빠진 완도 전용 P1 재생 파일을 저장소 원본과 바이트 동일하게 복원했습니다.
- README 경로와 라이선스 안내를 정리하고 소스 설치기가 r18 및 해당 ZIP SHA를 사용하도록 갱신했습니다.

## 시험

| 항목 | 결과 |
|---|---|
| 전체 실행 항목 | 103개, 최종 종료 코드 실패 0개 |
| Python 시험 | 567개 중 541개 통과, 26개 제외 |
| 시뮬레이션 단위시험 | 333개 중 316개 통과, 17개 제외 |
| 실제 자료 D5 브리핑 | 호텔·아이엔테크·완도 기반 12개 통과, 제외 없음 |
| 건물 화면 | 7개 모두 PASS, 콘솔/HTTP 오류 0 |
| 저장 사례 API | 강화 17·호텔 83·완도 1·아이엔테크 11, 총 112건 정상 응답 |
| 결과 선택 | 해당 층·화점 자동 선택, 재생/시간 이동 확인 |
| 모바일 | 호텔 설정·결과·표시 375px, 가로 넘침 0 |
| 단독 HTML | 호텔·아이엔테크, 서버 종료 후 file:// 재생/이동, 외부 요청 0 |
| Git/ZIP 일치 | 앱 파일 365개 SHA-256, Git blob과 ZIP 바이트 일치 |
| 보존 데이터 | r17 결과·런타임 등 보호 파일 4,412개 변경 0 |

원본 전수 시험에서 장경로 시험 한 건은 새 응답의 case_id 추가로 실패했습니다. 기대 응답에 case_id를 포함하도록 수정하고 재시험 통과했습니다. 원본 파일 해시 불변 검사는 유지했습니다. 최초 결과와 재시험 경로는 TEST-RESULTS.json에 함께 기록했습니다.

## 배포 파일

- ZIP: `FireLapse-Windows-x64-2026.11.10-r18.zip`
- 크기: 372,117,760 bytes (354.88 MiB)
- SHA-256: `6940efa6b76de11ca2c13b17128ae77d189c9ca11b00844d4525e8f68e173ae6`
- 파일: 4,846개, CRC PASS
- 앱 코드 기준: `d308193` (이후 설치기·시험 기대값·보고서 커밋은 앱 코드와 계산 데이터에 영향 없음).
- 보존된 simulation/results/playback.json 114개와 복원된 완도 P1. 목록 노출 112건과 물리 파일 개수는 동일한 지표가 아닙니다.
- 기존 GitHub 릴리스·태그·자산은 삭제하거나 교체하지 않습니다.

## 검증 범위와 제외

새 시뮬레이션, 원본 CAD가 필요한 재추출, 실제 사용자 AI API 연결, 모든 Windows PC/GPU 조합은 이번 검증 대상이 아닙니다. 호텔 B1의 unverified 표시와 결과는 그대로 보존했습니다. 다음 제외는 합격으로 세지 않았습니다.

### simulation

- test_15_degree_frame_line_is_not_assumed_open (test_cad_arc_doors.ArcTests.test_15_degree_frame_line_is_not_assumed_open) ... skipped 'SKIP: evidence folder missing'
- test_r17_real_mixed_bundle (test_cad_arc_doors.ArcTests.test_r17_real_mixed_bundle) ... skipped 'SKIP: evidence folder missing'
- test_existing_fgi_screening_preserved_on_completed_case (test_iteration.ConditionTests.test_existing_fgi_screening_preserved_on_completed_case) ... skipped 'SKIP: evidence folder missing'
- test_fo_unknown_flux_does_not_override_true_temperature (test_iteration.ConditionTests.test_fo_unknown_flux_does_not_override_true_temperature) ... skipped 'SKIP: evidence folder missing'
- test_forced_ignition_keeps_separate_oxygen_threshold_and_time_window (test_iteration.ConditionTests.test_forced_ignition_keeps_separate_oxygen_threshold_and_time_window) ... skipped 'SKIP: evidence folder missing'
- test_forced_and_failed_excluded_from_probability_denominator (test_lite_montecarlo.MCTests.test_forced_and_failed_excluded_from_probability_denominator) ... skipped 'retired mode: oxygen_inventory_mode / rollover sample key / visualization.states — 2026-10 이후 폐기'
- test_internal_transport_conserves_oxygen_no_fresh_air_reset (test_lite_room_oxygen.RoomOxygenTests.test_internal_transport_conserves_oxygen_no_fresh_air_reset) ... skipped 'retired mode: oxygen_inventory_mode / rollover sample key / visualization.states — 2026-10 이후 폐기'
- test_linear_oxygen_cap_no_lol_and_no_negative_stock_reset (test_lite_room_oxygen.RoomOxygenTests.test_linear_oxygen_cap_no_lol_and_no_negative_stock_reset) ... skipped 'retired mode: oxygen_inventory_mode / rollover sample key / visualization.states — 2026-10 이후 폐기'
- test_one_stock_per_room_and_initial_proxy (test_lite_room_oxygen.RoomOxygenTests.test_one_stock_per_room_and_initial_proxy) ... skipped 'retired mode: oxygen_inventory_mode / rollover sample key / visualization.states — 2026-10 이후 폐기'
- test_primary_and_upper_share_one_budget_and_fuel_heat_balance (test_lite_room_oxygen.RoomOxygenTests.test_primary_and_upper_share_one_budget_and_fuel_heat_balance) ... skipped 'retired mode: oxygen_inventory_mode / rollover sample key / visualization.states — 2026-10 이후 폐기'
- test_stage_constants_not_silently_overridden (test_lite_room_oxygen.RoomOxygenTests.test_stage_constants_not_silently_overridden) ... skipped 'retired mode: oxygen_inventory_mode / rollover sample key / visualization.states — 2026-10 이후 폐기'
- test_mc_duration_accepts_untenable_record_level_mask (test_lite_visualization.LiteVisualTests.test_mc_duration_accepts_untenable_record_level_mask) ... skipped 'Local MC output is not bundled'
- test_priority_and_independent_smoke_extent (test_lite_visualization.LiteVisualTests.test_priority_and_independent_smoke_extent) ... skipped 'retired mode: oxygen_inventory_mode / rollover sample key / visualization.states — 2026-10 이후 폐기'
- test_fallback_and_native_only (test_room_rule_r7.R7Tests.test_fallback_and_native_only) ... skipped 'SKIP: evidence folder missing'
- test_full_budget_without_legacy_stall_watchdog_or_retry (test_room_rule_r7_budget.R7BudgetTests.test_full_budget_without_legacy_stall_watchdog_or_retry) ... skipped 'CFAST executable not bundled in source clone'
- test_default_matches_frozen_r7_item_deck (test_room_rule_r8.R8SettingsTests.test_default_matches_frozen_r7_item_deck) ... skipped 'SKIP: evidence folder missing'
- test_single_default_or_exact_two_parallel_no_retry (test_room_rule_r8_runner.R8RunnerTests.test_single_default_or_exact_two_parallel_no_retry) ... skipped 'CFAST executable not bundled in source clone'

### ai_assistant_test.py

- test_1_ranking (__main__.Acceptance.test_1_ranking) ... skipped 'saved comparison references original-machine result folder'
- test_3_ventilation_proposals_no_run (__main__.Acceptance.test_3_ventilation_proposals_no_run) ... skipped 'saved comparison references original-machine result folder'
- test_5_briefing (__main__.Acceptance.test_5_briefing) ... skipped 'saved comparison references original-machine result folder'
- test_display_labels_and_zero_tooltips (__main__.Acceptance.test_display_labels_and_zero_tooltips) ... skipped 'saved comparison references original-machine result folder'
- test_report_explicit_save_only (__main__.Acceptance.test_report_explicit_save_only) ... skipped 'saved comparison references original-machine result folder'

### building_panel.test.mjs

- SKIP: evidence folder missing

### contracts.test.mjs

- SKIP: evidence folder missing

### display.test.mjs

- SKIP: evidence folder missing

### explore.test.mjs

- SKIP: evidence folder missing

### fixed_calculation_test.py

- test_saved_native_csv_exact_mapping (__main__.FixedCalculationTests.test_saved_native_csv_exact_mapping) ... skipped 'SKIP: evidence folder missing'

### model_library_test.py

- test_originals_preserved (__main__.ModelLibraryTest.test_originals_preserved) ... skipped 'source_path not available on this machine'

### model_operation_test.py

- test_display_does_not_run (__main__.OperationTest.test_display_does_not_run) ... skipped 'SKIP: evidence folder missing'
- test_existing_results_and_isolation (__main__.OperationTest.test_existing_results_and_isolation) ... skipped 'SKIP: evidence folder missing'

### model_review.test.mjs

- SKIP: evidence folder missing

### results.test.mjs

- SKIP: evidence folder missing

### shell.test.mjs

- SKIP: evidence folder missing

## 실행 증거

- 자세한 항목별 결과·제외·UI 사례·오프라인 검증: 릴리스 `TEST-RESULTS.json`.
- 원본 로그·캡처: `E:/FireLapse-audit-20261110/`.
- 검증 서버는 이 작업이 시작한 launcher의 정상 종료 API로 종료했습니다. 기존 서버·보안 프로세스·다른 사용자 작업은 종료하지 않았습니다.
