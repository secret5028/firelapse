// Confirmed next-run inputs are separate from the currently playing result.
export function fixedOpeningsFor(building,review){
 const valid=fixed=>fixed?.building_sha256===building?.source_hash&&fixed?.states;
 const fixed=review?.doors?.fixed_state;
 if(valid(fixed))return fixed;
 const saved=review?.playbackOpenings;
 return valid(saved)?saved:null;
}
