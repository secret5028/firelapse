// Native compartment DJET + expected/actual HRR diagnostics. Jet geometry is illustrative.
function createCfastCombustion({data,roots,rows,centre,panel,readout,focus}){
 const d=data.combustion;if(!d)return {update(){},animate(){},stats(){return {available:false}}};
 const fmt=t=>`${String(Math.floor(t/60)).padStart(2,'0')}:${String(Math.floor(t%60)).padStart(2,'0')}`;
 const box=document.createElement('details');box.id='cfCombustion';box.open=true;
 box.innerHTML='<summary>개구부 연소 · 환기지배 전환</summary><div id="cfRegime" style="white-space:pre-line;line-height:1.7;margin:7px 0"></div><div id="cfJetReadout"></div><div id="cfCombustionEvents"></div><small>개구부 연소: 구획별 계산값 · 화염: 기존 화점의 크기·패턴 변화<br>환기지배 표시는 산소제한 진단이며, NIST의 별도 판정값은 아닙니다.</small>';
 readout.after(box);
 const regime=box.querySelector('#cfRegime'),jetText=box.querySelector('#cfJetReadout'),events=box.querySelector('#cfCombustionEvents');
 const note=document.createElement('p');note.textContent=d.criterion.description+' · 5초 간격 결과에서 시작 시점과 10초 지속 확인 시점을 구분합니다. 미착화 실의 가구 연소와 개구부 가스 연소는 별개입니다.';panel.querySelector('#cfAssumptions').append(note);
 for(const r of d.rooms)for(const e of r.intervals){const b=document.createElement('button');b.className='cfArrival';b.textContent=`${r.solver_key} · 산소제한 ${fmt(e.onset)} → ${e.end===null?'계산 끝':fmt(e.end)} (확인 ${fmt(e.confirmed)})`;b.onclick=()=>focus(r.room_keys[0],e.confirmed);events.append(b)}
 const peak=d.jets.reduce((best,j)=>!best||j.peak_kW>best.peak_kW?j:best,null);
 if(peak){const b=document.createElement('button');b.id='cfJetPeak';b.textContent=`개구부 연소 최대 보기 · ${fmt(peak.peak_time)}`;b.onclick=()=>focus(peak.anchor?.room_key||peak.room_keys[0],peak.peak_time,peak.anchor);events.prepend(b)}
 const jetObjects=[];
 for(const j of d.jets){const r=rows.find(r=>r.key===(j.anchor?.room_key||j.room_keys[0]));if(!r)continue;
  const root=roots.get(r.floor),c=centre(r),tagEl=document.createElement('div');tagEl.className='cfTag';tagEl.style.borderColor='#ff953b';
  const tag=new CSS2DObject(tagEl);tag.position.set(c[0],c[1],Math.min(r.height-.3,2.5));tag.visible=false;root.add(tag);
  const ring=new THREE.Mesh(new THREE.RingGeometry(.7,1.,40),new THREE.MeshBasicMaterial({color:0xff7028,transparent:true,opacity:.9,side:THREE.DoubleSide,depthTest:false,depthWrite:false}));ring.renderOrder=21;ring.position.set(c[0],c[1],.15);ring.visible=false;ring.raycast=()=>{};root.add(ring);
  const ribbons=[];
  jetObjects.push({j,r,tag,tagEl,ring,ribbons,q:0});
 }
 let state=null,current={};
 const value=(a,t)=>{const i=Math.min(a.length-1,Math.floor(t/d.step));return a[i]}; // hold native samples, no early onset via interpolation
 return {
  update(s){state=s;const r=rows.find(r=>r.key===s.selected),diag=d.rooms.find(x=>x.solver_key===r?.solver_key),i=Math.min(data.hrr.length-1,Math.floor(s.time/d.step));
   let text='선택 구획: 등록 화원 없음 · 연료/환기 지배 판정 대상 아님';
   if(diag){const e=diag.expected_kW[i],a=diag.actual_kW[i],interval=diag.intervals.find(x=>s.time>=x.confirmed&&(x.end===null||s.time<x.end));
    const status=e<=1?'등록 가연물 연소 없음/미미 (개구부 가스 연소는 별도)':interval?'환기지배 · 산소제한 지속':diag.limited[i]?'산소제한 징후 · 지속 확인 전':'연료지배 · 유의한 산소제한 없음';
    text=`${diag.solver_key} · ${status}\n예상 ${e.toFixed(0)} / 실제 ${a.toFixed(0)} kW · 제한 ${Math.max(0,e-a).toFixed(0)} kW\n산소 상부 ${diag.upper_o2_percent[i].toFixed(1)}% / 하부 ${diag.lower_o2_percent[i].toFixed(1)}% (몰분율)\n상부 미연소 연료 ${diag.unburned_upper_percent[i].toFixed(3)}%`;
    if(interval)text+=`\n시작 ${fmt(interval.onset)} · 지속 확인 ${fmt(interval.confirmed)}`;
   }regime.textContent=text;jetText.replaceChildren();let total=0;
   for(const e of jetObjects){const q=value(e.j.hrr,s.time);e.q=q;total+=q;const active=s.enabled&&q>.01;e.ring.visible=active;e.tag.visible=active;
    e.tagEl.textContent=`개구부 가스 연소\n${e.j.solver_key} 합계 ${q.toFixed(0)} kW`;e.tagEl.style.visibility=e.tag.visible?'visible':'hidden';
    for(const rib of e.ribbons)rib.mesh.visible=active&&s.realView;
    const p=document.createElement('p');p.textContent=`${e.j.solver_key} 개구부 연소 ${q.toFixed(1)} kW · 첫 표시 ${fmt(e.j.onset)}`;jetText.append(p);
   }
   current={available:true,regime:text,jetTotal_kW:total,realView:s.realView,jets:jetObjects.filter(e=>e.q>.01).map(e=>({room:e.j.solver_key,kW:e.q,anchor:e.j.anchor?.vent_id,illustrative:false})),ribbons:jetObjects.reduce((n,e)=>n+e.ribbons.filter(r=>r.mesh.visible).length,0)};
  },
  animate(){},
  stats(){return current}
 };
}
