from pathlib import Path
p=Path('work/folder_review.html');s=p.read_text(encoding='utf-8')
s=s.replace('<div class="bar"><button', '<div class="bar"><select id="viewFloor" aria-label="3D 층 선택"><option value="all">전체 층</option></select><button',1)
s=s.replace("const chosen=state.pages.filter(p=>p.included&&p.scale&&p.shapes.length),names=", "const valid=state.pages.filter(p=>p.included&&p.scale&&p.shapes.length),selector=$('viewFloor'),selected=selector.value||'all';selector.innerHTML='';const allOption=document.createElement('option');allOption.value='all';allOption.textContent='전체 층';selector.appendChild(allOption);for(const p of valid){const option=document.createElement('option');option.value=p.building+'|'+p.floor;option.textContent=p.building+' · '+(p.floor<0?'B'+(-p.floor):p.floor+'F');selector.appendChild(option)}selector.value=[...selector.options].some(o=>o.value===selected)?selected:'all';const chosen=valid.filter(p=>selector.value==='all'||p.building+'|'+p.floor===selector.value),names=")
s=s.replace("$('mode2d').onclick=", "$('viewFloor').onchange=()=>{if(mode==='3d')view3d?.build()};$('mode2d').onclick=")
s=s.replace("!Number.isFinite(p.height)||", "!Number.isInteger(p.floor)||p.floor===0||!Number.isFinite(p.height)||")
p.write_text(s,encoding='utf-8')
p=Path('outputs/소방공간뷰-사용안내.txt');s=p.read_text(encoding='utf-8');s+='\n층 보기\n- 화면 오른쪽의 층 버튼은 항상 표시됩니다. D동 1F·2F는 해당 층만 표시합니다.\n- B·C동 선택 후 B1 버튼으로 지하층 외곽을 볼 수 있습니다. 지면 0m·바닥 -3.6m는 임시 기준입니다. 지하 내부·지상 연결 경로는 미구현입니다.\n- 새 도면 보정 화면에서는 지하 1층을 -1로 입력합니다. 3D 층 선택 목록에서도 층을 따로 볼 수 있습니다.\n';p.write_text(s,encoding='utf-8')
print('Generic editor floor selection and negative-floor validation added.')
