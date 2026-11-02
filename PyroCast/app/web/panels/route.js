export function createRoutePanel({store,graph}){
 const container=document.createElement('details');container.id='routeSettings';container.innerHTML='<summary>경로 설정</summary><label>호스 1본(m) <input id="routeHose" type="number" min="1" step="1" value="15"></label><label>계단 계수 <input id="routeStair" type="number" min="1" step="0.1" value="1.5"></label><div><button id="routePlace">차량 위치 지정</button><button id="routeReset">차량 기본 위치</button></div><div id="routeSummary"></div><div id="routeStatus" role="status"></div><span title="실 중심–문/계단 연결점 직선 거리 근사. 적재물·장애물·호스 굴곡은 미반영. 확인된 연결만 사용하며 진입 안전을 보증하지 않습니다.">ⓘ 경로 가정</span><pre id="routeDiagnostics" hidden></pre>';
 document.getElementById('exploreContent').append(container);
 const hud=document.createElement('div');hud.id='routeHUD';hud.style.cssText='padding-top:5px;font-size:12px;color:#9cdcff';document.querySelector('.compactHUD').append(hud);
 const $=id=>container.querySelector('#'+id);const cleanup=[];const on=(id,event,fn)=>{$(id).addEventListener(event,fn);cleanup.push(()=>$(id).removeEventListener(event,fn));};
 for(const [id,key] of [['routeHose','hose_m'],['routeStair','stair_factor']])on(id,'change',()=>{try{store.dispatch('route/set',{[key]:+$(id).value});$('routeStatus').textContent='';}catch(e){$('routeStatus').textContent=e.message;$(id).value=store.get('route')[key];}});
 on('routePlace','click',()=>store.dispatch('route/set',{placing:!store.get('route').placing}));on('routeReset','click',()=>store.dispatch('route/set',{vehicle:null,placing:false}));
 cleanup.push(store.subscribe('route',s=>{$('routePlace').textContent=s.placing?'차량 지정 취소':'차량 위치 지정';$('routeStatus').textContent=s.placing?'건물 밖 지면을 클릭하세요.':s.message;}));
 if(graph.error)for(const id of ['routePlace','routeReset','routeHose','routeStair'])$(id).disabled=true;
 return {update(r){hud.textContent=r.error?'경로 · '+r.error:`경로 ${r.length.toFixed(1)} m · 호스 ${r.hoses}본(+1 권장) · 계단 ${r.stairs}회`;hud.title=r.limits||r.error;$('routeSummary').textContent=hud.textContent;
  $('routeDiagnostics').textContent=JSON.stringify({main:graph.mainEntrance?.id,main_point:graph.mainEntrance?.point,default_vehicle:graph.defaultVehicle,...r});},dispose(){cleanup.forEach(f=>f());hud.remove();container.remove();}};
}
