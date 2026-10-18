/* Offline demand calculation. SI units; no automatic facility or demand inference. */
(function(root){
'use strict';
const G=9.80665, MPA_PER_M=G/1000;
const finite=v=>typeof v==='number'&&Number.isFinite(v);
function inspect(net){
 const errors=[];
 if(!net||net.version!==1||!Array.isArray(net.nodes)||!Array.isArray(net.pipes))return ['계통 파일 형식이 올바르지 않습니다.'];
 if(net.nodes.length>1000||net.pipes.length>2000)return ['최대 1,000개 지점 / 2,000개 배관입니다.'];
 const ids=new Set(), edges=new Set();
 for(const n of net.nodes){if(!n||typeof n.id!=='string'||!n.id||ids.has(n.id))errors.push('지점 ID가 없거나 중복됩니다.');ids.add(n?.id);if(!['inlet','junction','outlet'].includes(n?.type))errors.push('지원하지 않는 지점 종류입니다.');if(typeof n?.name!=='string'||n.name.length>120)errors.push('지점 명칭을 확인하세요.');for(const k of ['x','y','z','flowLpm','residualMpa'])if(n?.[k]!=null&&!finite(n[k]))errors.push('지점 수치 형식을 확인하세요.');}
 for(const p of net.pipes){if(!p||typeof p.id!=='string'||!p.id||edges.has(p.id))errors.push('배관 ID가 없거나 중복됩니다.');edges.add(p?.id);if(!ids.has(p?.from)||!ids.has(p?.to)||p.from===p.to)errors.push('배관 연결 지점을 확인하세요.');if(!['open','closed','unknown'].includes(p?.state)||!['both','forward'].includes(p?.direction))errors.push('밸브 상태와 통수 방향을 확인하세요.');}
 if(net.active!=null&&(!Array.isArray(net.active)||net.active.some(v=>typeof v!=='string')))errors.push('동시 방수 선택 형식을 확인하세요.');
 return [...new Set(errors)];
}
function trace(net,inletId){
 const errors=inspect(net);if(errors.length)return {errors,nodes:[],pipes:[],outlets:[],unknown:[]};
 const inlet=net.nodes.find(n=>n.id===inletId&&n.type==='inlet');
 if(!inlet)return {errors:['송수구를 선택하세요.'],nodes:[],pipes:[],outlets:[],unknown:[]};
 const seen=new Set([inletId]), used=new Set(), queue=[inletId],unknown=new Set();
 for(let i=0;i<queue.length;i++)for(const p of net.pipes){
  let other=null;if(p.from===queue[i])other=p.to;else if(p.to===queue[i]&&p.direction==='both')other=p.from;
  if(other===null)continue;
  if(p.state==='unknown'){unknown.add(p.id);continue;}if(p.state==='closed')continue;
  used.add(p.id);if(!seen.has(other)){seen.add(other);queue.push(other);}
 }
 return {errors:[],nodes:[...seen],pipes:[...used],outlets:net.nodes.filter(n=>n.type==='outlet'&&seen.has(n.id)).map(n=>n.id),unknown:[...unknown]};
}
function pipeLoss(p,flowLpm){
 const q=flowLpm/60000,d=p.diameterMm/1000;
 const velocity=q/(Math.PI*d*d/4);
 const frictionM=10.67*p.lengthM*Math.pow(q,1.852)/(Math.pow(p.c,1.852)*Math.pow(d,4.8704));
 const minorM=p.k*velocity*velocity/(2*G);
 return {frictionM,minorM,lossM:frictionM+minorM,velocity};
}
function calculate(net,inletId,activeIds){
 const tr=trace(net,inletId), errors=[...tr.errors];
 const result={...tr,ok:false,errors,branches:[],segments:[],requiredMpa:null};
 if(errors.length)return result;
 const byId=new Map(net.nodes.map(n=>[n.id,n])), inlet=byId.get(inletId),active=[...new Set(activeIds||[])];
 if(net.reviewed!==true)errors.push('연결 관계·밸브 상태·계산 범위의 검토 확인이 필요합니다.');
 if(!active.length)errors.push('동시에 방수할 말단을 선택하세요.');
 if(tr.unknown.length)errors.push('선택 송수구 계통에 상태 미확인 밸브가 있습니다: '+tr.unknown.join(', '));
 if(tr.nodes.some(id=>id!==inletId&&byId.get(id).type==='inlet'))errors.push('다른 송수구와 연결되어 있습니다. 단일 공급 경계를 확인하고 분리하세요.');
 const edges=net.pipes.filter(p=>tr.pipes.includes(p.id));
 // A directed tree is also a tree when direction is ignored. Parallel pipes count as a loop.
 if(edges.length!==tr.nodes.length-1)errors.push('환상·병렬 계통은 유량 분배 해석이 필요하여 현재 계산에서 제외합니다.');
 const parent=new Map(), order=[inletId];
 for(let i=0;i<order.length;i++)for(const p of edges){let v=p.from===order[i]?p.to:(p.to===order[i]&&p.direction==='both'?p.from:null);if(v&&v!==inletId&&!parent.has(v)){parent.set(v,{node:order[i],pipe:p});order.push(v);}}
 const demand=new Map(tr.nodes.map(id=>[id,0]));
 if(!finite(inlet.y))errors.push('송수구 높이(m)를 입력하세요.');
 for(const id of active){const n=byId.get(id);if(!n||n.type!=='outlet'||!tr.outlets.includes(id)){errors.push('송수구에서 연결되지 않은 말단: '+id);continue;}
  if(!finite(n.flowLpm)||n.flowLpm<=0)errors.push(n.name+': 요구 유량(L/min)이 필요합니다.');
  if(!finite(n.residualMpa)||n.residualMpa<0)errors.push(n.name+': 필요 말단 압력(MPa)이 필요합니다.');
  if(!finite(n.y))errors.push(n.name+': 높이(m)가 필요합니다.');
  demand.set(id,n.flowLpm);
 }
 if(errors.length){result.errors=[...new Set(errors)];return result;}
 for(let i=order.length-1;i>0;i--){const id=order[i],p=parent.get(id);demand.set(p.node,demand.get(p.node)+demand.get(id));}
 const losses=new Map();
 for(const id of order.slice(1)){const {pipe:p}=parent.get(id),flow=demand.get(id);if(!flow)continue;
  if(!finite(p.lengthM)||p.lengthM<=0)errors.push(p.id+': 실제 배관 길이(m)가 필요합니다.');
  if(!finite(p.diameterMm)||p.diameterMm<=0)errors.push(p.id+': 배관 내경(mm)이 필요합니다.');
  if(!finite(p.c)||p.c<=0||p.c>200)errors.push(p.id+': Hazen–Williams C(0 초과, 200 이하)가 필요합니다.');
  if(!finite(p.k)||p.k<0)errors.push(p.id+': 이음쇠·밸브 손실계수 ΣK가 필요합니다(없음 확인 시 0).');
  if(p.reviewed!==true)errors.push(p.id+': 배관 제원 검토가 필요합니다.');
  if(!errors.length){const loss=pipeLoss(p,flow);losses.set(p.id,loss);result.segments.push({id:p.id,flowLpm:flow,...loss});}
 }
 if(errors.length){result.segments=[];result.errors=[...new Set(errors)];return result;}
 for(const id of active){const n=byId.get(id);let cur=id,frictionM=0,minorM=0,lengthM=0,path=[];
  while(cur!==inletId){const {pipe:p,node}=parent.get(cur),loss=losses.get(p.id);frictionM+=loss.frictionM;minorM+=loss.minorM;lengthM+=p.lengthM;path.unshift(p.id);cur=node;}
  const elevationM=n.y-inlet.y,requiredMpa=n.residualMpa+(frictionM+minorM+elevationM)*MPA_PER_M;
  result.branches.push({id,name:n.name,flowLpm:n.flowLpm,residualMpa:n.residualMpa,elevationM,frictionM,minorM,lengthM,path,requiredMpa});
 }
 result.branches.sort((a,b)=>b.requiredMpa-a.requiredMpa);
 result.requiredMpa=Math.max(0,result.branches[0].requiredMpa);result.totalFlowLpm=demand.get(inletId);result.critical=result.branches[0].id;
 if(!finite(result.requiredMpa)||result.segments.some(s=>!finite(s.lossM))){errors.push('입력 범위를 확인하세요. 계산 결과가 유효하지 않습니다.');result.requiredMpa=null;return result;}
 result.ok=true;return result;
}
root.FireHydraulics={inspect,trace,calculate,pipeLoss,MPA_PER_M};
})(globalThis);
