"""Shared drawing classification policy; fuel values remain in fire_load_table.json."""
import json
import re
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / 'config/building-rules.json'

def load_rules():
    return json.loads(CONFIG.read_text('utf-8'))

def vertical_feature_allowed(building,kind):
    policy=building.get('model_axioms')
    return policy is None or kind in policy.get('vertical_kinds',('stair','elev'))

def usage_class(names, floor_use):
    policy = load_rules()['usage']
    text = ' / '.join(names)
    matches = [(cls, pattern) for cls, pattern in policy['names'] if re.search(pattern, text, re.I)]
    classes = list(dict.fromkeys(cls for cls, _ in matches))
    if len(classes) > 1:
        # CAD labels may span several uses in one polygon. Do not let regex order
        # classify an entire mixed room as a low-load toilet and omit its fire.
        return policy['ambiguous_class'], {'basis': 'mixed_labels', 'matched_classes': classes,
            'review_required': True, 'reason': '여러 용도 라벨 혼재 · 미분류 기준량 임시 적용'}
    if matches:
        cls, pattern = matches[0]
        return cls, {'basis': 'label', 'pattern': pattern}
    cls = policy['floor_use'].get(floor_use, 'default')
    return cls, {'basis': 'floor_use' if floor_use in policy['floor_use'] else 'default',
                 'floor_use': floor_use, 'label_unmapped': True}

def dedicated_core_kind(room):
    if 'axiom_core_kind' in room:
        return room['axiom_core_kind'] if room['axiom_core_kind'] in ('stair','elev') else None
    cfg = load_rules()['core']
    tags = set(room.get('tags', []))
    names = [s for s in room.get('names', []) if s and s not in cfg['ignored_names']]
    text = ' '.join(names).lower()
    dedicated = len(names) <= cfg['max_dedicated_labels']
    for kind in ('stair', 'elev'):
        if tags.intersection(cfg[kind+'_tags']) or dedicated and any(w in text for w in cfg[kind+'_tokens']):
            return kind
    return None
