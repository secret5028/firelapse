const TYPES=[['FO','#ef4444'],['FGI','#a855f7'],['backdraft','#facc15']];
const finite=Number.isFinite;
const stamp=t=>`${Math.floor(t/60).toString().padStart(2,'0')}:${Math.floor(t%60).toString().padStart(2,'0')}`;
// Preserve saved samples and gaps. Never synthesize a multi-cell room average.
export function timelineRiskData(building,result,selection){
 const room=building?.floors?.flatMap(f=>f.rooms).find(r=>r.room_id===selection?.room_id);
 const cell=selection?.cell_id??(room?.cells?.length===1?room.cells[0].cell_id:null);
 const times=result?.time_s||[],end=result?.t_end_s||0;
 const rows=TYPES.map(([type,color])=>{
  const values=cell?result?.index_by_cell?.[cell]?.[type]:null;
  let peak=null;const segments=[];let segment=[];
  for(let i=0;i<times.length;i++){
   const t=times[i],value=values?.[i];
   if(!finite(t)||!finite(value)||value<=100){if(segment.length)segments.push(segment);segment=[];continue;}
   segment.push({t,value});if(!peak||value>peak.value)peak={t,value};
  }
  if(segment.length)segments.push(segment);
  return {type,label:type==='backdraft'?'BD':type,color,segments,peak};
 });
 return {cell,end,rows,scale:Math.max(100,...rows.map(r=>r.peak?.value??0))};
}
export function createTimelineRisk({host,store}){
 const ns='http://www.w3.org/2000/svg',chart=document.createElement('div');chart.className='timelineRisk';host.prepend(chart);
 const style=document.createElement('style');style.textContent=`
 .timelineRisk{position:relative;margin:0 7px 4px;height:auto}.timelineRisk[hidden]{display:none}
 .timelineRiskRow{position:relative;height:24px;border-bottom:1px solid #36516455}.timelineRiskRow svg{position:absolute;inset:0;width:100%;height:24px;overflow:visible}
 .timelineRiskLabel{position:absolute;left:0;top:3px;font-size:9px;line-height:14px;background:#142b3bcc;padding-right:3px;pointer-events:none}
 #pyroShellTimeline .timelinePeak{position:absolute;top:0;transform:translateX(-50%);font:9px/12px system-ui;white-space:nowrap;padding:0 3px;border:0;border-radius:3px;background:#142b3bc9;color:var(--peak-color);z-index:2}
 .timelineCursor{position:absolute;top:0;bottom:0;border-left:1px solid #e9f8ff;pointer-events:none;z-index:3}
 `;document.head.append(style);
 let end=0,cursor=null;
 const seek=t=>{store.dispatch('playback/play',{playing:false});store.dispatch('playback/seek',{t_s:t});};
 function sync(){if(cursor)cursor.style.left=Math.max(0,Math.min(100,(store.get('playback').t_s/(end||1))*100))+'%';}
 function draw(){
  chart.replaceChildren();const result=store.get('result'),data=timelineRiskData(store.get('building'),result,store.get('selection'));end=data.end;chart.hidden=!end;cursor=null;if(!end)return;
  chart.title='선택 셀 · 지수 100 초과 구간만 · 바닥선 100, 공통 축 · 최고점 클릭 시 해당 시간 이동';
  const rows=data.rows.filter(row=>row.peak);chart.hidden=!data.cell||!rows.length;if(chart.hidden)return;
  for(const row of rows){
   const lane=document.createElement('div');lane.className='timelineRiskRow';chart.append(lane);
   const svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 1000 24');svg.setAttribute('preserveAspectRatio','none');svg.setAttribute('aria-hidden','true');lane.append(svg);
   const x=t=>+(t/end*1000).toFixed(2),y=v=>+(22-Math.max(0,v-100)/Math.max(1,data.scale-100)*19).toFixed(2);
   for(const points of row.segments){
    if(points.length===1){const dot=document.createElementNS(ns,'circle');dot.setAttribute('cx',x(points[0].t));dot.setAttribute('cy',y(points[0].value));dot.setAttribute('r','1.8');dot.setAttribute('fill',row.color);svg.append(dot);}
    const line=points.map((p,i)=>`${i?'L':'M'}${x(p.t)},${y(p.value)}`).join(' ');
    const area=document.createElementNS(ns,'path');area.setAttribute('d',`${line} L${x(points.at(-1).t)},22 L${x(points[0].t)},22 Z`);area.setAttribute('fill',row.color);area.setAttribute('fill-opacity','.22');svg.append(area);
    const path=document.createElementNS(ns,'path');path.setAttribute('d',line);path.setAttribute('fill','none');path.setAttribute('stroke',row.color);path.setAttribute('stroke-width','1.2');path.setAttribute('vector-effect','non-scaling-stroke');svg.append(path);
   }
   const label=document.createElement('span');label.className='timelineRiskLabel';label.style.color=row.color;label.textContent=row.label;lane.append(label);
   if(row.peak){const p=row.peak,dot=document.createElementNS(ns,'circle');dot.setAttribute('cx',x(p.t));dot.setAttribute('cy',y(p.value));dot.setAttribute('r','2.4');dot.setAttribute('fill',row.color);svg.append(dot);const b=document.createElement('button');b.type='button';b.className='timelinePeak';b.style.left=(p.t/end*100)+'%';if(p.t/end<.1)b.style.transform='none';else if(p.t/end>.9)b.style.transform='translateX(-100%)';b.style.setProperty('--peak-color',row.color);b.textContent=String(Math.round(p.value));b.title=`${row.label} 최고 ${Math.round(p.value)} · ${stamp(p.t)} (동률은 최초 시각)`;b.setAttribute('aria-label',b.title+' 이동');b.onclick=()=>seek(p.t);lane.append(b);}
  }
  cursor=document.createElement('i');cursor.className='timelineCursor';chart.append(cursor);sync();
 }
 const off=['building','result','selection'].map(k=>store.subscribe(k,draw));off.push(store.subscribe('playback',sync));draw();
 return {dispose(){off.forEach(fn=>fn());chart.remove();style.remove();}};
}
