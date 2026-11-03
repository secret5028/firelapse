"""Shared drawing classification policy; fuel values remain in fire_load_table.json."""
import json
import re
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / 'config/building-rules.json'

def load_rules():
    return json.loads(CONFIG.read_text('utf-8'))

def usage_class(names, floor_use):
    policy = load_rules()['usage']
    text = ' / '.join(names)
    for cls, pattern in policy['names']:
        if re.search(pattern, text, re.I):
            return cls, {'basis': 'label', 'pattern': pattern}
    cls = policy['floor_use'].get(floor_use, 'default')
    return cls, {'basis': 'floor_use' if floor_use in policy['floor_use'] else 'default',
                 'floor_use': floor_use, 'label_unmapped': True}

def dedicated_core_kind(room):
    cfg = load_rules()['core']
    tags = set(room.get('tags', []))
    names = [s for s in room.get('names', []) if s and s not in cfg['ignored_names']]
    text = ' '.join(names).lower()
    dedicated = len(names) <= cfg['max_dedicated_labels']
    for kind in ('stair', 'elev'):
        if tags.intersection(cfg[kind+'_tags']) or dedicated and any(w in text for w in cfg[kind+'_tokens']):
            return kind
    return None
