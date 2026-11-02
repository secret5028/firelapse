"""C8: a confirmed opening state produces one real result, never a fake pair."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation')]
from lite_fixed_openings import screening_states,apply_fixed,compare_fixed
model={'cad':{'building_sha256':'test'},'openings':[{'id':'D1','a':'R1','b':'R2','schedule':[[0,1]]}]}
fixed={'fixed_state':{'building_sha256':'test','states':{'D1':{'a':'R1','b':'R2','open':False,'effective_fraction':.01}}}}
assert screening_states(model,{})==['open_except_confirmed','closed']
assert screening_states(model,fixed)==['fixed']
assert apply_fixed(model,fixed)['openings'][0]['schedule']==[[0.,.01]]
case=dict(room='R1',name='R1',rank1=1,score=1,state='fixed',complete=True,
          burning_room_count=2,smoke_risk_room_count=3,smoke_caution_room_count=4,first_FO_s=40,origin_max_upper_C=650)
row=compare_fixed([case])[0]
assert row['state_results']==[case] and row['rank2']==1 and row['worst_state']=='fixed'
assert compare_fixed([{**case,'complete':False}])[0]['rank2'] is None
try:compare_fixed([case,case])
except ValueError:pass
else:raise AssertionError('duplicate accepted')
print('PASS: 2 extremes / 1 fixed input, exact schedules, single result ranking, incomplete and duplicate guards')
