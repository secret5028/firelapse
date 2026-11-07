"""Explicit project assumptions, shared by the native and Lite adapters."""
import json
from pathlib import Path


def defaults(section):
    return json.loads((Path(__file__).resolve().parents[2]/'config/physics_defaults.json').read_text('utf-8'))[section]
