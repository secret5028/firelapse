# Vehicle move / selected room route — 2026-11-04

- Vehicle click opens Move / Close popup. Move uses the 1F ground plane and the visible ground grid bounds; an 8 x 2.6 m truck footprint must fit outside the building. Invalid placements keep the previous position; Esc/cancel exits placement.
- Settings/exploration room clicks update only route target, not fire origin, fuel, simulation or results.
- Door normals fall back to recorded aperture polygon edges when swing leaves are absent. No new graph edges. All exterior entrances are seeded for shortest weighted route; exterior segments route around the recorded building footprint. Interior remains the existing room-centre/door/stair approximation, with registered obstacle avoidance.
- Hotel source edges 513 unchanged. Default to 5F R16: 68.162 m / 5 hoses / 4 stairs. Position [-8,45,15.7]: 80.958 m / 6 hoses; entry D18 -> D0.
- UI: vehicle popup verified; indoor placement rejected; ground placement accepted at [-6.18472873220129,45.83070955763446,15.7]. Room click changed target to 5F R6, 82.659 m / 6 hoses / 4 stairs, settings tab retained. Console errors 0.
- Tests: route_selection (hotel, entrance minimum, exterior obstacle, grid limits), route (Ganghwa), route_layer (50 rebuilds/dispose), scale_reference PASS. Wando R5 23.516 m / 2 hoses remains valid.
- No simulation runs. No server/engine/shader edits. Test screenshots are from a separate browser tab.
