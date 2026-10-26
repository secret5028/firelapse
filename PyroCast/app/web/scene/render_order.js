const policy=(order,depthTest,depthWrite)=>Object.freeze({order,depthTest,depthWrite});
export const RENDER_POLICY=Object.freeze({building:policy(0,true,true),core:policy(10,false,false),
 'openings.window':policy(20,true,false),smoke:policy(30,true,false),flame:policy(40,true,false),plume:policy(40,true,false),
 'openings.door':policy(50,false,false),risk:policy(60,false,false),selection:policy(70,false,false)});
export const RISK_TYPES=Object.freeze(['FO','FGI','backdraft','rollover','smoke']);
export const RISK_COLORS=Object.freeze({FO:'#ef4444',FGI:'#a855f7',backdraft:'#facc15',rollover:'#f97316',smoke:'#9ca3af'});
export const riskHeight=(floorZ,type)=>{const i=RISK_TYPES.indexOf(type);if(i<0)throw Error('Unknown risk type');return floorZ+.02+.015*i;};
export const LABELS=Object.freeze({building:'건물',openings:'문·창',core:'계단·승강기',smoke:'연기',flame:'화염',plume:'상승 플룸',risk:'위험 테두리',selection:'선택 실',upperCombustion:'상층 연소'});
export function applyRenderPolicy(object,key){const p=RENDER_POLICY[key];if(!p)throw Error('Unknown render policy');object.renderOrder=p.order;for(const mat of Array.isArray(object.material)?object.material:object.material?[object.material]:[]){mat.depthTest=p.depthTest;mat.depthWrite=p.depthWrite;}return object;}
