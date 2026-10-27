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
- Stage-3 user correction: `legacy_color`/`display_v8` compatibility gates drive risk rendering; shared condition flags remain detailed-panel data. They are not interchangeable. See `specs/Claude검토-3단계기준-기존화면코드-20261026.md`.
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

## Stage 3 — first layer (building)

Use `readLegacyBuildingSource({building: B, groups, sourceHash})` after the CAD loader has created its static meshes. The verified source hash must match `building/1.source_hash`. `createBuildingLayers(THREE, {geometryFor})` replaces only the empty building layer; the rest remain empty. The provider returns the same source identity while CAD geometry is unchanged. It is a read-only asset capability, not a reference to another display layer.

The building layer shares the imported geometry, copies Mesh/Line objects and clones materials. It reproduces the existing install() colour overrides without modifying the source materials. Disposal frees only its cloned materials and objects; source geometry stays owned by the CAD loader. Shut down the legacy host before a future live switchover, and dispose the layer before the CAD loader frees borrowed geometry. No new room-wall extrusion, cell-boundary building walls or custom shaders are created. Material colour/opacity/depth settings are preserved except the documented colour overrides.

Building/resultMeta identities are compared; a result-only change, seek, selection, layer toggle or floor change does not regenerate geometry. Floor changes only change visibility. `renderPolicy` rejects Groups and applies to actual Mesh/Line objects/materials.

The corrected legacy order is smoke 10, plume 15, flame 20, gas flame 22, smoke boundary 23, cell line 25, band 26, interface plane/line 27/28, exterior window 30, risk 35, selection 40, interior door 46, core 70/72/73. Existing transparent material opacity is retained (risk 1, selection .95, door .9), superseding the earlier uniform-opacity proposal. Risk ribbon height follows the smoke interface plus .14 m/type with the legacy clamps; it is not floor-fixed. The `displayV8Gates` helper freezes old visual gates; actual risk rendering is not yet implemented.

`npm run test:building` uses the frozen legacy CAD HTML geometry construction block and the actual lite_viewer.js colour override block as its isolated reference. It renders building-only reference and layer with the same camera, lighting, renderer, viewport and clock (180000 ms), in 3F isometric/top/all-building views. It is not a full S06/S09 fire-scene comparison; that follows when the other layers are implemented. `PYROCAST_MODEL` can override the model path found in the stage-0 manifest. Evidence is under `simulation/results/ui_refactor_stage3_building_20261026/`.

## Stage 3 — openings layer

`readLegacyOpeningsSource({building: B, groups, sourceHash})` exposes the unchanged CAD opening descriptions and floor groups. Inject it with `new OpeningsLayer(THREE, {geometryFor, camera})` in place of the empty openings layer when assembling the host. The provider returns a stable source identity and must match the building hash. The camera is the host camera. The running legacy viewer has not been switched over.

The exterior face filter is extracted unchanged from `lite_viewer.js`: standard-size exterior windows only, excluding terrace/railing outlines. Window loops retain opacity .65, depth testing and render order 30. Interior door loops retain opacity .9, no depth testing and render order 46. Both policies apply to actual LineLoop objects and materials. `setPartVisible('window'|'door', boolean)` preserves independent display controls without adding panel wiring at this stage.

Every `tick` checks every exterior window against the current camera position, with the original strict positive normal dot product. No OrbitControls event is required. Floor visibility and translation follow the source CAD groups. Camera movement, floor changes, time/selection and result metadata changes do not recreate geometry. This layer owns and disposes its line geometries/materials; it never disposes CAD assets or changes the source descriptions.

Run `npm run test:openings` with the same browser/runtime variables as the building test, then `python app/tests/compare_openings.py` from the repository root. The fixed-clock comparison uses actual 3F building + openings in front/back/top views against the original builders; smoke, core and fire layers are intentionally absent from both images. It checks all 611 CAD opening candidates, vertex/material parity, per-frame facing without an event, stable geometry over 500 frames, independent toggles and disposal. Evidence is in `simulation/results/ui_refactor_stage3_openings_20261027/`.

## Stage 3 — core layer

`readLegacyCoreSource({building: B, groups, sourceHash, shapeFor: shp})` borrows the CAD loader's transport footprints, floor groups and shape converter. Use `new CoreLayer(THREE, {geometryFor})` instead of the empty core layer when assembling the host. Only `stair`/`elev` entries with `connected`, `to_floor` or a nonempty `meshes` array are rendered; missing footprints are skipped. It does not invent connections or shafts across missing floors.

Core shells retain .10/r70, stair treads .86/r72, edges .95/r73; all are transparent with depthTest/depthWrite false. Shells remain double-sided while treads retain the original front-sided material. Floor translation/visibility follows the CAD groups. The existing store's `layers.core` checkbox state AND `floor.floor_id === null` controls the whole overlay. A selected floor always hides it. No panel or live-viewer switchover is included.

Run `npm run test:core` and then `python app/tests/compare_core.py` from the repository root, using the same runtime variables as the other layer tests. The fixture compares all actual transport geometry/materials to the unchanged legacy builder and captures all-building front/back/checkbox-off with fixed clock. Synthetic cases exercise all connectivity alternatives and rejected entries. Evidence: `simulation/results/ui_refactor_stage3_core_20261027/`. Static geometry remains unchanged over 500 updates and result-meta replacement; all 1,100 owned resources are disposed. This is a building+core comparison, not a complete smoke/fire scene.

## Stage 3 — smoke / flame / plume

`readLegacyRealSource({building: B, groups, sourceHash, data, resultId})` keeps the **original playback object** intact and separate from result/1. `sourceFor(building, resultMeta)` returns that stable capability. Import `createRealViewLayers(THREE, {sourceFor, camera})` from `web/layers/real_view_layers.js` and supply those three layers to the host with its camera. Replace the three empty counterparts; do not mount duplicate IDs. `legacy_real_bridge.js` imports the unchanged `legacy_real_view.js`; neither file is copied or edited.

The three independent layer IDs share one renderer session and its resources. Smoke's tick drives the session once, avoiding three copies of the expensive volume renderers. The host supplies `frame.layers`, `frame.realView` and reduced-motion state. `realView/set` updates enabled, smokeOpacity (0–1) and temperatureSmoke. Time comes from playback/seek, sample uses the saved output grid, floor null maps to all. Existing compatibility flags remain customRiskBoundaries:true, legacySmokeTexture:true and flameDisplay:'growth'. `animate(clock_s*1000)` receives zero for reduced motion. The legacy bridge hardcodes flame visibility on, so the wrapper hides only identified flame draw objects and lights after update when layers.flame is off; the next update restores native state.

The host provisions `#cfMeaning` before mounting these layers and removes it and the legacy legend during disposal. It rejects a pre-existing legend owner, requiring the old viewer to shut down before a future switch. The original renderer still creates its own legend adjacent to this anchor. `providePlumeLegend()` also supports fixture assembly. Shader source and uniforms are not patched. The session records and disposes geometries, materials and uniform textures once, since legacy detach() alone only removes DOM/scene nodes.

Run `npm run test:real-view`, then `python app/tests/compare_real_view.py` from the repository root. S09, 3F, R2 origin uses saved simulation time 1800 s and an independently fixed animation clock 180000 ms. All four smoke/plume ON/OFF combinations compare the direct legacy call against the wrappers. Checks cover uniform parity, reduced motion, appearance/flame toggles, unchanged geometry, raw-input identity, legend cleanup and an isolated remount with GPU counts returning to zero. Evidence is under `simulation/results/ui_refactor_stage3_real_20261027/`. This remains an isolated building+real-view fixture; live routing and the unfinished risk/selection layers are unchanged.
