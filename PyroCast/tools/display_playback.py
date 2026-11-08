"""Serialization of NEW display playback only; never round solver/MC inputs."""
import math
from pyrocast_cfbt.physics_config import defaults
from result_catalog import atomic_json

def display_copy(playback):
    cfg=defaults('display_output');digits=cfg['decimal_places'];boundaries=cfg['degree_boundaries']
    if type(digits) is not int or digits<0 or digits>15:raise ValueError('Invalid display decimal places')
    step=10**-digits
    def copy(value,key=None):
        if isinstance(value,dict):return {k:copy(v,k) for k,v in value.items()}
        if isinstance(value,list):return [copy(v,key) for v in value]
        if isinstance(value,float):
            if not math.isfinite(value):raise ValueError('Non-finite display number')
            rounded=round(value,digits)
            # Preserve display-derived 70/100 comparisons. Full-precision
            # result/summary and original Boolean gates/events stay authoritative.
            if key in ('degree','proximity','potential'):
                for boundary in boundaries:
                    if value<boundary<=rounded:rounded=round(boundary-step,digits)
            return 0.0 if rounded==0 else rounded
        return value
    result=copy(playback)
    result['display_serialization']=dict(revision='playback_decimal_v1',decimal_places=digits,
        compact_json=True,degree_boundaries=boundaries,raw_source='CFAST/*.csv; result.json and summary.json retain analysis precision')
    return result

def save_playback(path,playback):
    value=display_copy(playback)
    atomic_json(path,value,compact=True)
    return value
