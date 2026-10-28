# PyroCast UI — production host and contracts

Interface source: `specs/Claude계약초안-스토어·레이어·스키마-20261026.md`.
The running viewer uses this directory's scene host by default. `?ui=legacy` selects the preserved viewer. The pure read adapters and JSON Schema draft 2020-12 contracts do not import or run either simulation engine. Historical stage notes below describe earlier checkpoints.

## Production entry (2026-10-28)

Run `python tools/build_ui_bundle.py` from the project root after editing `app/web` sources. Its default output is the actual served `simulation/viewer/overlay.js`; do not hand-edit that generated file. `entry.js` selects the modern host for lite playback and preserves the old path for `?ui=legacy` and non-lite results. Server routes and cache keys are unchanged.

`controller.dispose()` restores the borrowed CAD renderer and building materials, disposes owned layer and menu resources, disconnects observers/listeners/timers, clears the series cache and removes its panels/styles. It also runs on `pagehide`. The CAD scene/canvas remains owned by the original loader. Auxiliary legacy menu modules now return optional disposers; their legacy UI and network behaviour are unchanged.

Run `node app/tests/production_switch.test.mjs` with Playwright configured as below and the local server on 8780. This exercises both paths against the served bundle, blocks writes, performs real 60-second playback at 1x/20x, captures legacy, and measures control fetches and modern cleanup. Evidence: `simulation/results/ui_refactor_production_20261028/`.

**Stage 4 pending:** the 38 invisible picking planes still issue **76 modern draw calls**. This is explicitly deferred; this switch does not optimize or remove them.

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

## Stage 4 item 2 — display controls and compact HUD (2026-10-28)

`panels/display.js` moves existing display inputs into the Display tab and adds independent flame/risk/operations/type switches, risk thresholds and three temperature-pattern choices. The controller alone bridges operations visibility and existing camera buttons. Operations default OFF; top/oblique live in the header. The HUD reads the selected cell's existing indices and three series values without a room average. `#cfMeaning` remains the single plume-legend anchor.

Temperature pattern defaults to current (unchanged rendering). The frozen shader lacks a highlight-gain uniform: weak remaps only display `uLayerTemp`, shifting hot red toward subdued yellow, and off clears `uTemperatureSmoke`. This limitation is in the tooltip; calculation/HUD values do not change. Only these two existing uniforms are written. Shader sources are unchanged.

Run `node app/tests/display.test.mjs` then `python app/tests/compare_display.py` from the root. Supply the previous cdd6e6f bundle as `simulation/results/ui_refactor_stage4_item2_20261028/previous-overlay.js`. The comparison-side name `stage3` is retained by the harness; this is the immediately previous bundle already proven equal to stage 3. Four fixed-clock/camera WebGL comparisons (risk off, operations off on both sides) are pixel-identical. Fourteen toggles round-trip exactly, control fetches are zero, threshold validation/opacity/pattern/HUD/camera checks pass, and disposal leaves no shell/display DOM, subscriptions or owned layer resources. Evidence includes separate desktop/mobile full-page captures. Item 3 remains pending; no push.

## Stage 4 item 1 — shell and picking mask (2026-10-28)

`panels/shell.js` supplies a header with the existing floor buttons, a 340 px sidebar with four accessible tabs, and a bottom timeline. Building/explore/display panes are empty; the complete existing panel lives inside the result pane without cloning its controls or replacing its handlers. The new timeline dispatches playback store actions and mirrors the old controls. Saved supply-start and first FO-condition samples provide timeline marks. At <=860 px the sidebar becomes a collapsible bottom panel. New HUD/legend/tab content is not implemented in this item.

Resize updates renderer/label dimensions and camera aspect only; it no longer calls fitFloor. Explicit fit controls still work. `scene/picking.js` reserves object layer 31 for selection hit planes. The camera remains on layer 0 and the host Raycaster uses layer 31; geometry/material/visibility remain available for picking. 38 double-sided transparent planes previously cost 76 draw calls.

Run `node app/tests/shell.test.mjs` from the root, with Playwright available and the local server running. The reference is the frozen stage-3 bundle from commit fd9325a (saved as stage3-overlay.js in the evidence directory). The test checks tabs, bidirectional timeline/legacy-control state, no control fetches, mobile folding, resize camera preservation, actual browser mouse/touch picking, and disposal. It captures four renderer-only comparisons at 1000x600, identical pose and clock180000, with the entire risk layer disabled on both sides. This isolates the unchanged 3D rendering from the intentionally new viewport layout; full-page desktop/mobile captures are separate. All four comparisons have zero changed pixels. S09 1420 s current risk display: 902 -> 826 calls; stage-3 S09 1800 s: 902 -> 826 with the mask. Evidence: simulation/results/ui_refactor_stage4_item1_20261028. No engine/server/shader/render-order change, no push; item 2 remains pending.

## Stage 4 item 0 — saved risk indices (2026-10-28)

Modern risk display now reads `result.index_by_cell[cell_id][phenomenon][time_index]`, copied as saved `scores.degree * 100`; null remains unknown. No factor recomputation or room scalar aggregate is introduced. Each original room independently ORs its member cells for the four ribbons. Default store `risk.threshold` is `{ribbon:100,caution:70}`; `risk/threshold` changes either value without rebuilding geometry. Grey caution is the lower index band; existing boundary flags retain dashed outlines. Ribbon colors, spacing and render policy are unchanged.

Only the existing legend wording changes in the panel. Threshold inputs and the new panel layout remain pending. `?ui=legacy` keeps the old `display_v8` behavior. Raw saved results, shaders, render_order.js, engine and server are untouched; only the UI adapter contract gains index arrays.

From the repository root run `node app/tests/risk_index.test.mjs`. Run the saved-data contract suite with `PYROCAST_CONTRACTS_OUT` set to a new evidence directory to preserve earlier snapshots. `risk_index_scene.test.mjs before|after` captures the served S09 1420 s scene at clock 180000 ms. Evidence: `simulation/results/ui_refactor_stage4_item0_20261028/`. Earlier stage-3 pixel-equality risk fixtures below are historical, no longer acceptance tests for the intentionally changed gates. The 76 picking draw calls remain deferred to item 1.

## Stage 3 — risk layer (historical compatibility gate)

`new RiskLayer(THREE)` consumes only building/1, result metadata and adapted cell series via `frame.series.cells`. Configure the host's `seriesAt` capability to return the active series cache (arrays on the saved time grid). No playback source, CAD-loader capability, fetch or engine import is accepted by this layer. The building read adapter now also retains optional `cell.legacy_display` fields z_m, height_m and single_zone; these are required for rendering risk geometry without looking back at playback. The legacy omitted single_zone flag is false exactly as in the old display. Older snapshots remain schema-valid, but need re-adaptation before mounting this layer.

Gates are exactly FO red colour, FGI stage 2 + oxygen >= LOC, backdraft stage 2 + oxygen < LOC, and rollover_band. They are ORed independently over each original room's cells. Shared conditions.met is never read. Colour-only fallbacks for gas/rollover were removed from the compatibility helper under the latest user instruction; the old direct builder remains the capture reference. Risk indices/threshold transitions are not part of this stage.

The layer preserves four original-perimeter ribbons at smoke-interface-relative heights, cell/exterior-boundary intersections, floor tint and neutral smoke interface lines/selected planes. It creates no internal cell borders, selection ribbons, pick planes or UI labels. `summary()` supplies the existing status wording for a future panel. A selected non-cell smoke plane retains the old .07 policy; multi-cell rooms do not gain an invented room plane. All owned geometry/materials are released on disposal, and display/time/floor/selection changes do not rebuild them.

Run `npm run test:risk` (Playwright and Ajv variables as above), then `python app/tests/compare_risk.py`. The actual S09 3F R2 case is compared at 1800 s and the first multi-type overlap (1420 s, R2 FO + backdraft), smoke ON, clock 180000 ms. Reference risk code is extracted unchanged from lite_viewer.js and gets raw data only inside the test; the new layer gets only adapter output. Both scenes exclude the not-yet-migrated selection ribbon. Synthetic display cases cover all four types, room OR/minimum interface height, grey dashes and selected neutral smoke planes. A throwing proxy rejects access to shared condition criteria. Evidence: `simulation/results/ui_refactor_stage3_risk_20261027/`. The live viewer remains unchanged.

## Stage 3: selection layer (isolated, not switched live)

`SelectionLayer` reads adapted building geometry and selection state. It exposes `getPickPlanes()` and creates no DOM or event listeners. Each cell has an invisible floor at z+.07 with `userData.liteRoom`; selected cells use the original room outline at z+.08, #42e8ff, opacity .95, depthTest false, renderOrder 40. A room-only selection displays exactly one ribbon. An unpartitioned room preserves its saved cell polygon vertex order; a partitioned room uses the original room polygons. Time, selection and result metadata changes reuse geometry.

The scene host owns pointerdown/move/up/cancel and raycasts only visible floor planes. Mouse movement up to 5 px and touch movement up to 10 px are accepted; exceeding the limit, multipointer gestures or pointercancel cancels selection. A hit dispatches `selection/set` with original room ID, cell ID and click/touch source. A miss preserves the existing selection. Host disposal removes listeners. `.cfbtSceneCaption` remains a future panel responsibility.

Run `npm run test:selection`, then `python app/tests/compare_selection.py`. S09, 3F, R2 fire, 1800 s, clock 180000 ms: R2 room selection / R3 cell selection / none. Baseline uses unchanged legacy geometry and update code; no-selection is represented by a null selected key. R3 is one cell in this saved case; all R2 cells separately verify original-room outlines. Tests include native mouse/touch picking, threshold edges, hidden floors, 500 updates and resource cleanup. Evidence: `simulation/results/ui_refactor_stage3_selection_20261027/`. Full scene switchover is the next separately authorized stage.

## Stage 3 switchover draft — STOPPED, not deployed

`entry.js` and `controller.js` prepare a default modern-host path with `?ui=legacy` rollback. `panels/` preserves the current HTML/text. The host can explicitly adopt the existing CAD canvas/renderer and panel legend, leaving the CAD loop as its sole frame driver. No server route, cache key, engine or shader changes are required. A small closed-graph build tool bundles named frontend modules while leaving frozen renderer modules external.

The whole-page comparison stopped at S06 890 s per user instruction: 3,923 changed pixels, with all cell risk gates, panel HTML and camera matching. Differences appear on CAD surfaces; exact render cause is not yet established. S09 also has nonzero surface differences. Whole-building/core capture and the full interaction regression remain pending. The live `simulation/viewer/overlay.js` is UNCHANGED. Do not promote this draft until the stop is resolved. The tested candidate was built with `python tools/build_ui_bundle.py --output simulation/results/ui_refactor_stage3_switchover_20261027/overlay.js`; `app/tests/switchover.test.mjs` intercepts only that response and prohibits POST requests.

## Building scope correction — still stopped (2026-10-27)
The building adapter now follows the exact legacy install colour branches across the whole floor hierarchy, including glass and stair treads. Nested transforms/visibility are retained and circular CAD userData is shallow-copied. The read-only install probe matches all 1,222 source objects to 1,222 clones (3F: 156 registered, 153 visible). S09 at 1800 s still differs by 164 pixels, bbox (559,233)-(809,454). Comparison stopped at that first difference as instructed; the remaining three scenes were not run. Picking planes remain unchanged at 76 modern draw calls. Live overlay is not promoted. Evidence: simulation/results/ui_refactor_stage3_building_scope_20261027/.

## Building shared materials — visual gate passed (2026-10-28)

Building clones now borrow original materials as well as geometry. The first override saves each unique material's color, opacity and transparent flag; rebuild/dispose restores them without disposing borrowed resources. Run `node app/tests/building_materials.test.mjs` for the 50-cycle shared-resource restoration check. The actual scene contains 1,222 source/clone pairs with identical material references and equal sets of 701 material IDs.

S09 1800 s / 1420 s, S06 890 s and whole-building/core ON all compare at zero changed pixels. The last comparison was completed from the already-saved PNG pair after the browser session ended; its per-scene browser metadata was not recovered. Evidence: `simulation/results/ui_refactor_stage3_shared_material_20261027/summary.json`, detailed first-three-scene `verification.json`, and four image pairs. Picking planes and frozen engine/server/shader files remain unchanged. This resolves the previous visual gate only; the live overlay is still not promoted and broader interaction testing is outside this change.
