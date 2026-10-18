from pathlib import Path
s=Path('work/check_shortest.mjs').read_text(encoding='utf-8');s=s[:s.index('assert(ctx.window.fireViewer.ready)')]
s+="""
console.log(ctx.window.fireViewer.state);
for(const entrance of ['west','east']){
console.log(entrance,ctx.candidatesForEntrance(entrance));
const start=entrance==='west'?{x:.7,z:10.5}:{x:30.2,z:14.5};
for(const side of ['west','east']){const sp=ctx.stairPoints(side),end=ctx.roomEntry(side,ctx.window.fireViewer.state.target,entrance);console.log(side,'startblocked',ctx.blocked(start.x,start.z,1),'endblocked',ctx.blocked(end.x,end.z,2),'leg1',!!ctx.pathfind(start,sp[0],1),'leg2',!!ctx.pathfind(sp.at(-1),end,2),sp[0],sp.at(-1));}}
"""
Path('work/diagnose.mjs').write_text(s,encoding='utf-8')
