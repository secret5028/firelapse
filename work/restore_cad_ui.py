from pathlib import Path
import shutil,sys

root=Path(__file__).resolve().parent
engine=root/'cad-web/cad_engine'
template=engine/'integrated_viewer.html'
backup=root/'cad-ui-before-v12.html'
if not backup.exists(): shutil.copy2(template,backup)
s=backup.read_text('utf8')
adapter=(root/'cad_ui_adapter.js').read_text('utf8')
old=(root/'legacy/floor-details.js').read_text('utf8')
references=old[old.index('function addSceneReferences('):]
legacy=(root/'legacy')
ops=(legacy/'operations-ui.js').read_text('utf8')
start=ops.index(' function point(e,groundOnly)')
end=ops.index(' function place(e)',start)
ops=ops[:start]+" function point(e,groundOnly){return cadPick(e,groundOnly)||(action==='fire'?null:cadPick(e,true))}\n"+ops[end:]
# Imported JSON must refresh selectors, not just scene meshes.
ops=ops.replace('window.operationsRefresh=()=>render();','window.operationsRefresh=()=>refresh();')
ops=ops.replace("const y=p.elevation??(p.floor-1)*p.height;", "const y=p.elevation??(p.floor-1)*p.height;")
chunks=[references,adapter,(legacy/'elevator-display.js').read_text('utf8'),(root/'cad_semantic_display.js').read_text('utf8'),
 (root/'cad_legacy_bridge.js').read_text('utf8'),(legacy/'auto-route.js').read_text('utf8'),
 (root/'cad_route_adapter.js').read_text('utf8'),ops]
for name in ['core','ui','view']:
    code=(legacy/f'hydraulic-{name}.js').read_text('utf8')
    if name=='ui':code=code.replace('try {const s=localStorage.getItem(key);','try {const s=window.CAD_OFFLINE?null:localStorage.getItem(key);')
    chunks.append(code)
chunks.append((root/'cad_legacy_finish.js').read_text('utf8'))
chunks.append((root/'cad_core_emphasis.js').read_text('utf-8-sig'))
chunks.append((root/'cad_cfast_multifloor_overlay.js').read_text('utf-8-sig'))
chunks.append((root/'cad_cfast_realistic.js').read_text('utf-8-sig'))
chunks.append((root/'cad_cfast_combustion.js').read_text('utf-8-sig'))
chunks.append((root/'cad_cfast_plume_math.js').read_text('utf-8-sig'))
chunks.append((root/'cad_cfast_plume_display.js').read_text('utf-8-sig'))
chunks.append((root/'cad_cfast_ceiling_display.js').read_text('utf-8-sig'))
chunks.append((root/'cad_html_export.js').read_text('utf-8-sig'))
s=s.replace('</script></body></html>','\n'.join(chunks)+'\n</script></body></html>')
s=s.replace('x.visible&&x.parent.parent.visible','visibleByName(x)').replace('x.visible&&x.parent.visible','visibleByName(x)').replace('.find(h=>h.object.visible)', '.find(h=>visibleByName(h.object))')
template.write_text(s,'utf8')
out=root.parent/'outputs'/(sys.argv[1] if len(sys.argv)>1 else 'CAD-수직동선완화-v15')
out.mkdir(exist_ok=True)
shutil.copy2(template,out/'model.html')
print(template)
