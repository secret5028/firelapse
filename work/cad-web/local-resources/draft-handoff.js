/* Saved detector output is a reference, editable geometry remains the model. */
(function(){
 const box=document.createElement('section');
 box.style.cssText='padding:10px;background:#17364b;border:1px solid #7293a3;margin-bottom:10px';
 box.innerHTML='<b>AI 판독 초안 → 직접 수정 → 3D</b><p>노랑: 벽 · 파랑: 창 · 빨강: 문</p><button id="draftReference">원래 AI 판독 보기</button><p>편집 선은 판독을 변환한 초안입니다. 문 종류·방향과 치수를 확인하고 작업 저장을 누르세요.</p>';
 document.querySelector('aside').prepend(box);
 const refs=D.pages.map(p=>{const im=new Image();im.src=p.detectorOverlay||p.image;return im;});
 let reference=false;
 const oldDraw=draw;
 draw=function(){oldDraw();if(mode!=='2d')return;ctx.save();ctx.translate(offset.x,offset.y);ctx.scale(zoom,zoom);
  if(reference&&refs[index]?.complete){ctx.drawImage(refs[index],0,0,D.pages[index].width,D.pages[index].height);}
  else if(!window.hideModelLines&&!window.guidedEditor){for(const sh of current().shapes){if(sh.type!=='door')continue;
   const kind=sh.openingKind||'single';if(!['single','double'].includes(kind))continue;
   const side=sh.swingSide===-1?-1:1, a=sh.a,b=sh.b;
   const leaf=(h,t,r)=>{const angle=Math.atan2(t[1]-h[1],t[0]-h[0]);ctx.beginPath();ctx.moveTo(...h);ctx.lineTo(h[0]+Math.cos(angle+side*Math.PI/2)*r,h[1]+Math.sin(angle+side*Math.PI/2)*r);ctx.stroke();ctx.beginPath();ctx.arc(h[0],h[1],r,angle,angle+side*Math.PI/2,side<0);ctx.stroke();};
   ctx.strokeStyle='#ff626a';ctx.lineWidth=1.5/zoom;const len=Math.hypot(b[0]-a[0],b[1]-a[1]);
   if(kind==='double'){leaf(a,b,len/2);leaf(b,a,len/2);}else if(sh.hinge==='end')leaf(b,a,len);else leaf(a,b,len);
  }}ctx.restore();
 };
 const button=document.getElementById('draftReference');
 button.onclick=()=>{reference=!reference;button.textContent=reference?'편집 선으로 돌아가기':'원래 AI 판독 보기';c.style.pointerEvents=reference?'none':'';draw();};
 switchMode('2d');draw();
})();
