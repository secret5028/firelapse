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

## Stage 4 item 3 — result panel (2026-10-28)

`panels/results.js` renders saved cases, four saved-index bars with current threshold markers, saved bottlenecks, per-cell selection (no room average), expandable quantities and one limits drawer. Existing result/selection actions remain in the controller; legacy panel DOM is hidden and necessary controls move into the new cards. The panel does not fetch or run simulations.

The catalogue supplies random-only condition sample counts and maximum score. The explicit saved-sample read button sequentially fetches completed playback files through the unchanged API to derive maximum original-room counts, deduplicating cells and preserving unknowns as lower bounds. Counts mean rooms ever meeting index >=100 over each saved sample, not simultaneous room counts. Max-room counts include mandatory samples; the table identifies this separately from random-only rates/max indices. Refresh/dispose aborts pending reads; the active scene remains unchanged.

Tests: `node app/tests/results.unit.mjs`, `node app/tests/results.test.mjs`, `python app/tests/compare_results.py`. Previous bundle 5236545 belongs at `simulation/results/ui_refactor_stage4_item3_20261028/previous-overlay.js`. Four equal-pose/clock WebGL comparisons (risk and operations OFF on both sides) are pixel-identical. Tests check score values, markers, multi/single-cell selection, zero control fetches, ten sequential saved reads, unchanged active scene and disposal. No engine/server/shader changes, no push; item 4 remains pending.

## Stage 4 item 2 — display controls and compact HUD (2026-10-28)

`panels/display.js` moves existing display inputs into the Display tab and adds independent flame/risk/operations/type switches, risk thresholds and two temperature-pattern choices. The controller alone bridges operations visibility and existing camera buttons. Operations default OFF; top/oblique live in the header. The HUD reads the selected cell's existing indices and three series values without a room average. `#cfMeaning` remains the single plume-legend anchor.

Temperature pattern is current/off only (default current). It uses the frozen renderer's existing temperatureSmoke switch. The wrapper never writes or remaps temperature inputs or uniforms. Weak is rejected by the store. Calculation/HUD temperatures and shader sources are unchanged.

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


## Stage 4 item 4 — exploration tab (2026-10-28)

`panels/explore.js` renders existing server rankings without recomputing scores or sorting them again. The default N is 8. Stage 2 preserves the server's ranking and displays rank, origin, stage-1 rank, burning-room count, smoke-risk-room count and first FO. Click, Enter or Space selects a candidate in `exploration` state, independently of scene selection/result/camera. The MC card shares this state, accepts a sample count and estimates time from saved MC wall time/completed samples. Null/missing values remain unknown.

The controller uses the unchanged GET/POST `/cfbt/lite/screening` route. A run sends `{top_n,mc_room,run:true}`, polls while running, preserves the old ranking on an error, and never automatically replaces playback. The folded rules section imports the unchanged `frozen_rule_controls.js` and its existing `/cfbt/r8/*` routes. Its context explicitly identifies the selected origin/current result horizon and server-default door/window settings; it is a separate native review calculation, not MC. No engine or server code is changed.

**User decision (2026-10-28):** this item implements the MC card and saved-results view only. The disabled “MC 실행” button has the exact tooltip “서버 실행 경로는 5단계”. No MC endpoint is added now. Results opens the existing saved MC summary only for the saved origin; unavailable origins stay disabled. The saved origin is read from a catalog-listed completed playback (initial playback if it belongs to MC, otherwise the first completed sample).

The two clarified UI corrections are included: HUD uses exactly the current result-selector option label (floor/cell + approved display name, not raw CAD labels); whole-floor/building fit buttons are removed from the visible case card; real view is a Display-tab switch; the menu review content is folded at the very bottom of Results. Hidden compatibility controls remain outside the visible panels so existing camera handlers and legacy rollback are preserved.

Verification: `node app/tests/explore.unit.mjs`; `node app/tests/explore.test.mjs`; `python app/tests/compare_explore.py`. Supply the previous 8ab8504 overlay bundle in the evidence folder. Four fixed-clock, equal-camera 1000x600 renderer comparisons have zero changed pixels, with the whole risk layer disabled on both sides. This immediately previous reference was already proven pixel-identical to stage 3. UI tests intercept all POST requests, so no simulations or selection config writes are performed. Click/keyboard selection and sample changes generate zero fetches and preserve result/scene selection/time/camera (camera floats compared to 10 decimal places; pixel comparison remains exact). Rules/screening payloads, N validation, saved MC reads and disposal are checked. Evidence: `simulation/results/ui_refactor_stage4_item4_20261028`. No push. Stop before item 5.


## Stage 5 backlog — server integration (completed below)

- Stage 4 deferred `POST /cfbt/lite/mc` and cache policy. Both were explicitly authorized and implemented in stage 5A; see the current contract below.


## Stage 4 item 5 — building panel and attention ranking (2026-10-28)

`panels/building.js` shows existing input classifications (confirmed/inferred/ordinary/windows), door IDs and connections, classification corrections, and room-use/fuel values. CAD source labels and classification/value evidence are confined to expandable details in the Building tab. Active Explore labels use approved usage labels; unknown usage is explicitly unknown. This API currently covers the 3F simulation input, not all CAD floors; the panel identifies that scope. The existing read-only legacy menu archive and `?ui=legacy` are preserved.

Controller GET/POST `/cfbt/lite/doors` exactly matches the existing lite_doors.js protocol (`{id,door_class}`). The existing server writes `simulation/config/lite-door-overrides.json`. The UI updates only after success; errors retain old classes. A successful change refreshes the cheap screening input/ranking data, never runs a simulation or changes saved playback. No new 3D classification markers or picking handlers are added. Server, classifier, solver and legacy lite_doors.js remain untouched.

**Reported cause of the all-zero smoke column:** screening.py summarize uses the old AND of gas temperature, flammable-fuel concentration and layer thickness. Its `smoke_risk_room_count` is not the new shared phenomenon index. The old caution count is also a different formula, so neither is reused. Following the user definition, the new column is explicitly called “주의 ≥70”: count each original room once if any FO/FGI/backdraft/rollover degree×100 reaches70 in any cell/time. It is a fixed ranking threshold, independent of display thresholds. Select the worse of both extreme states and sort origins by burning rooms descending, attention rooms descending, first FO ascending (null last). Equal metric tuples share rank; ID only stabilizes display order.

The frozen server API does not provide these time series. `tools/export_ui_attention.py` reads the existing sixteen saved result.json files, deduplicates original rooms, records source SHA256, and writes the compact UI-only `app/web/data/saved_attention.js` artifact. No integration/recalculation, no old result rewrite. The frontend matches saved run identity (origin/state/folder/time/burning/FO/horizon) before using the counts. Missing, stale or incomplete records are unranked and shown as unknown, never zero. **Newly executed screening results require re-export/rebuild until stage5 provides the aggregate through the server.** Run `python tools/export_ui_attention.py` then `python tools/build_ui_bundle.py` after an authorized new screening batch. Stage5 backlog also includes publishing this aggregate for new results; the server is not changed in this step.

Current saved ranking: R3 rank1 (2 burning/2 attention); R2 rank2 (1/1); R0/R23/R4/R8/R9 tied rank3 (1/1, no FO); R1 rank8 (1/0). R1 was formerly rank3 under the old formula. Zero old smoke counts were genuine old-metric results, not missing data. The approved room table retains R2 1800MJ/m² and excluded/tiny rooms with their documented reasons; unknown usage is not guessed.

Verification: `node app/tests/building_panel.unit.mjs`, `node app/tests/building_panel.test.mjs`, `python app/tests/compare_building_panel.py`. The browser test intercepts all POST writes; no production overrides or simulations are changed. It verifies successful and failed corrections, source-label separation, fuel rows, new ranking, camera/result preservation and disposal, plus four fixed-clock/camera 3D comparisons with risk disabled. Reference is previous6145cc8, already proven equal to stage3. Evidence: simulation/results/ui_refactor_stage4_item5_20261028. Stop before item6, no push.


## Stage 4 item 6 — explanatory-text audit (2026-10-28)

Modern panels use `panels/explanations.js` for accessible ⓘ `data-tip` presentation. Existing title-only info icons now carry data-tip. Room/door evidence retains raw CAD labels in Building while moving explanatory bases into info tips. MC denominator explanation is also a tip. The modern presentation boundary migrates imported legacy-review/frozen-rule prose without editing the legacy modules, controls, requests or shaders. A scoped MutationObserver handles refreshed report paragraphs and mixed text/control rows; disposal removes the observer, listeners and tooltip. Keyboard focus and touch/click expose tips, Escape closes them. Errors/progress and CAD diagnostic records remain actionable body content; their reasons and source lines are listed in the audit.

Evidence: `simulation/results/ui_refactor_stage4_item6_20261028/text-audit.md` (61 moved wording entries, 451 retained CAD diagnostics plus the operation hint; runtime duplicates deduplicated). Dynamic error templates are separately listed. `screenshots.html` contains Building/Explore/Results/Display at desktop1440×1080 and mobile390×844 (eight captures). One additional legacy capture verifies rollback. This step does not redesign camera hints or CAD diagnostics.

Verification: `node app/tests/explanations.test.mjs`, `python app/tests/compare_explanations.py`, `python app/tests/report_explanations.py`. The browser harness uses the d1d06a2 overlay as baseline (`previous-overlay.js` in the evidence directory); all writes are intercepted. Fixed clock180000ms, camera and1000×600 WebGL viewport: S09/1800, S09/1420, S06/890, whole-building/core ON each zero changed pixels **including risk ON**. Operations initial OFF, five risk toggles roundtrip, legacy one canvas/legend, dynamic explanation refresh, tooltip keyboard interaction, disposal resources/subscriptions/tooltipDOM0, no browser errors and POST0. Shader/render_order/server hashes match d1d06a2; stage0 frozen engine/config/result check remains unchanged (237-file inventory). No simulation, server write, push or stage5 work. Stop after this item.


## Stage 5A — minimal server integration (2026-10-28)

`tools/result_catalog.py` scans result folders for playback.json and writes `simulation/results/playback-catalog.json`. It filters building SHA, validates playback schema, excludes incomplete lite cases and test/publish snapshots, preserves existing lite IDs (S06/S09), and gives new cases stable path-derived IDs. The 18 native literals formerly in the server moved to `simulation/config/native-case-aliases.json` for URL compatibility only; new cases require no alias entry. A 15-second metadata cache and file stamps avoid rereading unchanged large payloads. Current building: 31 native / 11 lite cases; 45 files indexed. Initial scan measured19.66s, warm full metadata scan2.93s. This is not simulation time.

`POST /cfbt/lite/mc` accepts `{room,samples,duration_s,seed}`: eligible source room, total samples2–1000 including the two existing mandatory cases, duration1800/3600, seed uint32 (default20261025). It snapshots the approved fuel/source/door inputs and invokes `tools/run_lite_mc.py` without a shell. Existing MC sampling, serial execution and adopted physics are reused. One worker; **1200s integration budget per sample**, shared by BDF and at most one Radau fallback on numerical failure, not a total batch timeout. Pre/postprocessing remain outside that inherited integration budget. Invalid400, busy409, accepted202; GET same path reports status. A persisted process/job record detects interruptions without automatic reruns. No service cancel endpoint is added in this scope.

The Explore MC button is now connected. It sends the selected source, sample count, current result horizon and recorded seed; polls while busy; refreshes saved-case/summary lists after completion. Completion/failure never replaces the current playback or camera. A finished batch reports failed/incomplete samples explicitly; only completed playback files can be selected. Results remains available per source room. Generic batch output is under results/lite_mc_jobs; it never rewrites lite-viewer.json. Current input provider remains the existing approved3F source, not a new universal CAD-to-MC adapter.

`run_lite_l1.save()` creates `index-summary.json` when saving a lite result with shared conditions. `export_ui_attention.result_index()` and `comparison_attention()` are shared by CLI save and screening GET. Existing results are indexed lazily; new results need no frontend export/rebuild. The >=70 original-room union definition and unknown/incomplete treatment are unchanged. The existing static UI artifact remains an old-server compatibility fallback only.

User cache decision: execution_key excludes the server file SHA, while retaining calculation-package/data/thermal code, engine bytes, building SHA and options. The new cache schema causes a **one-time key migration**; old saved results are retained and viewable, but old keyed executions are not silently relabeled. Later server/UI-only changes do not invalidate calculation keys.

Tests: `python app/tests/server_stage5.test.py` (7 contracts, solver/process mocks), `python app/tests/server_stage5_http.py` (real HTTP with fake worker), `node app/tests/server_stage5_ui.test.mjs` (browser POST intercepted). Evidence: simulation/results/ui_refactor_stage5A_20261028. HTTP202/400/409, shared admission with native jobs, aggregate16 records, publication/partial failure, invalid counts, double click, completion/error playback preservation and dispose0 verified. S09/1420 fixed clock180000/equal1000x600 camera/riskON: zero changed pixels versus fbcab5f. Legacy path one canvas/legend; no page errors. 55 engine-package/shader/render-order files byte-identical to previous commit. No actual MC simulation was run for this change; numeric correctness/elapsed simulation time were not remeasured. Production8780 restarted with the same project/result options; read-only live API verified available/idle and preserved S06/S09. No push.


## Stage 5A follow-up 1 — verified aliases and historical reuse

`tools/migrate_execution_cache.py --legacy-server <exact-previous-server.py>` creates results/cache-key-aliases.json once. Only a reproducible old24-character execution_key with current calculation dependencies/exact request and complete outputs can be promoted. New key lookup precedes alias lookup; SHA-sealed outputs/building/type are checked. Newly completed native/r8 requests retain execution-request.json/cache-completed.json. Existing native16-character cache is excluded; actual migration contains zero verified aliases. No invented keys for named CLI results.

GET /cfbt/reuse/{native|lite}/{id} reports verified_cache (equivalent true) or historical_result (equivalent false), with solver_runs0. Result card labels both cases and a read-only “다시 실행” button; it does not submit calculations or reset an already loaded scene. User approved historical reuse explicitly. Current42 saved cases lack complete current execution provenance and are all historical. Modern11 cases, including S06/S09, were clicked through the actual UI with no recalculation. Full list/evidence: results/ui_refactor_stage5A_cache_20261028. `python app/tests/cache_aliases.test.py` verifies5 contracts using fixtures. Real alias hits0; API max404.82ms. Do not report a fixture hit as a production cache hit.

## Stage 5A supplement 2 — actual UI MC verification (2026-10-28)

One actual Explore-button run: R3, samples2 (mandatory2/random0),3600s,seed20261025,serial worker1,1200s integration budget per sample. Job mc-1793171631584057100-c3f54953 completed2/2 with no retries: batch859.123s, click-to-observed completion866.305s. S00 integration819.656s/total827.851s,11 burning/5 attention rooms; S01 integration13.046s/total20.471s,1/1. Independent status observations281/281 HTTP200 (median6.20ms,p95 26.89ms,max819.94ms). Engine unchanged during batch.

Catalog11→13; both new playback files and root/attempt index-summary.json exist. Results tab read2/2 and manual selection of each new case loaded R3/60min. Current S09 stayed unchanged automatically; actual before/after 3D screenshots differed by0 pixels. Manual verification then restored S09. Mandatory-only run has no random-sample rate (0/0, not probability). Evidence results/ui_refactor_stage5A_mc_20261028; read-only reporter app/tests/report_actual_mc.py; Korean report specs/웹앱리팩토링-5단계A-실제MC-20261028.md. No further simulation or push.

## Execution evidence (2026-10-28)

Completed server MC samples now write execution-evidence.json next to the final playback: canonical input hashes, run-time lite engine ledger/aggregate SHA, parameters, saved compiled-rule settings/hash, applied door classifications and manual corrections, sealed output/log hashes. New starts also record shared-rule source SHA. Reuse verifies evidence against files and current inputs/engine/rules with input generation and rule compilation only, never integration. Any mismatch or missing proof returns historical_result; matching samples show 동등 · 검증된 결과 재사용.

The two R3 samples in mc-1793171631584057100-c3f54953 were backfilled from their actual job logs. Old logs did not hash shared cfbt sources: the extra shared-source guard is explicitly evidence-verification-time, while compiled rules are compared to the run-time manifest. No fabricated historical SHA. Applied manual overrides are derived from saved user-classified doors (empty here). Current default/input/door changes invalidate equality. This is source/input equivalence for the saved sample, not physical accuracy or cross-platform bit identity.

Production check:2 equivalent +42 historical, solver runs0, both playback hashes unchanged; UI S00/S01 equivalent and S09 historical verified. Tests execution_evidence.test.py5, cache_aliases.test.py5, server_stage5.test.py7 pass (solver mocked). Evidence results/ui_refactor_stage5A_evidence_20261028 and specs/웹앱리팩토링-실행증거-20261028.md. One commit, no push.

## B1 — smoke temperature-pattern amplitude (2026-10-28)

Approved minimal wiring only: Display current/weak/off → realView.temperaturePattern → real_view wrapper → bridge noiseAmp/noiseScale → legacy renderer uNoiseAmp/uNoiseScale. Defaults1/1 preserve the old shader expression; weak sets amplitude0.4, off uses the existing temperature toggle. Density, input temperatures, grey base, fire/plume logic and geometry are unchanged. Only temperature highlight RGB blending changes; scale stays1 in UI.

Browser-controlled GET-only fixture app/tests/smoke_amplitude_proxy.py pins clock180000 and compares pre-change snapshots against current assets. Four full WebGL595×700 scenes (S09/1420,1800;S06/890;all/coreON) each changed pixels0, risk included. Weak changes37332 pixels; return to current0. Actual uniforms prove temperatures/OD/fire+gas/HUD unchanged. app/tests/compare_smoke_amplitude.py and pure-store roundtrip pass. Production verified S09/1420/R2/oblique, restored current.54 frozen engine/server/render-order files unchanged. Evidence results/ui_refactor_stageB1_20261028; file diff counts in specs/웹앱-B1-온도무늬진폭-20261028.md. Stop before ramp/flame items, no push.

## B-2 연기 색 램프 (2026-10-28)
표시 탭 현재/중성, 기본 현재. uRampMode만 추가. 기본 4장면 픽셀 0, 중성 왕복 0, 엔진/서버/render_order 불변. 상세: specs/웹앱-B2-연기색램프-20261028.md.

## B-3 발열량 기준 불꽃 (2026-11-02)

표시 탭 성장 비율(기본)/발열량 기준. HRR 모드는 Q/HRRPUA 면적(셀 상한), 기존 플룸 Heskestad 높이, ID 해시 배열, 실제 HRR 상위 3개 조명을 사용한다. HRRPUA는 선별 계산과 같은 fire_load_table.json을 GET /cfbt/lite/fire-load-table로 직접 읽는다. 사용자 승인 예외: 서버 읽기 전용 3줄, 127.0.0.1만 허용. 계산·캐시·저장 불변. 기본 4장면 및 모드 왕복 0픽셀, 요청 캡처 7장 완료. 상세: specs/웹앱-B3-발열량불꽃-20261102.md. 증거: results/ui_B3_hrr_20261028. 한 커밋, push 없이 정지.


## C-0 HRR 불꽃 수정 (2026-11-02)
절대 혀 간격·cluster clamp·셀 마스크 내부 면적 4회 이분법·고정 0.3 m 감쇠. 성장 기본 4장면 픽셀 0. Q/HRRPUA 등가 지름과 마스크 보정 표시 원 지름을 구분한다. 상세: specs/웹앱-C0-HRR불꽃수정-20261102.md.


## C-1 이력 표시 (2026-11-02)
저장 지수 prefix 최대, 기본 이력 ON. 현재 미충족/과거 충족은 점선 리본, 현재 멤버 셀 충족 시 실선 우선. 셰이더·엔진 불변. S09 60분 FO 원본/화면 1실 일치; 이력 OFF 4장면 픽셀 0. 상세: specs/웹앱-C1-이력표시-20261102.md. C-2 미착수.


## C-2 사용자 화점 지정 (2026-11-02)
HUD 선택 실 → 탐색 원래 방 → 기존 screening 단일 rooms 요청으로 2극단 직렬 실행. R11 자동 후보 제외는 유지하되 수동 최초 화점 허용. UI 실측 2/2 완주, 배치 68.43초, 목록 2건 추가·장면 자동 교체 없음. S09/1420 3D 0픽셀, 동결 SHA 55개 동일. 상세: specs/웹앱-C2-사용자화점-20261102.md. C-3 미착수, C-9는 C-8 뒤.

## C-3 차량·진입 경로 (2026-11-02)
기존 보정된 전층 CAD 연결 639건 보존, 통행 155건. Dijkstra 거리·계단 1.5배·호스 15m, 차량 외부 클릭 이동. 3F 계산용 전이 그래프 92건과의 범위 차이는 보고서에 명시. 기본 94.36m/7본/계단2, 이동 59.36m/4본/계단2. 경로 OFF S09 픽셀0, 엔진 불변. specs/웹앱-C3-진입경로-20261102.md. C-4 미착수.
