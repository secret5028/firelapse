# UI contracts — stage 1

Interface source: `specs/Claude계약초안-스토어·레이어·스키마-20261026.md`.
This directory is not connected to the running viewer yet. It contains pure read adapters and JSON Schema draft 2020-12 contracts. It does not import or run either simulation engine.

## Entry points

- `adaptBuilding({scenario, playback, sourceHash})`: saved scenario rooms/openings plus explicit cell-to-room mapping. Does not infer missing geometry or connectivity.
- `adaptResult({playback, sourceResult, scenario, summary, building, resultId, sourceRefs})`: the saved lite playback plus its saved result/input sidecars. Checks time axis, building hash and manifest hash. Reads supply HRR and historical settings from the sidecar; never fills them from current defaults.
- `adaptScreening({score, comparison, selection, buildingId, floorId, mc})`: keeps the saved ranking and ties. Missing result links remain null.
- `validateContract(payload, compiledValidator)`: mandatory explicit validator at the loading boundary; throws on an invalid payload. No permissive fallback.

Input objects are not mutated. Unknown engines are rejected rather than labelled CFAST. A native CFAST playback reader remains to be separately mapped and verified; accepting `engine.kind="cfast"` in the common schema is not evidence that this reader supports it.

## Additive contract details

- `polygons_m` retains every disconnected CAD polygon and hole; the draft's singular `polygon_m`/`holes_m` refer to the first component only. Consumers rendering geometry must use the complete list.
- `cell_conditions` keeps original cell-level flags and scores. Existing room-level “any cell meets condition” flags remain available, with null for unknown values.
- R1, R2 and R10 have multiple cells. By user approval, their aggregate fields are null with `aggregation="none"` (`aggregation_status="not_defined"`), while every cell value remains available. Single-cell rooms retain the cell values with `aggregation="single"`. No mean/max aggregation is authorized; adding one requires separate approval.
- Future room-detail UI must expand the cell list for multi-cell rooms and display **방 평균 없음**. This is a recorded UI requirement, not a stage-1 viewer change. The existing “any cell meets condition → show room” condition policy remains unchanged.
- `legacy_color` is archival. Shared condition flags are not equivalent to every old display colour gate. Changing their visual use belongs to the later layer stage.
- Missing seed, supply HRR, engine hash, fallback list or opening-risk evaluation remains null/explicitly unavailable. A missing list is not interpreted as an evaluated empty list.
- A building snapshot covers the saved scenario's rooms, not the entire CAD building. The three supplied examples cover 3F only.

## Reproduce saved-data checks

With Node and the pinned Ajv 8.20.0 dependency installed, run `npm test` in `app/`. If using an existing bundled runtime, set `PYROCAST_AJV` to its `ajv/dist/2020.js` path instead of installing another dependency.

The test reads S06, S09 and stage4 sequentially, writes gzip JSON snapshots and a hash-backed verification report to `simulation/results/ui_refactor_stage1_20261026/`, and checks the saved screening ranks. It never invokes a solver or starts the server. Schema artifacts are generated with `node app/contracts/build-schemas.mjs` from the repository root.

## Stage 2 — isolated store and host

`web/state/store.js` exports `createStore({validators, seriesCache})` and a default store. Supply compiled stage-1 validators at the data boundary; unvalidated loads are rejected. `get(slice)` returns an immutable snapshot. Only `camera/fit` changes camera state. `result/load` returns an increasing sequence; `result/receive` accepts only the current sequence. No store action performs I/O. `legacyDispatchBridge` exposes only `dispatch`.

`series_cache.js` keeps the active result's immutable room/cell series outside observable result metadata. An accepted load replaces the old series payload. The owner clears it when closing a project; host disposal does not delete application data.

`createSceneHost({container, THREE, store, clock, ...})` owns one canvas, renderer and frame loop. `clock.now()` is in milliseconds; layer `tick(dt_s, clock_s)` receives seconds. It supports `start`, `stop`, `render` (single frame), `listen` (tracked events) and idempotent `dispose`. The same container cannot have two hosts. A disposed host/layer cannot be reused. The renderer may be injected for tests. Real layers will obtain sampled data through `seriesAt(t_s)`; this stage does not add sampling/condition calculations.

`web/layers/empty.js` defines eight independent empty layer types with the required lifecycle. Openings have separate window/door groups. Owned resources registered by `own(resource)` are disposed once; borrowed/shared assets must not be registered as owned. Render order, depth policies, risk offsets and labels live in `render_order.js`. Existing shaders remain untouched. User-facing wording is **상층 연소**.

Run `npm run test:stage2` with Playwright available. Alternatively set `PYROCAST_PLAYWRIGHT` to an existing package path. `PYROCAST_BROWSER` and `PYROCAST_THREE` can override the installed Chrome and saved Three.js r160 asset used by the fixture. All fixture requests are intercepted from local files; no server or external request is needed. The fixture uses real Three.js and WebGL (software rendering), allocates a test mesh/material/texture, and repeats mount/dispose 50 times. Results are in `simulation/results/ui_refactor_stage2_20261026/verification.json` and `fixture.png`.

The new host has not replaced the live 3D viewer. Real rendering layers, panels, browser performance at full building scale and native-result playback remain later work. Server routing and cache-key changes are not included.
