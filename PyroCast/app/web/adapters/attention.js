// Presentation ranking only. Never substitute legacy smoke counts for indices.
export function attentionRanking(comparison,saved){
 const key=r=>[-r.burning_room_count,-r.attention_room_count,r.first_FO_s??Infinity];
 const compare=(a,b)=>{const x=key(a),y=key(b);for(let i=0;i<x.length;i++)if(x[i]!==y[i])return x[i]<y[i]?-1:1;return 0;};
 const rows=(comparison?.rows||[]).map(row=>{const pair=(row.state_results||[]).map(c=>{const identity=[c.room,c.state,c.result_folder,c.times?.total_s,c.burning_room_count,c.first_FO_s,c.safe_end_s];const found=saved.records.find(s=>s.identity.every((v,i)=>v===identity[i]));return {...c,attention_room_count:found?.attention_room_count??null,index_complete:!!(found?.complete&&!found.unknown_rooms.length)};});
  const valid=pair.length===2&&pair.every(c=>c.index_complete&&c.complete);if(!valid)return {...row,rank2:null,attention_room_count:null,index_complete:false};
  const worst=[...pair].sort(compare)[0];return {...row,rank2:null,index_complete:true,attention_room_count:worst.attention_room_count,burning_room_count:worst.burning_room_count,first_FO_s:worst.first_FO_s,worst_state:worst.state};
 });
 const good=rows.filter(r=>r.index_complete).sort((a,b)=>compare(a,b)||a.room.localeCompare(b.room));let rank=0;for(let i=0;i<good.length;i++){if(i===0||compare(good[i-1],good[i]))rank=i+1;good[i].rank2=rank;}
 return [...good,...rows.filter(r=>!r.index_complete)];
}
