"""Evidence checks for saved-data-only smoke/door-jet display changes."""
from pathlib import Path
import json
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reviews/smoke-doorjet-20261103'
def read(p):return json.loads(p.read_text('utf-8'))
def difference(a,b,name):
    x=np.asarray(Image.open(a).convert('RGB'));y=np.asarray(Image.open(b).convert('RGB'))
    # 3D viewport only; header, timeline and panel excluded. HUD overlays remain.
    delta=np.abs(x[50:663,:940].astype(int)-y[50:663,:940].astype(int));changed=np.any(delta>0,axis=2)
    yy,xx=np.where(changed);threshold=np.any(delta>8,axis=2)
    result={'pixels':int(changed.sum()),'pixels_delta_gt_8':int(threshold.sum()),'total_pixels':changed.size,
        'max_channel_difference':int(delta.max()),'bbox':[int(xx.min()),int(yy.min()+50),int(xx.max()),int(yy.max()+50)]}
    Image.fromarray(np.where(changed[...,None],np.array([255,0,80]),0).astype('uint8')).save(OUT/(name+'-diff.png'))
    return result
def main():
    before=read(OUT/'before-P1-playback.json');after=read(ROOT/'data/wando-coldstore/P1-playback.json')
    for key in ['solvers','time_s','native_time_s','rooms','opening_states']:assert before[key]==after[key],key
    for a,b in zip(before['fires'],after['fires']):assert a=={k:v for k,v in b.items() if k!='visual_mode'}
    max_residual=0.
    for room,s in after['solvers'].items():
        allocated=np.sum([d['HRR_kW'] for d in after['door_jet']['directions'] if d['to']==room],axis=0)
        max_residual=max(max_residual,float(np.max(abs(allocated-np.asarray(s['Qvent_kW'])))))
    assert max_residual<1e-6
    old=read(OUT/'diagnostic.json');new=read(OUT/'after-diagnostic.json')
    for sample in ['at1325','slider150','at2100']:
        assert old[sample]['meshes']==new[sample]['meshes'],sample
    ref=read(ROOT/'simulation/results/ui_D1_20261103/wando-P1-2100-after.json')
    current=new['at2100']['meshes']
    for a,b in zip(ref['smoke'],current):
        assert a['position']==b['position'] and a['scale']==b['scale']
        for rk,uk in [('od','uOD'),('temp','uLayerTemp'),('opacity','uOpacity'),('amp','uNoiseAmp')]:assert a[rk]==b['uniform'][uk]
    shell_before=np.asarray(Image.open(OUT/'shell-before-2100.png').convert('RGB'))
    shell_after=np.asarray(Image.open(OUT/'after-2100.png').convert('RGB'))
    # Fixed smoke interior patch, away from glow, HUD, path and furniture.
    roi=(slice(300,340),slice(340,390))
    result={'physical_arrays_unchanged':True,'simulation_runs':0,'allocation_max_residual_kW':max_residual,
        'before_after_smoke_uniforms_equal':True,'D1_smoke_uniforms_equal':True,
        'render_order_only_ROI':[340,300,390,340],
        'render_order_only_RGB_mean_before':float(shell_before[roi].mean()),
        'render_order_only_RGB_mean_after':float(shell_after[roi].mean()),
        'D1_reference':difference(ROOT/'simulation/results/ui_D1_20261103/wando-P1-2100-after.jpg',OUT/'Wando-P1-2100-D1-view.png','D1'),
        'isolated_exterior_order':difference(OUT/'shell-before-2100.png',OUT/'after-2100.png','exterior-order')}
    (OUT/'checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
