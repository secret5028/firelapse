"""Apply source-bound AI drawing review decisions, with geometry validation.

This consumes recorded visual reviews, not invented nearest-room links. A fresh
drawing requires a fresh review; source SHA and room IDs must still match.
"""
from copy import deepcopy
import numpy as np
from cad_arc_doors import bind_leaf
from cad_connectivity_shared import geometry

def apply_reviewed_connections(floor,policy):
    shapes={r['id']:geometry(r['polys']) for r in floor['rooms']};changes=[];reviews=[]
    for decision in floor.get('ai_connection_reviews',[]):
        if decision['source_sha256']!=floor.get('cad_arc_provenance',{}).get('source_sha256'):
            raise ValueError('AI drawing review source SHA mismatch: '+decision['id'])
        h,e=decision['closed_plane'];binding=bind_leaf(dict(hinge=h,closed=e),shapes,policy)
        if not binding['sides'] or set(binding['sides'])!=set(decision['sides']):
            raise ValueError('AI drawing review geometry mismatch: '+decision['id'])
        if decision['kind'] not in ('door_elev','door','open_passage'):raise ValueError('Unsupported reviewed aperture')
        existing=next((o for o in floor['openings'] if o['id']==decision['id']),None)
        if existing is None:
            a=np.array(h,float);b=np.array(e,float);u=b-a;w=float(np.linalg.norm(u));n=np.array([-u[1],u[0]])/w*.025
            c=dict(kind='ai_reviewed_connection',before=None,after=decision['sides'],basis=decision['axiom'],evidence=decision['evidence'])
            floor['openings'].append(dict(id=decision['id'],kind=decision['kind'],sides=decision['sides'],span=round(w,4),
                polys=[[(a-n).tolist(),(b-n).tolist(),(b+n).tolist(),(a+n).tolist()]],
                door_h=floor['h'] if decision['kind']=='open_passage' else floor.get('door_h') or 2.1,
                connection_confidence='inferred',connection_evidence={**binding,'ai_review':deepcopy(decision)},
                auto_corrections=[c]))
            changes.append(dict(floor=floor['name'],id=decision['id'],**c))
        reviews.append(dict(floor=floor['name'],id=decision['id'],kind='door_connection_estimated',
            sides=decision['sides'],detail='AI 도면 검토 · 연결 추정 · '+decision['evidence']))
    return dict(changes=changes,reviews=reviews)
