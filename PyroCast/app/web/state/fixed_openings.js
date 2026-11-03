// Confirmed next-run inputs are separate from the currently playing result.
export function fixedOpeningsFor(building,review){
 const fixed=review?.doors?.fixed_state;
 return fixed?.building_sha256===building?.source_hash&&fixed?.states?fixed:null;
}
