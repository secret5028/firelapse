# -*- coding: utf-8 -*-
"""경량 해석 결과를 CAD3D 뷰어에 입힘: building.json + <층>_fire_mc.json → building_fire.html"""
import json, sys, os
def main(bjson, mcjson, out):
    B = json.load(open(bjson, encoding='utf-8')); F = json.load(open(mcjson, encoding='utf-8'))
    F.pop('runs', None)
    html = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'viewer_template.html'), encoding='utf-8').read()
    html = html.replace('/*__DATA__*/null', json.dumps(B, ensure_ascii=False)).replace('/*__FIRE__*/null', json.dumps(F, ensure_ascii=False))
    open(out, 'w', encoding='utf-8').write(html)
if __name__ == '__main__':
    main(*sys.argv[1:4])
