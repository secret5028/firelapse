# Calculation control — 2026-11-04

- Final Settings/Exploration card: 간략 엔진 · MC · selected origin, 간략 계산하기, concise state.
- Uses existing POST /cfbt/lite/mc. Duplicate pending requests blocked. No new CFAST execution route.
- Existing saved output is labelled 저장 결과 있음, not proof that current settings were calculated.
- Requests made in this session retain input signature; changed settings require recalculation. Unstored fuel edits disable execution.
- Result scope includes 간략 or CFAST engine identity.
- calculation_status.test.mjs, explore.unit.mjs, result_scope.test.mjs: PASS.
- Factory operating UI: 3F selected, automatic origin R1, final button enabled, state 계산 전; screenshot attached.
- No actual simulation launched; engine/server unchanged. Execution still follows existing serial MC path.
