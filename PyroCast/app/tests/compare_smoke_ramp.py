"""Compare browser-exported fixed-clock render buffers and uniform diagnostics."""
import json
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'simulation/results/ui_refactor_stageB2_20261028'

def pixels(name):
    return np.asarray(Image.open(OUT/name).convert('RGBA')).astype(int)

rows=[]
for name in ('S09-1420','S09-1800','S06-890','all-core'):
    a=pixels(name+'-before-3d.png');b=pixels(name+'-after-3d.png')
    d=np.abs(a-b);mask=np.any(d>0,axis=2);y,x=np.nonzero(mask)
    rows.append(dict(scene=name,changed_pixels=int(mask.sum()),max_channel_difference=int(d.max()),
                     size=list(a.shape),bbox=[int(x.min()),int(y.min()),int(x.max()),int(y.max())] if len(x) else None))
    Image.fromarray(np.where(mask[:,:,None],[255,0,255],[0,0,0]).astype('uint8')).save(OUT/(name+'-diff.png'))
(OUT/'pixel-comparison.json').write_text(json.dumps(rows,indent=2)+'\n','utf-8')
assert all(r['changed_pixels']==0 for r in rows),rows
modes=json.loads((OUT/'modes.json').read_text('utf-8'))
for r in modes:
    assert all(s['ramp']==(1 if r['ramp']=='neutral' else 0) for s in r['smoke'])
    assert [{k:v for k,v in s.items() if k!='ramp'} for s in r['smoke']]==[{k:v for k,v in s.items() if k!='ramp'} for s in modes[0]['smoke']]
    assert r['other']==modes[0]['other'] and r['hud']==modes[0]['hud'] and np.allclose(r['camera'],modes[0]['camera'],rtol=0,atol=1e-9)
a=pixels('S09-1420-before-3d.png');b=pixels('S09-1420-neutral-3d.png');c=pixels('S09-1420-roundtrip-3d.png')
assert np.array_equal(a,c)
assert np.array_equal(a,pixels('S09-1420-current-3d.png'))
report=dict(default_roundtrip_changed_pixels=0,neutral_changed_pixels=int(np.any(a!=b,axis=2).sum()),
            only_smoke_ramp_uniform_changed=True,smoke_temperature_unchanged=True,optical_density_unchanged=True,flame_and_gas_uniforms_unchanged=True,hud_unchanged=True)
assert report['neutral_changed_pixels']>0
(OUT/'option-verification.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
print(json.dumps(dict(defaults=rows,options=report)))
