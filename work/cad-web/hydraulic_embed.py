from pathlib import Path
import json,re

def embed_hydraulics(content,base,building_id,name):
    content=re.sub(r'<script id="hydraulic-scripts">[\s\S]*?</script>', '', content)
    if 'const cv=renderer.domElement;' in content and 'installHydraulicView?.(T,scene,camera,renderer.domElement)' not in content:
        content=content.replace('const cv=renderer.domElement;', 'window.installHydraulicView?.(T,scene,camera,renderer.domElement);const cv=renderer.domElement;')
    base=Path(base)
    cfg=json.dumps({'buildingId':building_id,'name':name},ensure_ascii=False).replace('</','<\\/')
    code='window.HYDRAULIC_CONFIG='+cfg+';\n'+'\n'.join((base/f'hydraulic-{n}.js').read_text('utf-8') for n in ['core','ui','view'])
    tag='<script id="hydraulic-scripts">'+code.replace('</script','<\\/script')+'</script>'
    return content.replace('</body>',tag+'</body>') if '</body>' in content else content+tag
