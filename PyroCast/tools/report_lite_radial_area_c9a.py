"""Postprocess saved C9a only: comparison table and three-cell temperature PNG."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'simulation/results/ui_C9a_20261102'
def read(p):return json.loads(p.read_text('utf-8'))


def main():
    sources=[('legacy',ROOT/'simulation/results/lite_v8_mc_R2_10_20261026/S09'),
             ('radial',ROOT/'simulation/results/ui_C9_20261102/radial'),
             ('radial_area',OUT/'radial_area')]
    comparison=[];series=None
    for mode,path in sources:
        summary=read(path/'summary.json');pb=read(path/'playback.json')
        cells=[]
        for row in pb['rooms']:
            if row['original_room']!='CAD_3F_R2':continue
            v=pb['solvers'][row['solver_id']];t=pb['time_s'];imax=int(np.argmax(v['Tu']))
            cells.append(dict(id=row['solver_id'],area_m2=row['area_m2'],max_upper_C=max(v['Tu']),
                              max_at_s=t[imax],upper_1420_C=v['Tu'][t.index(1420)],peak_HRR_kW=max(v['Qsolid_kW'])))
        comparison.append(dict(mode=mode,times=summary['times'],burning_rooms=summary['burning_original_rooms'],cells=cells,events=pb['events']))
        if mode=='radial_area':series=pb
    info=read(OUT/'radial_area/rule_manifest.json')['cells']['radial']
    plt.rcParams['font.family']='Malgun Gothic';plt.rcParams['axes.unicode_minus']=False
    fig,ax=plt.subplots(figsize=(10,5),layout='constrained')
    for label,color,cell in zip(('화점','중간','외곽'),('#de493e','#e59627','#277caf'),info['cells']):
        values=series['solvers'][cell['id']]['Tu']
        ax.plot(np.array(series['time_s'])/60,values,color=color,lw=2,label=f'{label} · 최고 {max(values):.1f} ℃')
    ax.axhline(300,color='#888888',ls='--',lw=1,label='셀 전이 기준 300 ℃')
    ax.set(xlabel='시뮬레이션 시간 (분)',ylabel='상층 온도 (℃)',xlim=(0,60),title='S09 R2 · radial_area · 동일 목표 면적 104.117㎡')
    ax.grid(alpha=.2);ax.legend();fig.savefig(OUT/'radial-area-upper-temperature.png',dpi=170);plt.close(fig)
    result=dict(rows=comparison,geometry=info,gate=read(OUT/'radial_area/summary.json')['gate'],
                limits=['legacy/radial are archived runtimes, not rerun controls','CFAST aggressive reference ends at 2850s and differs from S09 opening inputs'])
    (OUT/'comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(comparison,ensure_ascii=False))

if __name__=='__main__':main()
