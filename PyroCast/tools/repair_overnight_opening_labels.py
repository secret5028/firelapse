"""Correct display-only opening booleans in this batch, retaining frozen inputs."""
from copy import deepcopy
from run_overnight_floors import OUT, ROOT, read, save, sha

def repair():
    plan=read(OUT/'plan.json')
    reports=[]
    for row in plan['rows']:
        from pathlib import Path
        folder=Path(row['folder'])
        if read(folder/'status.json',{}).get('state')!='complete': continue
        data=read(folder/'input.json')
        ids=data['overnight_openings']['confirmed_ids']
        if not ids: continue
        errata=folder/'opening-display-errata.json'
        if errata.exists(): continue
        assert sha(folder/'input.json')==row['input_sha256']
        config=(ROOT/'simulation/config/lite-door-overrides.json' if row['building']=='ganghwa' else
            ROOT/'simulation/config/model-fixed-openings'/(row['building_sha256']+'.json'))
        fixed=read(config)['fixed_state']
        assert {k:v for k,v in fixed.items() if k!='states'}==data['overnight_openings']['confirmation_source']
        states=deepcopy(data['screening_source']['opening_states']);changes=[]
        for state in states:
            if state['id'] not in ids: continue
            source=fixed['states'][state['id']]
            assert all(state[k]==source[k] for k in ('a','b','effective_fraction'))
            assert type(source['open']) is bool
            if state['open']!=source['open']:
                changes.append(dict(id=state['id'],before=state['open'],after=source['open']))
                state['open']=source['open']
        path=folder/'playback.json';before=sha(path);playback=read(path)
        assert playback['building_sha256']==row['building_sha256']
        playback['display_opening_state']=dict(building_sha256=row['building_sha256'],
            basis='saved_case_input_with_display_errata',states={s['id']:s for s in states})
        backup=folder/'playback.before-opening-labels.json'
        if not backup.exists(): backup.write_bytes(path.read_bytes())
        save(path,playback)
        report=dict(changes=changes,input_sha256=sha(folder/'input.json'),
            playback_before_sha256=before,playback_after_sha256=sha(path),
            confirmation_sha256=sha(config),reason='Closed leakage is not a physically open door',
            simulation_repeated=False,calculated_series_changed=False)
        save(errata,report);reports.append(dict(building=row['building'],floor=row['floor'],changed=len(changes)))
    return reports

if __name__=='__main__': print(repair())
