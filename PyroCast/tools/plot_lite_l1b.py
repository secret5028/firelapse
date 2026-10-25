"""Read-only overlay plots from normalized CSV, never runs a simulation."""
from pathlib import Path
import csv
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'simulation/results/lite_l1b_20261025'
fig,axes=plt.subplots(2,3,figsize=(13,7.5),constrained_layout=True)
panels=[('ULT_1','Upper-layer temperature (C)'),('HRR_1','Actual source HRR (kW)'),('HGT_1','Layer interface height (m)')]
for i,name in enumerate(('B2','B3')):
    with (OUT/f'isolation/{name}/overlay.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
    data={key:np.array([float(row[key]) for row in rows]) for key in rows[0]}
    for j,(key,label) in enumerate(panels):
        ax=axes[i,j]
        ax.plot(data['time_s']/60,data['native_'+key],label='Stored CFAST: primary only',color='#164c82',lw=2.3)
        ax.plot(data['time_s']/60,data['lite_'+key],label='Lite L1b: primary only',color='#d77b12',lw=1.8,ls='--')
        ax.set(title=f'{name} / R1',xlabel='Time (min)',ylabel=label,xlim=(0,20))
        ax.grid(alpha=.2)
        if j==0:ax.axhline(600,color='#b43434',lw=.7,ls=':',label='600 C (no spread in isolation)')
        if i==0:ax.legend(fontsize=7,loc='best')
fig.suptitle('Isolated primary fire: shared inputs, Cd=0.70, native mass-fraction LOL\nNo secondary fires; native 5 s data interpolated to lite 10 s output; no new CFAST run',fontsize=12)
fig.savefig(OUT/'isolation-overlay.png',dpi=160)
fig.savefig(OUT/'isolation-overlay.pdf')
plt.close(fig)
print(OUT/'isolation-overlay.png')
