// Smoke visibility must never depend on a risk flag or on the selected room.
export function smokeLayerVisibility({enabled,smokeEnabled,opticalDensity,thickness,riskColor}){
 const visible=!!enabled&&!!smokeEnabled&&Number.isFinite(opticalDensity)&&opticalDensity>1e-5&&thickness>.01;
 return {visible,outlineVisible:visible&&!!riskColor};
}
