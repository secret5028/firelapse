# Selection and saved calculation scope — 2026-11-04

- Saved scope is derived from result cell membership, independently of the viewed floor or selected CAD room.
- All CAD room polygons can be selected. Uncalculated rooms have no synthetic result cells or time series.
- Moving to another floor clears an out-of-floor selection; it does not change the saved scenario or start a simulation.
- Current indices, peak indices/times and physical quantities show — when absent. Genuine computed zero remains 0. Accessibility labels also identify missing indices as unevaluated, not a zero meter.

## Verification
- result_scope.test.mjs: PASS (CAD-only picking, immutable result scope, metadata-store path, missing/zero distinction, resource disposal).
- history_peaks.test.mjs: PASS.
- results.unit.mjs: PASS, including ten stored samples.
- Hotel operating page: 2F R6 selected → 미평가, all current/peak/time values and eight calculated quantities —; saved scope remains 5F, origin 5F R16.
- Hotel operating page: return to 5F, click R16, seek 34:40 → FO 117, FGI 0, BD 0; Tu 702.3 ℃.
- Floor switch removes the previous selected room and its timeline graph. Selected result tab remains active.
- No engine changes, no saved playback edits, no simulation.
