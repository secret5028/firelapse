const policy=(order,depthTest,depthWrite,transparent=null,opacity=null)=>Object.freeze({order,depthTest,depthWrite,transparent,opacity});
// Verified legacy values replace the draft. Null preserves CAD material flags.
export const RENDER_POLICY=Object.freeze({building:policy(0,null,null),
 smoke:policy(10,false,false,true),plume:policy(15,false,false,true),flame:policy(20,false,false,true),
 gasFlame:policy(22,false,false,true),smokeBoundary:policy(23,false,false,true),cellOutline:policy(25,false,false,true),
 band:policy(26,false,false,true),interfacePlane:policy(27,false,false,true),interfaceLine:policy(28,false,false,true),
 'openings.window':policy(30,true,false,true,.65),risk:policy(35,false,false,true,1),selection:policy(40,false,false,true,.95),
 'openings.door':policy(46,false,false,true,.9),core:policy(70,false,false,true,.10),'core.tread':policy(72,false,false,true,.86),'core.edge':policy(73,false,false,true,.95)});
export const RISK_TYPES=Object.freeze(['FO','FGI','backdraft','rollover','smoke']);
export const RISK_COLORS=Object.freeze({FO:'#ef4444',FGI:'#a855f7',backdraft:'#facc15',rollover:'#f97316',smoke:'#9ca3af'});
export const riskHeight=(floorZ,height,activeHeights,type)=>{const i=['FO','FGI','backdraft','rollover'].indexOf(type);if(i<0||!activeHeights.length)throw Error('Active ribbon type/heights required');const base=Math.max(.16,Math.min(height-.5,...activeHeights));return floorZ+Math.min(height-.04,base+i*.14);};
// Display compatibility only. Shared conditions.*.met remains panel data.
export function displayV8Gates({color,smoke_stage,oxygen,loc,rollover_band}){
 const gas=smoke_stage===2&&Number.isFinite(loc)&&Number.isFinite(oxygen);
 return {FO:color==='#ef4444',FGI:color==='#a855f7'||(gas&&oxygen>=loc),
  backdraft:color==='#facc15'||(gas&&oxygen<loc),rollover:color==='#f97316'||rollover_band===true};
}
export const LABELS=Object.freeze({building:'건물',openings:'문·창',core:'계단·승강기',smoke:'연기',flame:'화염',plume:'상승 플룸',risk:'위험 테두리',selection:'선택 실',upperCombustion:'상층 연소'});
export function applyRenderPolicy(object,key){const p=RENDER_POLICY[key];if(!p)throw Error('Unknown render policy');
 if(!object.isMesh&&!object.isLine)throw Error('Render policy requires a Mesh/Line, not a Group');
 object.renderOrder=p.order;
 for(const mat of Array.isArray(object.material)?object.material:object.material?[object.material]:[]){
  const old=mat.transparent;if(p.depthTest!==null)mat.depthTest=p.depthTest;if(p.depthWrite!==null)mat.depthWrite=p.depthWrite;
  if(p.transparent!==null)mat.transparent=p.transparent;if(p.opacity!==null)mat.opacity=p.opacity;
  if(old!==mat.transparent)mat.needsUpdate=true;
 }return object;
}
