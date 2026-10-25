"""Publish only saved MC results to the existing local viewer catalog."""
import json
from pathlib import Path
from report_lite_mc_v8_r2 import main as report

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'simulation/results/lite_v8_mc_R2_10_20261026'
def read(p):return json.loads(p.read_text('utf-8'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    a=read(OUT/'aggregate.json');rows=read(OUT/'summaries.json')
    if len(rows)!=10 or not a['code_unchanged_during_batch']:raise ValueError('Incomplete batch or changed calculation code')
    for s in rows:
        p=OUT/s['sample_id']/'summary.json';old=read(p)
        if old.get('failure')=="KeyError: 'all_met'":save(p.with_name('summary-before-postprocess-fix.json'),old)
        save(p,s)
    save(OUT/'progress.json',dict(state='completed',completed=10,total=10,aggregate=a))
    cfgpath=ROOT/'simulation/config/lite-viewer.json';c=read(cfgpath);by={s['sample_id']:s for s in rows}
    raw=read(ROOT/'simulation/results/lite_v8_stage4_R2_20261026/input.json')
    labels={r['id']:r.get('approved_fuel_class',{}).get('label') for r in raw['rooms']}
    kinds={'all_fire_doors_open':'방화문 모두 열림','all_openings_closed':'모두 닫힘','random':'무작위'}
    for v in c['cases']:
        pbpath=Path(v['path']);pb=read(pbpath);pb['case_id']=v['id']
        for room in pb['rooms']:
            label=labels.get(room['original_room'])
            if label:room['display_name']=label+' (승인 용도)'
        save(pbpath,pb)
        if v['id'] not in by:continue
        s=by[v['id']]
        if not s['complete']:raise ValueError('Incomplete sample included in operational catalog')
        v['label']=f"R2 {v['id']} · {kinds[s['kind']]} · 연소 {len(s['burning_original_rooms'])} / 연기 위험 {len(s['smoke_risk_rooms'])}실"
    c['mc_summary']=dict(completed=a['completed'],wall_s=a['wall_s'],rates=a['condition_sample_rates_random_only'],
        rows=[dict(id=s['sample_id'],complete=s['complete'],burning=len(s.get('burning_original_rooms',[])),smoke_risk=len(s.get('smoke_risk_rooms',[]))) for s in rows])
    c['progress_text']=f"R2 MC10 직렬 종료 · 완주 {a['completed']}/10 · 실패/미완료 {a['failed_or_incomplete']} · 실제 발생확률 아님"
    complete=[s for s in rows if s['complete']]
    if complete:
        best=sorted(complete,key=lambda s:(-len(s['burning_original_rooms']),-len(s['smoke_risk_rooms']),s['phenomena']['FO']['first_s'] if s['phenomena']['FO']['first_s'] is not None else float('inf'),s['sample_id']))[0]
        c['active_path']=str(OUT/best['sample_id']/'playback.json')
        c['display_default_basis']='completed sample: burning room count, smoke-risk room count, earlier FO; not a universal worst-case claim'
        c['active_case_id']=best['sample_id']
    save(cfgpath,c)
    p=ROOT/'simulation/config/lite-screening-selection.json';selection=read(p);selection['mc_room']='CAD_3F_R2';save(p,selection)
    report()
    if complete:
        p=ROOT/'specs/간략엔진-v8-R2-MC10-20261026.txt'
        with p.open('a',encoding='utf-8') as f:
            f.write(f"\n3D 기본 사례: {best['sample_id']} / 실제 고체 연소 {len(best['burning_original_rooms'])}실. 선택 기준은 연소 실 수 → 연기 위험 실 수 → 최초 FO가 빠른 순. 모든 위험 유형의 보편적 최악을 의미하지 않는다.\n")
    print(json.dumps(c['mc_summary'],ensure_ascii=False))

if __name__=='__main__':main()
