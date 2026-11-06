"""Boundary and missing-value checks for saved-result UI aggregation only."""
import importlib.util
import sys
from pathlib import Path

path = Path(__file__).resolve().parents[2] / 'tools/export_ui_attention.py'
sys.path.insert(0,str(path.parent))
spec = importlib.util.spec_from_file_location('ui_attention', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = {'t': [0], 'room_summary': [], 'shared_conditions': {'rooms': {}}}
for cell, room, value in [('a', 'R1', .7), ('b', 'R1', .8), ('c', 'R2', .69999), ('d', 'R3', None)]:
    result['room_summary'].append({'cell': cell, 'original_room': room})
    result['shared_conditions']['rooms'][cell] = {k: {'scores': {'degree': [value]}} for k in module.KINDS}
summary = module.summarize(result)
assert summary == {'attention_rooms': ['R1'], 'attention_room_count': 1, 'unknown_rooms': ['R3']}
result['shared_conditions']['rooms']['d']['FO']['scores']['degree'] = [.7]
assert module.summarize(result)['unknown_rooms'] == []
assert module.summarize(result)['attention_room_count'] == 2
print('PASS: >=70 edge, original-room dedup, unknown preservation, known hit across phenomena')
