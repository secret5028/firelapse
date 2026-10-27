from pathlib import Path
import sys,json
import numpy as np
from PIL import Image
root=Path(sys.argv[2]) if len(sys.argv)>2 else Path(__file__).resolve().parents[2]/'simulation/results/ui_refactor_stage3_switchover_20261027'
name=sys.argv[1]
a=np.asarray(Image.open(root/(name+'-legacy.png')).convert('RGB')).astype(int)
b=np.asarray(Image.open(root/(name+'-modern.png')).convert('RGB')).astype(int)
if a.shape!=b.shape:raise ValueError('Screenshot dimensions differ')
d=np.abs(a-b);mask=np.any(d>0,axis=2)
Image.fromarray(np.where(mask[:,:,None],np.array([255,0,255]),0).astype('uint8')).save(root/(name+'-diff.png'))
y,x=np.nonzero(mask)
print(json.dumps({'changed_pixels':int(mask.sum()),'total_pixels':int(mask.size),'max_channel_difference':int(d.max()),'bbox_inclusive':[int(x.min()),int(y.min()),int(x.max()),int(y.max())] if len(x) else None}))
