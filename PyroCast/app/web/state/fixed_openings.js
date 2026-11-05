// Confirmed next-run inputs are separate from the currently playing result.
export function openingFraction(state){
 if(!state)return null;
 if(Number.isFinite(state.effective_fraction))return Math.max(0,Math.min(1,state.effective_fraction));
 return typeof state.open==='boolean'?(state.open?1:0):null;
}
export function fixedOpeningsFor(building,review){
 const valid=fixed=>fixed?.building_sha256===building?.source_hash&&fixed?.states;
 const fixed=review?.doors?.fixed_state;
 if(valid(fixed))return fixed;
 const saved=review?.playbackOpenings;
 return valid(saved)?saved:null;
}
