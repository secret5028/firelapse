// Presentation-only migration. Legacy modules and their request handlers stay intact.
export const explanatoryText = text => /(?:입니다|합니다|않습니다|없습니다|아닙니다|뜻하지|표시용|계산 아님|예측 아님|확률 아님|확률이 아님|별개|별도|검토용|자동으로|전파 계산|기준이며|서로 다른|표시 효과|미연결|보는 쪽 외부 창만|도면 문틀 ·|위험 테두리:|임계값은 사용자 가정|가스 화염 표현 끔)/.test(text);
export function infoTip(text){
 const info=document.createElement('span');info.className='panelInfo';info.tabIndex=0;info.textContent='ⓘ';info.dataset.tip=text;info.title=text;info.setAttribute('aria-label',text);return info;
}
export function attachExplanations(){
 const roots=[document.getElementById('pyroShellSidebar'),document.getElementById('cfMeaning')].filter(Boolean),moved=[];
 const excluded='[data-tip],#resultLimits,script,style,button,input,select,textarea,[role="alert"],[role="status"]';
 const style=document.createElement('style');style.dataset.pyrocastExplanations='true';
 style.textContent='.panelInfo{display:inline-block;cursor:help;margin-left:4px;color:#b8cbd8}.panelInfo:focus-visible{outline:2px solid #42c4e8}#panelTipPopover{position:fixed;z-index:1000;max-width:min(320px,calc(100vw - 24px));padding:10px;background:#193648;color:#eaf3f8;border:1px solid #698493;border-radius:5px;font:12px/1.5 system-ui;white-space:pre-line;overflow-wrap:anywhere;pointer-events:none}';document.head.append(style);
 const popup=document.createElement('div');popup.id='panelTipPopover';popup.role='tooltip';popup.hidden=true;document.body.append(popup);
 function show(event){const node=event.target.closest?.('[data-tip]');if(!node||!roots.some(r=>r.contains(node)))return;popup.textContent=node.dataset.tip;popup.hidden=false;const box=node.getBoundingClientRect(),w=popup.offsetWidth,h=popup.offsetHeight;popup.style.left=Math.max(12,Math.min(innerWidth-w-12,box.left))+'px';popup.style.top=Math.max(12,Math.min(innerHeight-h-12,box.bottom+6))+'px';}
 const hide=()=>popup.hidden=true;
 const listeners=[['pointerover',show],['focusin',show],['click',show],['pointerout',hide],['focusout',hide],['keydown',e=>{if(e.key==='Escape')hide();}]];
 for(const [event,fn] of listeners)document.addEventListener(event,fn);
 function migrate(){
  for(const root of roots){
   for(const info of root.querySelectorAll('span[title]'))if(info.textContent.trim()==='ⓘ'&&!info.dataset.tip){info.dataset.tip=info.title;info.setAttribute('aria-label',info.title);}
   // Imported read-only menus and frozen-rule reports can refresh their DOM.
   for(const scope of root.querySelectorAll('#exploreRuleMount')){
    for(const status of scope.querySelectorAll('#liteScreening [role="status"]')){
     const marker=' N 변경은 저장된 결과를 재계산하지 않습니다.',text=status.textContent,index=text.indexOf(marker);
     if(index>=0&&!status.querySelector('[data-tip]'))status.replaceChildren(text.slice(0,index),infoTip(text.slice(index).trim()));
    }
    for(const summary of scope.querySelectorAll('summary')){
     if(summary.textContent.trim()==='MC 10표본 결과 · 발생확률 아님')summary.replaceChildren('MC 10표본 결과',infoTip('표본 비율은 발생확률이 아닙니다.'));
    }
    for(const node of [...scope.querySelectorAll('p,small,div,span')].reverse()){
     if(node.closest(excluded)||node.querySelector('input,select,button,textarea,table,details,[data-tip],[role="alert"],[role="status"]'))continue;
     const text=node.textContent.trim();if(!explanatoryText(text)||/로드 실패|읽기 실패/.test(text))continue;
     moved.push({scope:scope.id,id:node.id,text});node.replaceChildren(infoTip(text));node.hidden=false;
    }
    // Mixed paragraphs contain live buttons/labels; move only their prose text nodes.
    const walker=document.createTreeWalker(scope,NodeFilter.SHOW_TEXT),texts=[];
    while(walker.nextNode())texts.push(walker.currentNode);
    for(const textNode of texts){const parent=textNode.parentElement,text=textNode.textContent.trim();
     if(!parent||parent.closest('[data-tip],script,style,button,select,textarea,summary,[role="alert"]')||!explanatoryText(text))continue;
     if(parent.closest('[role="status"]')&&!parent.id.endsWith('cfbtComparison'))continue;
     moved.push({scope:scope.id,id:parent.id,text});textNode.replaceWith(infoTip(text));
    }
   }
  }
 }
 const observer=new MutationObserver(()=>{observer.disconnect();migrate();observe();});
 const observe=()=>roots.forEach(root=>observer.observe(root,{childList:true,subtree:true,characterData:true}));migrate();observe();
 return {moved,dispose(){observer.disconnect();for(const [event,fn] of listeners)document.removeEventListener(event,fn);popup.remove();style.remove();}};
}
