// Progress is processed MC samples, not a wall-clock estimate or a success rate.
export function mcProgressState(job={},pending=false,origin=null){
 const active=pending||job.running||job.state==='queued';
 const terminal=['completed','failed','interrupted'].includes(job.state);
 if(!active&&(!terminal||(job.room&&job.room!==origin)))return {visible:false};
 const known=!pending&&Number.isFinite(job.total)&&job.total>0&&Number.isFinite(job.completed);
 const percent=known?Math.round(Math.min(1,Math.max(0,job.completed/job.total))*100):null;
 const warning=job.error||['failed','interrupted'].includes(job.state)||job.failed_or_incomplete>0||job.excluded_physically_invalid>0;
 return {visible:true,percent,state:warning?'warning':job.state==='completed'?'complete':'running',
  text:percent===null?(pending?'준비 중':'진행률 확인 중'):`${percent}%`};
}
export function createMCProgress(){
 const root=document.createElement('div');root.id='exploreMCProgress';root.hidden=true;
 root.innerHTML='<div class="mcProgressHeading"><span>MC 전체 진행</span><span id="exploreMCPercent"></span></div><progress id="exploreMCBar" max="100" aria-label="MC 전체 진행률"></progress>';
 const style=document.createElement('style');style.textContent=`
 #exploreMCProgress{margin-top:12px;--mc-progress:var(--accent)}#exploreMCProgress[data-state=complete]{--mc-progress:#62dcb0}#exploreMCProgress[data-state=warning]{--mc-progress:#f59e0b}
 .mcProgressHeading{display:flex;justify-content:space-between;gap:8px;margin-bottom:6px;font-size:12px;font-variant-numeric:tabular-nums;color:var(--mc-progress)}
 #exploreMCBar{display:block;appearance:none;width:100%;height:10px;border:0;border-radius:6px;overflow:hidden;background:var(--bg-control);accent-color:var(--mc-progress)}
 #exploreMCBar::-webkit-progress-bar{background:var(--bg-control);border-radius:6px}#exploreMCBar::-webkit-progress-value{background:var(--mc-progress);border-radius:6px;transition:width .2s}#exploreMCBar::-moz-progress-bar{background:var(--mc-progress)}
 #exploreMCBar:indeterminate{background:linear-gradient(90deg,var(--bg-control),var(--mc-progress),var(--bg-control));background-size:200% 100%;animation:mcProgressPending 1.5s linear infinite}#exploreMCBar:indeterminate::-webkit-progress-bar{background:transparent}
 @keyframes mcProgressPending{to{background-position:-200% 0}}@media(prefers-reduced-motion:reduce){#exploreMCBar{animation:none!important}#exploreMCBar::-webkit-progress-value{transition:none}}
 `;root.append(style);
 const bar=root.querySelector('progress'),label=root.querySelector('#exploreMCPercent');
 return {root,update(job,pending,origin){const state=mcProgressState(job,pending,origin);root.hidden=!state.visible;if(!state.visible)return;
  root.dataset.state=state.state;label.textContent=state.text;
  if(state.percent===null){bar.removeAttribute('value');bar.setAttribute('aria-valuetext',state.text);}
  else{bar.value=state.percent;bar.setAttribute('aria-valuetext',state.text+' 진행');}
 }};
}
