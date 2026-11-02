"""Viewer adapter for v8 two-state comparisons, independent of operating playback."""
import json,time,subprocess,sys
from lite_fixed_openings import classifications
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SIM=ROOT/'simulation'
DEFAULT=SIM/'results/lite_v8_approved_screening_20261025'
SAVED=SIM/'config/lite-screening-selection.json'

def read(path,default=None):
    try:return json.loads(path.read_text('utf-8'))
    except (OSError,ValueError):return default

def payload(top_n=None):
    from pyrocast_lite.screening_v8_approved import score
    selection=read(SAVED,{})
    raw=read(SIM/'results/room_rule_r8_20261025/source-scenario.json')
    scored=score(raw,top_n if top_n is not None else selection.get('top_n',3),door_overrides=classifications(read(SIM/'config/lite-door-overrides.json',{})))
    from lite_manual_origin import origins
    manual=origins(scored)
    scored.pop('classified_model')
    destination=Path(selection.get('result_path',str(DEFAULT))).resolve()
    if not destination.is_relative_to((SIM/'results').resolve()):raise ValueError('Invalid result directory')
    comparison=read(destination/'comparison.json')
    legacy=comparison is not None and comparison.get('revision')!='v8_approved_screening'
    from export_ui_attention import comparison_attention
    progress=read(destination/'progress.json')
    if progress:progress={**progress,'running':progress.get('state') in ('queued','running')}
    return {'manual_origins':manual,'score':scored,'comparison':None if legacy else comparison,'legacy_comparison_not_reused':legacy,
            'progress':progress,'saved_score':read(destination/'score.json'),
            'selection':selection,'playback_replaced':False,
            'attention':comparison_attention(None if legacy else comparison)}

def select(top_n,mc_room=None,rooms=None):
    if type(top_n) is not int:raise ValueError('N must be an integer')
    data=payload(top_n)
    allowed={r['room'] for r in (data['score']['ranked'] if rooms is None else data['manual_origins'])}
    if rooms is not None and (not isinstance(rooms,list) or len(rooms)!=1 or not isinstance(rooms[0],str) or rooms[0] not in allowed or mc_room!=rooms[0]):raise ValueError('Invalid single source room')
    if mc_room is not None and mc_room not in allowed:raise ValueError('Invalid source room')
    value={**read(SAVED,{}),'top_n':top_n,'mc_room':mc_room,'manual_rooms':rooms}
    SAVED.parent.mkdir(parents=True,exist_ok=True)
    SAVED.write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf-8')
    return payload()

def compute(top_n,rooms=None):
    # One serial process; never launches MC or replaces completed 3D playback.
    out=SIM/'results'/('lite_screening_ui_'+str(time.time_ns()))
    selection={**read(SAVED,{}),'top_n':top_n,'result_path':str(out)}
    SAVED.write_text(json.dumps(selection,ensure_ascii=False,indent=2),'utf-8')
    out.mkdir(parents=True)
    (out/'progress.json').write_text(json.dumps({'state':'running','completed':0,'top_n':top_n,'total':2 if rooms else 2*top_n,'current_room':'입력 준비'}),'utf-8')
    with (out/'console.txt').open('w',encoding='utf-8') as log:
        try:
            subprocess.run([sys.executable,'-X','utf8',str(ROOT/'tools/run_lite_screening_v8_approved.py'),'--top-n',str(top_n),'--out',str(out)]+(['--room',rooms[0]] if rooms else []),
                           cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except Exception as exc:
            (out/'progress.json').write_text(json.dumps({'state':'failed','error':str(exc)}),'utf-8')
            raise


