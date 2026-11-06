// Cleanup is deliberately a two-step action; rendering/export never deletes data.
export function createStoragePanel(host){
 const root=document.createElement('details');root.id='resultStorage';
 if(location.protocol==='file:'||document.getElementById('pcOfflineData'))return {dispose(){}};
 root.innerHTML='<summary>저장공간 · 계산 과정 정리</summary><div style="font-size:11px;color:var(--text-muted);line-height:1.5;margin:8px 0">이 PC의 전체 계산 · 입력·최종 결과·MC 집계 보존</div><div class="storagePath" style="font-size:11px;overflow-wrap:anywhere"></div><button type="button" class="storagePreview">정리 가능 용량 확인</button> <button type="button" class="storageApply" hidden>계산 과정 정리</button><div class="storageStatus" role="status" style="margin-top:8px;font-size:11px;line-height:1.5"></div>';
 host.append(root);const preview=root.querySelector('.storagePreview'),apply=root.querySelector('.storageApply'),status=root.querySelector('.storageStatus');let token=null,disposed=false,busy=false;
 const size=n=>n>=1024**3?(n/1024**3).toFixed(2)+' GB':n>=1024**2?(n/1024**2).toFixed(1)+' MB':(n/1024).toFixed(1)+' KB';
 async function request(action,body){const response=await fetch('/cfbt/storage/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!response.headers.get('Content-Type')?.includes('application/json'))throw Error('앱 서버에서 사용할 수 있습니다.');const value=await response.json();if(!response.ok)throw Error(value.error||'정리 실패');return value;}
 async function run(action){if(busy||disposed)return;busy=true;preview.disabled=true;apply.disabled=true;status.textContent=action==='preview'?'완료된 계산의 정리 가능 용량 확인 중…':'계산 과정 정리 중…';status.className='storageStatus status-busy';
  try{const v=await request(action,action==='preview'?{}:{token});if(disposed)return;
   if(action==='preview'){token=v.token;root.querySelector('.storagePath').textContent='새 계산 저장 위치: '+v.data_path;apply.hidden=!v.files;apply.textContent='계산 과정 정리 · '+size(v.bytes);status.textContent=`확보 가능 ${size(v.bytes)} · ${v.calculations}건 / ${v.files}파일. 실행 중·미완료·보존 검증 불가 ${v.skipped}건 제외. 원시 출력과 상세 로그는 정리됩니다.`;}
   else{token=null;apply.hidden=true;status.textContent=`${size(v.bytes)} 정리 완료 · ${v.files}파일${v.errors.length?' · 삭제하지 못한 파일 '+v.errors.length+'개':''}. 입력과 최종 결과는 유지됩니다.`;}
   status.className='storageStatus status-ok';
  }catch(e){token=null;apply.hidden=true;status.className='storageStatus status-error';status.textContent=e.message;}finally{busy=false;preview.disabled=false;apply.disabled=false;}
 }
 const inspect=()=>run('preview'),clean=()=>run('cleanup');preview.addEventListener('click',inspect);apply.addEventListener('click',clean);
 return {dispose(){disposed=true;preview.removeEventListener('click',inspect);apply.removeEventListener('click',clean);root.remove();}};
}
