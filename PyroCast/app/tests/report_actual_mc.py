"""Read-only evidence for a real UI-started MC job. Never starts a simulation."""
import argparse,json,hashlib,statistics
from pathlib import Path


def read(p):return json.loads(p.read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def report(job,out):
    request=read(job/'request.json');progress=read(job/'progress.json');started=read(job/'started.json')
    if progress.get('state')!='completed':raise RuntimeError('Job has not completed; do not report success')
    rows=[]
    for s in read(job/'summaries.json'):
        folder=job/s['sample_id'];sample=read(folder/'sample.json');index=folder/'index-summary.json'
        selected=folder/s.get('selected_attempt','')/'index-summary.json'
        playback=folder/'playback.json'
        rows.append(dict(id=s['sample_id'],kind=sample['kind'],complete=s.get('complete'),failure=s.get('failure'),
            attempts=s.get('attempts'),times=s.get('times'),burning=s.get('burning_original_rooms'),
            index_exists=index.exists(),attempt_index_exists=selected.exists(),
            attention=read(index) if index.exists() else None,
            playback_exists=playback.exists(),playback_sha256=sha(playback) if playback.exists() else None,
            playback_fire_key=read(playback).get('fire_key') if playback.exists() else None))
    polls=[json.loads(line) for line in (out/'status-polls.jsonl').read_text('utf-8').splitlines()]
    times=[r['response_ms'] for r in polls if r.get('http')==200]
    click=read(out/'click.json');finish=read(out/'finished.json')
    value=dict(request=request,job=job.name,workers=started['workers'],budget_s_per_sample=started['budget_s_per_sample'],
        mandatory=started['mandatory'],random=started['random'],batch_wall_s=progress['wall_s'],
        click_to_observed_completion_s=round(finish['unix']-click['clicked_at_ms']/1000,3),
        status_observation=dict(count=len(polls),http200=len(times),errors=[r for r in polls if r.get('http')!=200],
            median_ms=statistics.median(times),max_ms=max(times),p95_ms=sorted(times)[int((len(times)-1)*.95)],
            basis='independent read-only 3-second HTTP observations; UI also polls its own status'),
        aggregate=read(job/'aggregate.json'),rows=rows)
    (out/'run-report.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps({k:value[k] for k in ('job','batch_wall_s','click_to_observed_completion_s','status_observation')},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True)
    a=p.parse_args();report(a.job,a.evidence)
