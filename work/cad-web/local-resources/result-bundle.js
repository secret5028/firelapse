/* Portable ZIP (stored entries, UTF-8 filenames). No external dependency. */
(function(root){
 function zip(files){
  const enc=new TextEncoder(),parts=[],central=[];let offset=0;
  const crc=bytes=>{let c=0xffffffff;for(const b of bytes){c^=b;for(let i=0;i<8;i++)c=(c>>>1)^((c&1)?0xedb88320:0);}return (c^0xffffffff)>>>0;};
  for(const [name,content]of Object.entries(files)){
   const n=enc.encode(name),b=enc.encode(content),sum=crc(b),h=new Uint8Array(30),v=new DataView(h.buffer);
   v.setUint32(0,0x04034b50,true);v.setUint16(4,20,true);v.setUint16(6,0x800,true);v.setUint32(14,sum,true);v.setUint32(18,b.length,true);v.setUint32(22,b.length,true);v.setUint16(26,n.length,true);
   const ch=new Uint8Array(46),cv=new DataView(ch.buffer);cv.setUint32(0,0x02014b50,true);cv.setUint16(4,20,true);cv.setUint16(6,20,true);cv.setUint16(8,0x800,true);cv.setUint32(16,sum,true);cv.setUint32(20,b.length,true);cv.setUint32(24,b.length,true);cv.setUint16(28,n.length,true);cv.setUint32(42,offset,true);
   parts.push(h,n,b);central.push(ch,n);offset+=h.length+n.length+b.length;
  }
  const size=central.reduce((a,b)=>a+b.length,0),end=new Uint8Array(22),ev=new DataView(end.buffer);ev.setUint32(0,0x06054b50,true);ev.setUint16(8,Object.keys(files).length,true);ev.setUint16(10,Object.keys(files).length,true);ev.setUint32(12,size,true);ev.setUint32(16,offset,true);
  return new Blob([...parts,...central,end],{type:'application/zip'});
 }
 root.ResultBundle={zip};if(typeof module!=='undefined'){module.exports=root.ResultBundle;return;}
 const button=document.getElementById('export'),previous=button.onclick;
 button.textContent='3D + 학습자료 저장';
 button.onclick=async e=>{
  const originalDownload=download;let html;
  try{
   window.reviewLearning?.sync('bundle-export');
   const dataset=AnnotationStore.exportDataset(state,D),saved=JSON.parse(JSON.stringify(state));
   // The existing exporter embeds the current editable model and all Three.js assets.
   download=(name,content,mime)=>{if(mime?.startsWith('text/html'))html=content;else originalDownload(name,content,mime);};
   try{previous(e);}finally{download=originalDownload;}
   if(!html)throw Error('3D HTML을 생성하지 못했습니다.');
   const files={
    '3D-모델.html':html,
    '작업.json':JSON.stringify(saved),
    '학습데이터/검수정답.json':JSON.stringify(dataset),
    '학습데이터/전체수정이력.json':JSON.stringify({sourceHash:D.sourceHash,learning:saved.learning}),
    '학습데이터/원본페이지.json':JSON.stringify({sourceHash:D.sourceHash,pages:D.pages}),
    'manifest.json':JSON.stringify({schemaVersion:1,createdAt:new Date().toISOString(),sourceHash:D.sourceHash,reviewedSamples:dataset.samples.length,trainingPerformed:false,usage:'local-only',model:'3D-모델.html',project:'작업.json'}),
    '읽어주세요.txt':'3D-모델.html을 브라우저에서 여세요. 작업.json으로 편집을 이어갑니다.\n학습데이터에는 원본 페이지와 모든 수정 기록이 포함됩니다. 검수정답.json의 samples만 검수된 자료이며, 비어 있으면 검수 정답이 없는 상태입니다. 미검수 기록은 자동으로 정답이 되지 않습니다. 모델 학습은 실행하지 않았습니다.'
   };
   originalDownload(D.name.replace(/[\\/:*?"<>|]/g,'_')+'-3D-학습자료.zip',zip(files),'application/zip');
   text('3D 결과·작업·학습 데이터를 ZIP 하나로 저장했습니다.');
  }catch(err){download=originalDownload;text('묶음 저장 실패: '+err.message);}
 };
})(globalThis);
