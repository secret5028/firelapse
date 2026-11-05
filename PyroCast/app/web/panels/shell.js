import {createNewBuildingButton} from './new_building.js';
import {bindResizeHandle} from './resize_handle.js';
import {createTimelineRisk} from './timeline_risk.js';
// Stage 4 shell only: keep the working legacy panel intact in the result tab.
export function createPanelShell({panel,store,buildingFloors=[]}){
 const $=id=>document.getElementById(id),cleanups=[],moves=[];
 const move=(node,parent)=>{const marker=document.createComment('shell restore');node.before(marker);moves.push(()=>{marker.replaceWith(node);});parent.append(node);};
 const listen=(node,type,fn)=>{node.addEventListener(type,fn);cleanups.push(()=>node.removeEventListener(type,fn));};
 const style=document.createElement('style');style.dataset.pyrocastShell='true';style.textContent=`
 body.pyroShell{--shell-top:62px;--shell-bottom:58px;--shell-side:340px;--shell-mobile:42px}
 body.pyroShell>header:not(#pyroShellHeader){display:none!important}
 body.pyroShell #v{left:0!important;right:var(--shell-side)!important;top:var(--shell-top)!important;bottom:var(--shell-bottom)!important}
 #pyroShellHeader,#pyroShellSidebar,#pyroShellTimeline{position:fixed;box-sizing:border-box;z-index:125;color:#eaf3f8;background:#142b3b;font:13px/1.45 system-ui,'Malgun Gothic',sans-serif}
 #pyroShellHeader{top:0;left:0;right:0;min-height:48px;display:flex;align-items:center;gap:14px;padding:8px 14px;border-bottom:1px solid #496273}
 #pyroShellHeader .brand{font-weight:700;white-space:nowrap}#pyroShellHeader #fbtn{flex:1;min-width:0;display:flex;align-items:center;gap:6px}
 #pyroShellHeader #fbtn [hidden]{display:none!important}#shellFloor{min-width:86px;max-width:130px;color:#eaf3f8;background:#1d4158;border:1px solid #577487;border-radius:4px;padding:6px 9px;font:inherit}
 #shellSelectedRoom{font-size:14px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:230px;min-width:0;margin-left:5px}#shellSelectedRoom[hidden]{display:none!important}
 #pyroShellHeader #fbtn button[aria-pressed=true]{background:#e7be66;color:#142b3b;border-color:#f0d18e}
 #pyroShellSidebar{top:var(--shell-top);right:0;bottom:var(--shell-bottom);width:var(--shell-side);display:flex;flex-direction:column;border-left:1px solid #496273}
 body.pyroShell.shellHidden #v{right:0!important}#pyroShellSidebar[hidden]{display:none!important}
 #shellResize{position:absolute;left:-5px;top:0;bottom:0;width:10px;z-index:150;cursor:col-resize}#shellResize:hover,#shellResize:focus-visible{background:#42c4e855}
 #shellPanelToggle{position:fixed;top:calc(var(--shell-top) + 8px);right:calc(var(--shell-side) + 9px);z-index:140;width:30px;height:30px;padding:6px;color:#cbe2ed;background:#1c3545;border:1px solid #577487;border-radius:7px;cursor:pointer}body.shellHidden #shellPanelToggle{right:9px}
 #shellPanelToggle svg{display:block;width:16px;height:16px}
 #pyroShellTabs{display:flex;flex-shrink:0;border-bottom:1px solid #496273}
 #pyroShellTabs button{flex:1;border:0;border-radius:0;border-bottom:2px solid transparent;background:transparent;padding:12px 5px}
 #pyroShellTabs button[aria-selected=true]{border-bottom-color:#42c4e8;color:#a2efff;background:#1c3e52}
 #pyroShellSidebar .pyroPane{flex:1;min-height:0;overflow:auto}#pyroShellSidebar [hidden]{display:none!important}
 body.pyroShell #cfbtPanel{position:static;max-height:none;width:100%;border:0;overflow:visible;padding:12px;left:auto;right:auto;bottom:auto;font-size:12px}
 #pyroShellSidebar #cfbtPanel .row{align-items:flex-start}#pyroShellSidebar #cfbtPanel select{min-width:0;max-width:100%}
 #pyroShellTimeline{bottom:0;left:0;right:0;min-height:58px;padding:9px 14px;display:flex;align-items:center;gap:10px;border-top:1px solid #496273}
 #pyroShellTimeline .track{position:relative;flex:1;min-width:70px}#shellTime{width:100%;margin:0;accent-color:#42c4e8}
 #shellClock{white-space:nowrap;font-variant-numeric:tabular-nums}
 #pyroShellHeader button,#pyroShellSidebar>button,#pyroShellTabs button,#pyroShellTimeline button,#pyroShellTimeline select{color:inherit;background:#1d4158;border:1px solid #577487;border-radius:4px;padding:6px 9px;font:inherit;cursor:pointer}
 #pyroShellTabs button{border-radius:0;border-width:0 0 2px}#shellMobileToggle{display:none}
 #pyroShellHeader button:focus-visible,#pyroShellTabs button:focus-visible,#pyroShellTimeline :focus-visible{outline:2px solid #42c4e8;outline-offset:2px}
 @media(max-width:860px){body.pyroShell{--shell-mobile:42px}body.pyroShell.shellExpanded{--shell-mobile:46vh}body.pyroShell #v{right:0!important;bottom:calc(var(--shell-bottom) + var(--shell-mobile))!important}
 #pyroShellSidebar{top:auto;left:0;width:100%;height:var(--shell-mobile);border-left:0;border-top:1px solid #496273}#shellMobileToggle{display:block;min-height:40px;flex-shrink:0}body.pyroShell:not(.shellExpanded) #pyroShellTabs,body.pyroShell:not(.shellExpanded) .pyroPane{display:none!important}
 #shellResize{display:none}#shellPanelToggle{right:9px}body.pyroShell.shellHidden #v{bottom:var(--shell-bottom)!important}
 #pyroShellHeader{gap:8px;padding:6px 8px}#pyroShellHeader .brand{font-size:12px}#pyroShellHeader #fbtn{flex-wrap:nowrap!important;overflow-x:auto}#pyroShellHeader #fbtn button{white-space:nowrap}#pyroShellTimeline{padding:8px;gap:6px}#shellClock{font-size:11px}}
 `;document.head.append(style);document.body.classList.add('pyroShell');
 const header=document.createElement('header');header.id='pyroShellHeader';header.innerHTML='<span class="brand">PyroCast</span>';
 const sidebar=document.createElement('aside');sidebar.id='pyroShellSidebar';sidebar.setAttribute('aria-label','프로그램 패널');sidebar.innerHTML='<button id="shellMobileToggle" aria-expanded="false" aria-controls="pyroShellTabs">결과 패널 펼치기</button><div id="pyroShellTabs" role="tablist" aria-label="프로그램 메뉴"></div>';
 const timeline=document.createElement('footer');timeline.id='pyroShellTimeline';timeline.setAttribute('aria-label','시뮬레이션 재생');timeline.innerHTML='<button id="shellPlay">재생</button><select id="shellSpeed" aria-label="재생 배속">'+[1,5,10,20,30,60].map(v=>`<option value="${v}">${v}배</option>`).join('')+'</select><div class="track"><input id="shellTime" type="range" min="0" max="0" step="10" value="0" aria-label="시뮬레이션 시각"></div><output id="shellClock"></output>';
 document.body.append(header,sidebar,timeline);move($('fbtn'),header);
 const splitter=document.createElement('div');splitter.id='shellResize';splitter.setAttribute('aria-label','패널 너비 조절');splitter.title='드래그하여 패널 너비 조절';sidebar.prepend(splitter);
 let resizeFrame=null;const requestResize=()=>{if(resizeFrame===null)resizeFrame=requestAnimationFrame(()=>{resizeFrame=null;window.dispatchEvent(new Event('resize'));});};
 cleanups.push(bindResizeHandle(splitter,{axis:'x',value:()=>sidebar.getBoundingClientRect().width,setValue:n=>{document.body.style.setProperty('--shell-side',n+'px');requestResize();},limits:()=>[280,Math.min(640,innerWidth*.7)]}),()=>{if(resizeFrame!==null)cancelAnimationFrame(resizeFrame);document.body.style.removeProperty('--shell-side');});
 const toggle=document.createElement('button');toggle.id='shellPanelToggle';toggle.type='button';toggle.setAttribute('aria-controls','pyroShellSidebar');toggle.innerHTML='<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><rect x="2" y="3" width="16" height="14" rx="3"/><path d="M12 3v14"/></svg>';document.body.append(toggle);
 function toggleLabel(){const hidden=sidebar.hidden;toggle.title=hidden?'패널 펼치기':'패널 숨기기';toggle.setAttribute('aria-label',toggle.title);toggle.setAttribute('aria-expanded',String(!hidden));}
 listen(toggle,'click',()=>{sidebar.hidden=!sidebar.hidden;document.body.classList.toggle('shellHidden',sidebar.hidden);if(!sidebar.hidden&&innerWidth<=860){document.body.classList.add('shellExpanded');$('shellMobileToggle').setAttribute('aria-expanded','true');$('shellMobileToggle').textContent='패널 접기';}toggleLabel();requestResize();});toggleLabel();cleanups.push(()=>toggle.remove());
 const riskTimeline=createTimelineRisk({host:timeline.querySelector('.track'),store});cleanups.push(()=>riskTimeline.dispose());
 const buildingSelect=document.createElement('select');buildingSelect.id='shellBuilding';buildingSelect.setAttribute('aria-label','건물 선택');
 for(const [label,url] of [['강화 공장','http://127.0.0.1:8780/model.html'],['완도 저온창고','http://127.0.0.1:8832/data/wando-coldstore/model.html']])buildingSelect.add(new Option(label,url));
 buildingSelect.value=location.pathname.includes('/wando-coldstore/')?buildingSelect.options[1].value:buildingSelect.options[0].value;
 const catalogAbort=new AbortController();cleanups.push(()=>catalogAbort.abort());
 function refreshBuildings(){if(window.__PYROCAST_OFFLINE__||location.protocol==='file:')return;
  const current=document.body.dataset.operationUrl||buildingSelect.value;
  return fetch('http://127.0.0.1:8841/models/catalog.json',{signal:catalogAbort.signal}).then(r=>{if(!r.ok)throw Error('catalog');return r.json();}).then(c=>{
   if(catalogAbort.signal.aborted)return;buildingSelect.replaceChildren();
   for(const e of c.models)buildingSelect.add(new Option(e.label+(e.source_kind==='scan'?' [열람 전용]':''),e.operation_url||e.url));
   buildingSelect.value=current;
  }).catch(()=>{});
 }
 header.insertBefore(buildingSelect,$('fbtn'));listen(buildingSelect,'change',()=>location.assign(buildingSelect.value));
 refreshBuildings();cleanups.push(createNewBuildingButton({container:header,onCreated:refreshBuildings}));
 const tabs=[],panes=[];
 for(const [id,label] of [['building','설정·탐색'],['result','결과'],['display','표시']]){
  const tab=document.createElement('button');tab.id='shellTab-'+id;tab.type='button';tab.role='tab';tab.textContent=label;tab.setAttribute('aria-controls','shellPane-'+id);$('pyroShellTabs').append(tab);tabs.push(tab);
  const pane=document.createElement('section');pane.id='shellPane-'+id;pane.className='pyroPane';pane.role='tabpanel';pane.setAttribute('aria-labelledby',tab.id);pane.tabIndex=0;sidebar.append(pane);panes.push(pane);
  listen(tab,'click',()=>activate(id));listen(tab,'keydown',e=>{const i=tabs.indexOf(tab);let next;if(e.key==='ArrowRight')next=(i+1)%tabs.length;else if(e.key==='ArrowLeft')next=(i+tabs.length-1)%tabs.length;else if(e.key==='Home')next=0;else if(e.key==='End')next=tabs.length-1;else return;e.preventDefault();tabs[next].click();tabs[next].focus();});
 }
 const explorePane=document.createElement('div');explorePane.id='shellPane-explore';$('shellPane-building').append(explorePane);
 const exploreAlias=document.createElement('button');exploreAlias.id='shellTab-explore';exploreAlias.hidden=true;exploreAlias.onclick=()=>activate('building');sidebar.append(exploreAlias);
 function activate(id){if(id==='explore')id='building';tabs.forEach(t=>{const active=t.id==='shellTab-'+id;t.setAttribute('aria-selected',String(active));t.tabIndex=active?0:-1;});panes.forEach(p=>p.hidden=p.id!=='shellPane-'+id);}
 move(panel,$('shellPane-result'));activate('result');
 listen($('shellMobileToggle'),'click',()=>{const expanded=document.body.classList.toggle('shellExpanded');$('shellMobileToggle').setAttribute('aria-expanded',String(expanded));$('shellMobileToggle').textContent=expanded?'패널 접기':'결과 패널 펼치기';});
 listen($('shellPlay'),'click',()=>store.dispatch('playback/play',{playing:!store.get('playback').playing}));
 listen($('shellSpeed'),'change',()=>{store.dispatch('playback/speed',{speed:+$('shellSpeed').value});$('liteSpeed').value=$('shellSpeed').value;});
 listen($('shellTime'),'input',()=>{const t_s=+$('shellTime').value;store.dispatch('playback/play',{playing:false});store.dispatch('playback/seek',{t_s});});
 const stamp=t=>`${Math.floor(t/60).toString().padStart(2,'0')}:${Math.floor(t%60).toString().padStart(2,'0')}`;
 function sync(){const p=store.get('playback');$('shellPlay').textContent=p.playing?'일시정지':'재생';$('shellPlay').setAttribute('aria-pressed',String(p.playing));$('shellSpeed').value=p.speed;$('shellTime').max=p.t_end_s;$('shellTime').value=p.t_s;$('shellClock').textContent=`${stamp(p.t_s)} / ${stamp(p.t_end_s)}`;}
 function marks(){const r=store.get('result');$('shellTime').step=r?.dt_out_s||10;}
 const floorButtons=[...$('fbtn').querySelectorAll('button')],oldFloorAttributes=floorButtons.map(b=>[b,b.getAttribute('aria-pressed'),b.hidden]);
 const floorSelect=document.createElement('select');floorSelect.id='shellFloor';floorSelect.setAttribute('aria-label','층 선택');
 const placeholder=new Option('층 선택','');placeholder.disabled=true;floorSelect.add(placeholder);
 const floorOrder=new Map(buildingFloors.map((f,i)=>[f.name,i]));
 for(const b of [...floorButtons].sort((a,b)=>(floorOrder.get(a.textContent.trim())??Infinity)-(floorOrder.get(b.textContent.trim())??Infinity)))if(b.textContent.trim()!=='전체'){floorSelect.add(new Option(b.textContent.trim(),b.textContent.trim()));b.hidden=true;}
 $('fbtn').append(floorSelect);
 const roomLabel=document.createElement('span');roomLabel.id='shellSelectedRoom';roomLabel.setAttribute('aria-label','선택 방');roomLabel.hidden=true;$('fbtn').append(roomLabel);
 function selectedRoom(){
  const selection=store.get('selection'),floor=store.get('floor').floor_id;
  const source=buildingFloors.flatMap(f=>f.rooms.map(r=>({floor:f.name,room:r,key:`CAD_${f.name}_${r.id}`}))).find(r=>r.key===selection.room_id);
  const names=source?.room.names?.filter(Boolean)||[];
  roomLabel.textContent=names.join(' · ')||source?.room.name||source?.room.id||'';
  roomLabel.title=source?`${source.floor} ${source.room.id} · ${roomLabel.textContent}`:'';
  roomLabel.hidden=!source||(floor!==null&&floor!==source.floor);
 }
 cleanups.push(store.subscribe('selection',selectedRoom),store.subscribe('floor',selectedRoom),()=>roomLabel.remove());selectedRoom();
 // Invoke the original handler so every building keeps its existing floor and camera policy.
 listen(floorSelect,'change',()=>floorButtons.find(b=>b.textContent.trim()===floorSelect.value)?.click());
 const floors=()=>{const id=store.get('floor').floor_id;floorSelect.value=id??'';for(const b of floorButtons)b.setAttribute('aria-pressed',String(b.textContent.trim()===(id??'전체')));};
 cleanups.push(()=>{floorSelect.remove();for(const [b,value,hidden] of oldFloorAttributes){b.hidden=hidden;if(value===null)b.removeAttribute('aria-pressed');else b.setAttribute('aria-pressed',value);}});
 cleanups.push(store.subscribe('playback',sync),store.subscribe('result',marks),store.subscribe('floor',floors));sync();marks();floors();
 const sizes=()=>{document.body.style.setProperty('--shell-top',header.getBoundingClientRect().height+'px');document.body.style.setProperty('--shell-bottom',timeline.getBoundingClientRect().height+'px');};
 let sizeFrame=null;const ro=new ResizeObserver(()=>{if(sizeFrame===null)sizeFrame=requestAnimationFrame(()=>{sizeFrame=null;sizes();});});ro.observe(header);ro.observe(timeline);sizes();cleanups.push(()=>{ro.disconnect();if(sizeFrame!==null)cancelAnimationFrame(sizeFrame);});
 return {dispose(){for(const off of cleanups.reverse())off();for(const undo of moves.reverse())undo();header.remove();sidebar.remove();timeline.remove();style.remove();document.body.classList.remove('pyroShell','shellExpanded','shellHidden');document.body.style.removeProperty('--shell-top');document.body.style.removeProperty('--shell-bottom');}};
}
