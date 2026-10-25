"""Project-only batched reruns. No native engine state restoration or new physics."""
import time
import numpy as np
from .deck import active_fuels
from .native import interruption_status


def tolerance(settings, old):
    return max(settings['converge_abs_s'],settings['converge_rel']*old)


def merge(model, events, fo, decisions, proposals):
    settings=model['spread']; flags=[]
    def earlier(old, candidates, key):
        out={e[key]:dict(e) for e in old}
        found={e[key]:e for e in sorted(candidates,key=lambda e:-e['t_ign_s'])}
        for ident,event in found.items():
            prev=out.get(ident)
            if prev is None or event['t_ign_s']<prev['t_ign_s']-tolerance(settings,prev['t_ign_s']):out[ident]=dict(event)
        for ident,event in list(out.items()):
            if ident not in {e[key] for e in old}:continue
            candidate=found.get(ident)
            if candidate is None or candidate['t_ign_s']>event['t_ign_s']+tolerance(settings,event['t_ign_s']):
                flags.append({'kind':'later_or_missing','key':ident,'t_old':event['t_ign_s'],
                              't_new':candidate['t_ign_s'] if candidate else None})
        return out
    new=earlier(events,decisions,'group'); nf=earlier(fo,proposals,'room')
    for gid,event in list(new.items()):
        if event['room'] in nf and event['t_ign_s']>nf[event['room']]['t_ign_s']:
            del new[gid];flags.append({'kind':'pooled_by_fo','key':gid})
    ordered=sorted(new.values(),key=lambda e:(e['t_ign_s'],e['group']))
    if len(ordered)>settings['max_added_ignitions']:
        flags.extend({'kind':'truncated','key':e['group']} for e in ordered[settings['max_added_ignitions']:])
        ordered=ordered[:settings['max_added_ignitions']]
    # Truncation can remove an FO's only predecessor. Validate AFTER all edits.
    starts={g['id']:g['initial_time_s'] for g in model['fuel_groups'] if 'initial_time_s' in g}
    starts.update({e['group']:e['t_ign_s'] for e in ordered})
    for rid,event in list(nf.items()):
        if not any(g['room']==rid and starts.get(g['id'],float('inf'))<=event['t_ign_s'] for g in model['fuel_groups']):
            del nf[rid];flags.append({'kind':'fo_without_source','key':rid})
    return ordered,sorted(nf.values(),key=lambda e:(e['t_ign_s'],e['room'])),flags


def signature(events,fo):
    return {('solid',e['group']):e['t_ign_s'] for e in events}|{('fo',e['room']):e['t_ign_s'] for e in fo}


def prefix_check(model,old,new,events,fo,next_events,next_fo,check):
    a=signature(events,fo);b=signature(next_events,next_fo)
    changed=[v for k in a.keys()|b.keys() if a.get(k)!=b.get(k) for v in (a.get(k),b.get(k)) if v is not None]
    cut=min(changed)
    settings={**model['spread'],'causality_abs':{k:v for k,v in model['spread']['causality_abs'].items() if k!='HRR'}}
    record={'before_s':cut,'ok':True}
    try:
        check(old,new,{'t_ign_s':cut},settings)
        # FIRE indices change with batch membership. Match by stable group ID.
        t=old['zone']['Time'];mask=t<cut-settings['event_tolerance_s']
        def sources(result,es):
            return {g['id']:result['zone'][f'HRR_{i}'] for i,g in enumerate(active_fuels(model,es),1)}
        x=sources(old,events);y=sources(new,next_events)
        maximum=0.
        for gid in x.keys()|y.keys():
            av=x.get(gid,np.zeros(len(t)))[mask]
            bv=np.interp(t[mask],new['zone']['Time'],y.get(gid,np.zeros(len(new['zone']['Time']))))
            maximum=max(maximum,float(np.max(np.abs(av-bv),initial=0)))
            if not np.allclose(av,bv,rtol=settings['causality_rel'],atol=model['spread']['causality_abs']['HRR']):
                raise ValueError('Pre-event fire mismatch: '+gid)
        record['max_HRR_diff_W']=maximum
    except ValueError as exc:record.update(ok=False,error=str(exc))
    return record


def iterate(model,current,targets,run,runs,attempts,started,assess,fo_proposals,check):
    from copy import deepcopy
    seed=model.get('native_prefix_seed',{})
    s=model['spread'];events=deepcopy(seed.get('events',[]));fo=deepcopy(seed.get('transitions',[]));history=[];checks=[];all_flags=[];pending=[];error=None
    status='not_converged';stable=False;flags=[];decisions=[];views=[];states={}
    for number in range(1,s['max_passes']+1):
        decisions,views,states=assess(model,current,targets,events,fo,
            deadline=started+s['wall_time_budget_s'],reevaluate=True)
        if not s['enabled']:decisions=[]
        proposals=fo_proposals(model,current,states,events,[],views)
        # Re-evaluate FO only from observations strictly before its own change.
        for e in fo:
            prior=current['zone']['Time'][current['zone']['Time']<e['t_ign_s']-s['event_tolerance_s']]
            proposals=[p for p in proposals if p['room']!=e['room'] or (len(prior) and p['t_ign_s']<=prior[-1])]
        ne,nf,flags=merge(model,events,fo,decisions,proposals)
        for f in flags:
            if f['kind']=='later_or_missing' and f['t_new'] is None:
                f['reason']='not_reconfirmed_before_self_heating_boundary_or_conditions_weakened'
        all_flags.extend({'pass':number,**f} for f in flags)
        stable=signature(events,fo)==signature(ne,nf)
        history.append({'pass':number,'executed_events':signature_json(events),'executed_fo':signature_json(fo,'room'),
                        'proposed_events':signature_json(ne),'proposed_fo':signature_json(nf,'room'),
                        'input_sha256':current['run']['input_sha256'],'flags':flags})
        pending=[] if stable else ne+nf
        if any(v.get('status')=='unevaluated' for v in views):status='time_budget';break
        if stable:
            status='converged';break
        if number==s['max_passes']:break  # Last completed pass is always assessed.
        if len(attempts)>=s['max_runs']:status='max_runs';break
        if time.monotonic()-started>=s['wall_time_budget_s']:status='time_budget';break
        try:updated=run(ne,nf)
        except TimeoutError as exc:status=interruption_status(exc);error=str(exc);break
        except (RuntimeError,ValueError) as exc:status='solver_failed';error=str(exc);break
        diagnostic=prefix_check(model,current,updated,events,fo,ne,nf,check)
        checks.append({'pass':number+1,**diagnostic})
        # Transaction: publish a schedule only with its successful native result.
        current=updated;events=ne;fo=nf;runs.append(current['run'])
    consistent=stable and not any(f['kind'] in ('later_or_missing','truncated','fo_without_source') for f in flags) and all(c['ok'] for c in checks)
    meta={'mode':'fixed_point','passes':len(history),'terminated':status,'schedule_stable':stable,
          'condition_consistent':consistent,'history':history,'flags':all_flags,'final_flags':flags,
          'pass_consistency':checks,'native_seconds':[0 if r.get('cache_hit') else r.get('wall_seconds',0) for r in runs],
          'tolerance_abs_s':s['converge_abs_s'],'tolerance_rel':s['converge_rel'],
          'pass_definition':'one completed native result plus assessment; retries count toward max_runs',
          'full_reruns':True}
    return current,events,fo,decisions,views,states,pending,status,error,meta


def signature_json(events,key='group'):
    return {e[key]:e['t_ign_s'] for e in events}
