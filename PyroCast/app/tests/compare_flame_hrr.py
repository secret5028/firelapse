"""Validate fixed-clock browser exports; no browser or solver is launched."""
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'simulation/results/ui_B3_hrr_20261028'
def pixels(name):return np.asarray(Image.open(OUT/name).convert('RGBA')).astype(int)
def difference(a,b):
    d=np.abs(pixels(a)-pixels(b));return dict(changed_pixels=int(np.any(d,axis=2).sum()),max_channel_difference=int(d.max()))
rows=[dict(scene=n,**difference(n+'-before-3d.png',n+'-after-3d.png')) for n in ('S09-1420','S09-1800','S06-890','all-core')]
assert all(r['changed_pixels']==0 for r in rows),rows
captures=json.loads((OUT/'captures.json').read_text('utf-8'))
assert len(captures)==7
for c in captures:
    if c['flameDisplay']!='hrr':continue
    visible=[f for f in c['flames'] if f['visible']]
    top=sorted(visible,key=lambda f:(-f['q'],f['id']))[:3]
    assert [l['id'] for l in c['lights'] if l['intensity']>0]==[f['id'] for f in top]
    assert len(c['lights'])==3
    for f in visible:
        area=min(f['cellArea'],f['q']/f['hrrpua'])
        assert math.isclose(f['scale'][0],2*math.sqrt(area/math.pi),rel_tol=1e-12)
        assert f['scale'][0]==f['scale'][1]
        assert f['scale'][2]>=.1
for view in ('oblique','top','R2-focus'):
    a,b=[next(c for c in captures if c['stem']==f'S09-1420-{mode}-{view}') for mode in ('growth','hrr')]
    assert a['hud']==b['hud'] and a['smoke']==b['smoke']
    assert np.allclose(a['camera'],b['camera'],rtol=0,atol=1e-9)
    assert [(f['q'],f['stage']) for f in a['flames']]==[(f['q'],f['stage']) for f in b['flames']]
roundtrip=difference('S09-1420-before-3d.png','S09-1420-growth-roundtrip-3d.png')
repeat=difference('S09-1420-hrr-oblique-3d.png','S09-1420-hrr-repeat-3d.png')
assert roundtrip['changed_pixels']==0,roundtrip
assert repeat['changed_pixels']==0,repeat
early=next(c for c in captures if c['time']==300)
report=dict(defaults=rows,roundtrip=roundtrip,hrr_repeat=repeat,top3_lights=True,diameters_match=True,
            smoke_hud_hrr_stage_unchanged=True,early_visible=[f for f in early['flames'] if f['visible']])
(OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
print(json.dumps(report,ensure_ascii=False))
