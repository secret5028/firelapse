"""Read-only 20-sample overview."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'simulation/results/lite_l1d_20261025'
def read(p):return json.loads(p.read_text('utf-8'))
plan=read(OUT/'sampling-plan.json');rows=[read(OUT/'samples'/i/'summary.json') for i in plan['sample_ids']]
fig,ax=plt.subplots(3,1,figsize=(14,9),constrained_layout=True,sharex=True)
x=np.arange(len(rows));labels=[s['sample_id']+('*' if s['kind']!='random' else '') for s in rows]
colors=['#b33c3c' if not s['complete'] else '#d78b25' if not s.get('balance_diagnostic',{}).get('passed') else '#327b69' for s in rows]
ax[0].bar(x,[s['times']['total_s'] for s in rows],color=colors)
ax[0].set(ylabel='Wall time (s)',title='Green: completed + output diagnostic pass / Orange: diagnostic exceeded / Red: incomplete or failed')
for i,(key,color) in enumerate([('FO','#df9926'),('FGI','#8054bc'),('backdraft','#af4058')]):
    values=[s.get('phenomena',{}).get(key,{}).get('ever_room_count',0) if s['complete'] else np.nan for s in rows]
    ax[1].bar(x+(i-1)*.24,values,width=.23,label=key,color=color)
ax[1].set(ylabel='Rooms ever meeting condition',title='Completed samples only; blanks are not zero risk; rollover is not evaluated')
ax[1].legend(loc='upper right',ncol=3)
ax[2].bar(x-.18,[len(s.get('burning_original_rooms',[])) if s['complete'] else np.nan for s in rows],width=.35,label='Burning rooms (actual HRR > 0)',color='#cc5d2e')
ax[2].bar(x+.18,[s.get('boundary_room_count',0) if s['complete'] else np.nan for s in rows],width=.35,label='Boundary rooms (peak 600 +/- 30 C)',color='#4176a3')
ax[2].set(ylabel='Original rooms',xlabel='Sample (* mandatory scenario, excluded from random-sample fractions)')
ax[2].legend(loc='upper right',ncol=2);ax[2].set_xticks(x,labels)
for a in ax:a.grid(axis='y',alpha=.2);a.set_axisbelow(True)
fig.suptitle('L1 exploration pilot / 3F, 60 minutes, seed 20261025, 4 workers\nInput-sample condition frequencies are not real-world event probabilities',fontsize=13)
fig.savefig(OUT/'mc20-overview.png',dpi=160);fig.savefig(OUT/'mc20-overview.pdf');plt.close(fig)
print(OUT/'mc20-overview.png')
