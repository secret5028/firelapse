from pathlib import Path
s=Path('work/check_shortest.mjs').read_text(encoding='utf-8')
s+='''
for(const id of ['B','C']){ctx.window.fireViewer.showBasement(id);assert.equal(ctx.window.fireViewer.state.mode,'basement');assert(ctx.window.fireViewer.basementGroups[id].visible);assert(!vm.runInContext('model.visible||site.visible||routesGroup.visible',ctx));const bb=ctx.window.fireViewer.basementGroups[id].children.filter(o=>o.isMesh&&o.userData.info);assert(bb.length===5);for(const o of bb){o.geometry.computeBoundingBox();assert(o.position.y+o.geometry.boundingBox.max.y<0)}assert.equal(get('gradeNote').style.display,'block');}
ctx.window.fireViewer.setMode('detail');assert(Object.values(ctx.window.fireViewer.basementGroups).every(g=>!g.visible));ctx.window.fireViewer.setFloor('1');assert(vm.runInContext('floorGroups[0].visible&&!floorGroups[1].visible',ctx));assert(!ctx.window.fireViewer.basementGroups.D);assert(get('floorDock').children.length>0);
console.log('PASS persistent floor dock, single-floor isolation, B/C basements below grade, no invented D basement, hidden basement routes.');
'''
Path('work/check_basement.mjs').write_text(s,encoding='utf-8')
