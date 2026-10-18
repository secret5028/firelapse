window.addEventListener('DOMContentLoaded',()=>{
 if(document.getElementById('fireFacilityPanel'))return;
 const host=document.getElementById('viewerPanel');if(!host)return;
 const panel=document.createElement('section');panel.id='fireFacilityPanel';const title=document.createElement('h2');title.textContent='소화설비';panel.append(title);
 const kinds=new Set(),equipment={hydrant:['indoorHydrant','옥내소화전'],extinguisher:['extinguisher','소화기'],inlet:['fireInlet','송수구'],pump:['waterPump','펌프'],tank:['waterTank','수조'],alarmValve:['fireValve','밸브']};
 const names={sprinkler:'스프링클러',waterPipe:'배관(계통 미확정)',indoorHydrant:'옥내소화전',standpipe:'연결송수관',waterSpray:'연결살수설비'};
 for(const p of state.pages){const f=p.fireFacilities;if(!f)continue;if(f.heads?.length)kinds.add('sprinkler');for(const b of f.pipes||[])kinds.add(b.system==='unknown'?'waterPipe':b.system||'waterPipe');for(const e of f.equipment||[]){const item=equipment[e.type];if(item){kinds.add(item[0]);names[item[0]]=item[1];}}}
 for(const key of kinds){const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=window.reviewLayerVisibility?.[key]!==false;check.onchange=()=>{window.reviewLayerVisibility??={};window.reviewLayerVisibility[key]=check.checked;window.reviewApplyLayers?.();};label.append(check,document.createTextNode(names[key]||key));panel.append(label);}
 if(kinds.size)host.append(panel);
});