// Confirmed next-run inputs are separate from the currently playing result.
export function openingFraction(state){
 if(!state)return null;
 if(Number.isFinite(state.effective_fraction))return Math.max(0,Math.min(1,state.effective_fraction));
 return typeof state.open==='boolean'?(state.open?1:0):null;
}
export function fixedInputFor(review,room){
 const doors=review?.doors;
 return doors?.fixed_by_room?doors.fixed_by_room[room]:doors?.fixed_state;
}
export function fixedOpeningsFor(building,review,room){
 const valid=fixed=>fixed?.building_sha256===building?.source_hash&&fixed?.states;
 const saved=review?.playbackOpenings;
 if(review?.doors?.fixed_by_room&&valid(saved))return saved;
 const fixed=fixedInputFor(review,room);
 if(valid(fixed))return fixed;
 return valid(saved)?saved:null;
}
