/* Local annotation journal. No network and no automatic model training. */
(function(root){
 const clone=x=>JSON.parse(JSON.stringify(x));
 const id=()=>globalThis.crypto.randomUUID();
 const snapshot=p=>Object.fromEntries(Object.keys(p).filter(k=>k!=='correctionLog'&&p[k]!==undefined).sort().map(k=>[k,clone(p[k])]));
 const signature=p=>JSON.stringify(snapshot(p));
 function ensure(state,data){
  state.learning ||= {schemaVersion:1,sourceHash:data.sourceHash,actorId:id(),pages:{},scenarioEvents:[],scenarioBaseline:clone(state.operations||{}),scenarioLast:clone(state.operations||{})};
  if(state.learning.sourceHash!==data.sourceHash)throw Error('학습 기록의 원본이 다릅니다.');
  const keys=new Set();
  state.pages.forEach((p,i)=>{
   const src=data.pages[i];
   const key=src.pageId||`${data.sourceHash}:page-${src.number??i+1}:index-${i}:render-${src.width}x${src.height}`;
   if(keys.has(key))throw Error('중복 페이지 식별자');keys.add(key);p.pageId=key;
   const used=new Set();for(const s of p.shapes||[]){if(!s.id||used.has(s.id))s.id=id();used.add(s.id);}
   state.learning.pages[key] ||= {pageId:key,sourcePage:src.sourcePage??src.number??i+1,width:src.width,height:src.height,
    prediction:clone(src.initial||{}),baseline:snapshot(p),last:snapshot(p),revisionId:id(),events:[],reviews:[],legacyLog:clone(p.correctionLog||[])};
  });return state.learning;
 }
 function sync(state,data,action='edit'){
  const book=ensure(state,data);let changed=0;
  for(const p of state.pages){const rec=book.pages[p.pageId],next=snapshot(p);
   if(JSON.stringify(next)===JSON.stringify(rec.last))continue;
   const revision=id();rec.events.push({eventId:id(),parentRevisionId:rec.revisionId,revisionId:revision,action,origin:'user-session',time:new Date().toISOString(),before:rec.last,after:clone(next)});
   rec.last=next;rec.revisionId=revision;for(const r of rec.reviews)if(r.status==='confirmed')r.status='stale';changed++;
  }
  const op=state.operations||{};
  if(JSON.stringify(op)!==JSON.stringify(book.scenarioLast)){book.scenarioEvents.push({eventId:id(),time:new Date().toISOString(),before:book.scenarioLast,after:clone(op),domain:'scenario-not-drawing'});book.scenarioLast=clone(op);changed++;}
  return changed;
 }
 function confirm(state,data,index,region,attributes){
  sync(state,data,'before-review');const p=state.pages[index],rec=state.learning.pages[p.pageId];
  const [x1,y1,x2,y2]=region;
  if(!region.every(Number.isFinite)||x1<0||y1<0||x2>rec.width||y2>rec.height||x2<=x1||y2<=y1)throw Error('검수 영역을 확인하세요.');
  const allowed=['geometry','openingKind','doorDirection'];
  if(!attributes.length||attributes.some(x=>!allowed.includes(x)))throw Error('검수할 항목을 선택하세요.');
  const r={reviewId:id(),revisionId:rec.revisionId,status:'confirmed',region:region.slice(),attributes:attributes.slice(),signature:signature(p),reviewerId:state.learning.actorId,time:new Date().toISOString()};rec.reviews.push(r);return r;
 }
 function correctionDiff(rec,p){
  const old=new Map((rec.baseline.shapes||[]).map(s=>[s.id,s])),now=new Map(p.shapes.map(s=>[s.id,s])),changes=[];
  const groups={geometry:['type','a','b','path'],openingKind:['openingKind','leaves'],doorDirection:['hinge','swingSide','openingAngle']};
  for(const entityId of new Set([...old.keys(),...now.keys()])){const before=old.get(entityId),after=now.get(entityId);
   const fields=Object.entries(groups).filter(([,keys])=>keys.some(k=>JSON.stringify(before?.[k])!==JSON.stringify(after?.[k]))).map(([k])=>k);
   if(!fields.length)continue;
   const points=[before,after].filter(Boolean).flatMap(s=>s.path||[s.a,s.b]);
   const bounds=[Math.min(...points.map(p=>p[0])),Math.min(...points.map(p=>p[1])),Math.max(...points.map(p=>p[0])),Math.max(...points.map(p=>p[1]))];
   changes.push({entityId,operation:!before?'add':!after?'delete':'modify',before:before?clone(before):null,after:after?clone(after):null,changedAttributes:fields,bounds});
  }return changes;
 }
 function exportDataset(state,data){
  sync(state,data,'before-export');const samples=[],correctionCandidates=[];
  for(let i=0;i<state.pages.length;i++){const p=state.pages[i],rec=state.learning.pages[p.pageId],src=data.pages[i];
   const changes=correctionDiff(rec,p);
   correctionCandidates.push(...changes.map(change=>({pageId:p.pageId,revisionId:rec.revisionId,...change,reviewStatus:'candidate',unchangedContext:'not-a-label'})));
   for(const r of rec.reviews.filter(r=>r.status==='confirmed'&&r.revisionId===rec.revisionId&&r.signature===signature(p))){
    const inside=q=>q[0]>=r.region[0]&&q[0]<=r.region[2]&&q[1]>=r.region[1]&&q[1]<=r.region[3];
    const entities=[],excluded=[],accepted=[];
    for(const change of changes){const pts=[change.before,change.after].filter(Boolean).flatMap(s=>s.path||[s.a,s.b]);if(!pts.every(inside)){excluded.push(change.entityId);continue;}
     const attrs=r.attributes.filter(a=>change.changedAttributes.includes(a));if(!attrs.length)continue;
     accepted.push({...change,confirmedAttributes:attrs});const s=change.after;if(!s)continue;
     const e={id:s.id,type:s.type};
     if(attrs.includes('geometry')){Object.assign(e,{a:s.a,b:s.b});if(s.path)e.path=clone(s.path);}
     if(attrs.includes('openingKind')&&s.openingKind)e.openingKind=s.openingKind;
     if(attrs.includes('doorDirection')&&s.type==='door')Object.assign(e,{hinge:s.hinge||'start',swingSide:s.swingSide??1});
     entities.push(e);
    }
    if(!accepted.length)continue;
    samples.push({pageId:p.pageId,sourcePage:rec.sourcePage,revisionId:rec.revisionId,review:clone(r),
     image:src.image,width:src.width,height:src.height,coordinateSystem:'source-image-pixels',
     corrections:accepted,labels:{format:'vector-corrections-only-v2',entities,excludedEntityIds:excluded,ignoreUnchangedEntities:true,ignoreOutsideRegion:true,unlistedAttributes:'unknown',boundaryCrossingEntities:'ignored',wallThickness:'unknown',unlabeledPixels:'unknown'},
     provenance:{prediction:rec.prediction,baseline:rec.baseline,events:rec.events},scale:p.scale});
   }
  }
  return {schemaVersion:1,datasetId:id(),createdAt:new Date().toISOString(),sourceHash:data.sourceHash,
   usage:'local-only',trainingPerformed:false,scope:'user-corrections-only',correctionCandidates,splitGroup:data.sourceHash,requiresBuildingGroupBeforeTraining:true,samples};
 }
 root.AnnotationStore={ensure,sync,confirm,exportDataset,snapshot};
 if(typeof module!=='undefined')module.exports=root.AnnotationStore;
})(globalThis);
