"""Plot saved isolation evidence only; no simulation imports."""
from pathlib import Path
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'simulation/results/lite_l1c_20261025'
def load(path):
    with path.open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
    return {k:np.array([float(r[k]) for r in rows]) for k in rows[0]}
fig,axes=plt.subplots(2,3,figsize=(13,7.5),constrained_layout=True)
for i,name in enumerate(('B2','B3')):
    old=load(ROOT/f'simulation/results/lite_l1b_20261025/isolation/{name}/overlay.csv')
    new=load(OUT/f'radiation_on/isolation/{name}/overlay.csv')
    for j,(key,label) in enumerate([('ULT_1','Upper temperature (C)'),('HRR_1','Actual HRR (kW)'),('HGT_1','Interface height (m)')]):
        ax=axes[i,j];t=old['time_s']/60
        ax.plot(t,old['native_'+key],label='Stored CFAST',color='#164c82',lw=2.2)
        ax.plot(t,old['lite_'+key],label='Lite radiation OFF',color='#d77b12',ls='--')
        ax.plot(t,new['lite_'+key],label='Lite radiation ON (rejected)',color='#9b3c9b',ls='-.')
        ax.set(title=name+' / R1',xlabel='Time (min)',ylabel=label,xlim=(0,20));ax.grid(alpha=.2)
        if i==0:ax.legend(fontsize=8)
fig.suptitle('Section 1.3: isolated primary fire / grey-gas radiation comparison\nSame supply and shared inputs; no secondary fires; no new CFAST run',fontsize=12)
fig.savefig(OUT/'isolation-before-after.png',dpi=160);fig.savefig(OUT/'isolation-before-after.pdf');plt.close(fig)
print(OUT/'isolation-before-after.png')
