import {createTimelineRisk} from './timeline_risk.js';
// Stage 4 shell only: keep the working legacy panel intact in the result tab.
export function createPanelShell({panel,store}){
 const $=id=>document.getElementById(id),cleanups=[],moves=[];
 const move=(node,parent)=>{const marker=document.createComment('shell restore');node.before(marker);moves.push(()=>{marker.replaceWith(node);});parent.append(node);};
 const listen=(node,type,fn)=>{node.addEventListener(type,fn);cleanups.push(()=>node.removeEventListener(type,fn));};
 const style=document.createElement('style');style.dataset.pyrocastShell='true';style.textContent=`
 body.pyroShell{--shell-top:62px;--shell-bottom:58px;--shell-side:340px;--shell-mobile:42px}
 body.pyroShell>header:not(#pyroShellHeader){display:none!important}
 body.pyroShell #v{left:0!important;right:var(--shell-side)!important;top:var(--shell-top)!important;bottom:var(--shell-bottom)!important}
 #pyroShellHeader,#pyroShellSidebar,#pyroShellTimeline{position:fixed;box-sizing:border-box;z-index:125;color:#eaf3f8;background:#142b3b;font:13px/1.45 system-ui,'Malgun Gothic',sans-serif}
 #pyroShellHeader{top:0;left:0;right:0;min-height:48px;display:flex;align-items:center;gap:14px;padding:8px 14px;border-bottom:1px solid #496273}
 #pyroShellHeader .brand{font-weight:700;white-space:nowrap}#pyroShellHeader #fbtn{flex:1;min-width:0}
 #pyroShellHeader #fbtn button[aria-pressed=true]{background:#e7be66;color:#142b3b;border-color:#f0d18e}
 #pyroShellSidebar{top:var(--shell-top);right:0;bottom:var(--shell-bottom);width:var(--shell-side);display:flex;flex-direction:column;border-left:1px solid #496273}
 #pyroShellTabs{display:flex;flex-shrink:0;border-bottom:1px solid #496273}
 #pyroShellTabs button{flex:1;border:0;border-radius:0;border-bottom:2px solid transparent;background:transparent;padding:12px 5px}
 #pyroShellTabs button[aria-selected=true]{border-bottom-color:#42c4e8;color:#a2efff;background:#1c3e52}
 #pyroShellSidebar .pyroPane{flex:1;min-height:0;overflow:auto}#pyroShellSidebar [hidden]{display:none!important}
 body.pyroShell #cfbtPanel{position:static;max-height:none;width:100%;border:0;overflow:visible;padding:12px;left:auto;right:auto;bottom:auto;font-size:12px}
 #pyroShellSidebar #cfbtPanel .row{align-items:flex-start}#pyroShellSidebar #cfbtPanel select{min-width:0;max-width:100%}
 #pyroShellTimeline{bottom:0;left:0;right:0;min-height:58px;padding:9px 14px;display:flex;align-items:center;gap:10px;border-top:1px solid #496273}
 #pyroShellTimeline .track{position:relative;flex:1;min-width:70px;padding-bottom:6px}#shellTime{width:100%;margin:0;accent-color:#42c4e8}
 #shellMarks{position:absolute;left:7px;right:7px;height:6px;bottom:0;pointer-events:none}#shellMarks i{position:absolute;height:6px;border-left:2px solid #ffb34d}#shellMarks i.fo{border-color:#ef4444}
 #shellClock{white-space:nowrap;font-variant-numeric:tabular-nums}
 #pyroShellHeader button,#pyroShellSidebar>button,#pyroShellTabs button,#pyroShellTimeline button,#pyroShellTimeline select{color:inherit;background:#1d4158;border:1px solid #577487;border-radius:4px;padding:6px 9px;font:inherit;cursor:pointer}
 #pyroShellTabs button{border-radius:0;border-width:0 0 2px}#shellMobileToggle{display:none}
 #pyroShellHeader button:focus-visible,#pyroShellTabs button:focus-visible,#pyroShellTimeline :focus-visible{outline:2px solid #42c4e8;outline-offset:2px}
 @media(max-width:860px){body.pyroShell{--shell-mobile:42px}body.pyroShell.shellExpanded{--shell-mobile:46vh}body.pyroShell #v{right:0!important;bottom:calc(var(--shell-bottom) + var(--shell-mobile))!important}
 #pyroShellSidebar{top:auto;left:0;width:100%;height:var(--shell-mobile);border-left:0;border-top:1px solid #496273}#shellMobileToggle{display:block;min-height:40px;flex-shrink:0}body.pyroShell:not(.shellExpanded) #pyroShellTabs,body.pyroShell:not(.shellExpanded) .pyroPane{display:none!important}
 #pyroShellHeader{gap:8px;padding:6px 8px}#pyroShellHeader .brand{font-size:12px}#pyroShellHeader #fbtn{flex-wrap:nowrap!important;overflow-x:auto}#pyroShellHeader #fbtn button{white-space:nowrap}#pyroShellTimeline{padding:8px;gap:6px}#shellClock{font-size:11px}}
 `;document.head.append(style);document.body.classList.add('pyroShell');
 const header=document.createElement('header');header.id='pyroShellHeader';header.innerHTML='<span class="brand">PyroCast</span>';
 const sidebar=document.createElement('aside');sidebar.id='pyroShellSidebar';sidebar.setAttribute('aria-label','프로그램 패널');sidebar.innerHTML='<button id="shellMobileToggle" aria-expanded="false" aria-controls="pyroShellTabs">결과 패널 펼치기</button><div id="pyroShellTabs" role="tablist" aria-label="프로그램 메뉴"></div>';
 const timeline=document.createElement('footer');timeline.id='pyroShellTimeline';timeline.setAttribute('aria-label','시뮬레이션 재생');timeline.innerHTML='<button id="shellPlay">재생</button><select id="shellSpeed" aria-label="재생 배속">'+[1,5,10,20,30,60].map(v=>`<option value="${v}">${v}배</option>`).join('')+'</select><div class="track"><input id="shellTime" type="range" min="0" max="0" step="10" value="0" aria-label="시뮬레이션 시각"><div id="shellMarks" aria-hidden="true"></div></div><output id="shellClock"></output>';
 document.body.append(header,sidebar,timeline);move($('fbtn'),header);
 const riskTimeline=createTimelineRisk({host:timeline.querySelector('.track'),store});cleanups.push(()=>riskTimeline.dispose());
 const buildingSelect=document.createElement('select');buildingSelect.id='shellBuilding';buildingSelect.setAttribute('aria-label','건물 선택');
 for(const [label,url] of [['강화 공장','http://127.0.0.1:8780/model.html'],['완도 저온창고','http://127.0.0.1:8832/data/wando-coldstore/model.html']])buildingSelect.add(new Option(label,url));
 buildingSelect.value=location.pathname.includes('/wando-coldstore/')?buildingSelect.options[1].value:buildingSelect.options[0].value;
 const catalogAbort=new AbortController();cleanups.push(()=>catalogAbort.abort());
 if(!window.__PYROCAST_OFFLINE__&&location.protocol!=='file:'){
  const current=document.body.dataset.operationUrl||buildingSelect.value;
  buildingSelect.add(new Option('전체 모델 · 과거 작업 보기','http://127.0.0.1:8841/models/'));
  fetch('http://127.0.0.1:8841/models/catalog.json',{signal:catalogAbort.signal}).then(r=>{if(!r.ok)throw Error('catalog');return r.json();}).then(c=>{
   if(catalogAbort.signal.aborted)return;buildingSelect.replaceChildren();
   for(const e of c.models)buildingSelect.add(new Option(e.label+(e.source_kind==='scan'?' [열람 전용]':''),e.operation_url||e.url));
   buildingSelect.value=current;
  }).catch(()=>{});
 }
 header.insertBefore(buildingSelect,$('fbtn'));listen(buildingSelect,'change',()=>location.assign(buildingSelect.value));
 const tabs=[],panes=[];
 for(const [id,label] of [['building','건물'],['explore','탐색'],['result','결과'],['display','표시']]){
  const tab=document.createElement('button');tab.id='shellTab-'+id;tab.type='button';tab.role='tab';tab.textContent=label;tab.setAttribute('aria-controls','shellPane-'+id);$('pyroShellTabs').append(tab);tabs.push(tab);
  const pane=document.createElement('section');pane.id='shellPane-'+id;pane.className='pyroPane';pane.role='tabpanel';pane.setAttribute('aria-labelledby',tab.id);pane.tabIndex=0;sidebar.append(pane);panes.push(pane);
  listen(tab,'click',()=>activate(id));listen(tab,'keydown',e=>{const i=tabs.indexOf(tab);let next;if(e.key==='ArrowRight')next=(i+1)%tabs.length;else if(e.key==='ArrowLeft')next=(i+tabs.length-1)%tabs.length;else if(e.key==='Home')next=0;else if(e.key==='End')next=tabs.length-1;else return;e.preventDefault();tabs[next].click();tabs[next].focus();});
 }
 function activate(id){tabs.forEach(t=>{const active=t.id==='shellTab-'+id;t.setAttribute('aria-selected',String(active));t.tabIndex=active?0:-1;});panes.forEach(p=>p.hidden=p.id!=='shellPane-'+id);}
 move(panel,$('shellPane-result'));activate('result');
 listen($('shellMobileToggle'),'click',()=>{const expanded=document.body.classList.toggle('shellExpanded');$('shellMobileToggle').setAttribute('aria-expanded',String(expanded));$('shellMobileToggle').textContent=expanded?'패널 접기':'결과 패널 펼치기';});
 listen($('shellPlay'),'click',()=>store.dispatch('playback/play',{playing:!store.get('playback').playing}));
 listen($('shellSpeed'),'change',()=>{store.dispatch('playback/speed',{speed:+$('shellSpeed').value});$('liteSpeed').value=$('shellSpeed').value;});
 listen($('shellTime'),'input',()=>{const t_s=+$('shellTime').value;store.dispatch('playback/play',{playing:false});store.dispatch('playback/seek',{t_s});});
 const stamp=t=>`${Math.floor(t/60).toString().padStart(2,'0')}:${Math.floor(t%60).toString().padStart(2,'0')}`;
 function sync(){const p=store.get('playback');$('shellPlay').textContent=p.playing?'일시정지':'재생';$('shellPlay').setAttribute('aria-pressed',String(p.playing));$('shellSpeed').value=p.speed;$('shellTime').max=p.t_end_s;$('shellTime').value=p.t_s;$('shellClock').textContent=`${stamp(p.t_s)} / ${stamp(p.t_end_s)}`;}
 function marks(){const r=store.get('result'),host=$('shellMarks');host.replaceChildren();if(!r?.t_end_s)return;$('shellTime').step=r.dt_out_s||10;
  const entries=r.events.filter(e=>e.kind==='supply_start').map(e=>({t:e.t_s,title:`${e.room_id} 연료 공급 시작`,fo:false}));
  for(const [id,frames] of Object.entries(r.conditions)){const i=r.time_s.findIndex((_,i)=>frames[i]?.FO?.met===true);if(i>=0)entries.push({t:r.time_s[i],title:`${id} FO 조건 충족`,fo:true});}
  for(const e of entries){const mark=document.createElement('i');mark.style.left=Math.min(100,e.t/r.t_end_s*100)+'%';mark.className=e.fo?'fo':'';mark.title=e.title+' '+stamp(e.t);host.append(mark);}
 }
 const floors=()=>{const id=store.get('floor').floor_id;for(const b of $('fbtn').children)b.setAttribute('aria-pressed',String(b.textContent===(id??'전체')));};
 const oldFloorAttributes=[...$('fbtn').children].map(b=>[b,b.getAttribute('aria-pressed')]);
 cleanups.push(()=>{for(const [b,value] of oldFloorAttributes)if(value===null)b.removeAttribute('aria-pressed');else b.setAttribute('aria-pressed',value);});
 cleanups.push(store.subscribe('playback',sync),store.subscribe('result',marks),store.subscribe('floor',floors));sync();marks();floors();
 const sizes=()=>{document.body.style.setProperty('--shell-top',header.getBoundingClientRect().height+'px');document.body.style.setProperty('--shell-bottom',timeline.getBoundingClientRect().height+'px');};
 let sizeFrame=null;const ro=new ResizeObserver(()=>{if(sizeFrame===null)sizeFrame=requestAnimationFrame(()=>{sizeFrame=null;sizes();});});ro.observe(header);ro.observe(timeline);sizes();cleanups.push(()=>{ro.disconnect();if(sizeFrame!==null)cancelAnimationFrame(sizeFrame);});
 return {dispose(){for(const off of cleanups.reverse())off();for(const undo of moves.reverse())undo();header.remove();sidebar.remove();timeline.remove();style.remove();document.body.classList.remove('pyroShell','shellExpanded');document.body.style.removeProperty('--shell-top');document.body.style.removeProperty('--shell-bottom');}};
}
