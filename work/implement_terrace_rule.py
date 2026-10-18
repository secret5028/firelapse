from pathlib import Path
p=Path('work/cad-web/cad_engine/cad_model_transport.py');s=Path('outputs/CAD-테라스-v13/cad_model_transport.py').read_text('utf8')
a=s.index('def apply_outdoor_semantics(');z=s.index('    terrace=geometry(room[\'polys\'])',a)
s=s[:a]+'''def apply_outdoor_semantics(f, plan, building):
    """Classify exposed floor projections using aligned adjacent floor slabs.

    Ground/basement and a main roof beneath a penthouse are separate cases.
    A small alignment tolerance must not turn facade slivers into terraces.
    """
    if 'outdoor_source_model' in f:
        for key,value in f['outdoor_source_model'].items():f[key]=copy.deepcopy(value)
    f['outdoor_spaces']=[]
    upper=next((q for q in building['floors'] if abs(q['z']-f['z']-f['h'])<.02),None)
    if not upper or upper['name'].upper() in ('PH','RF','ROOF') or f['name'].upper().startswith('B'):return
    upper_slab=geometry(upper['slab'])
    exposed=geometry(f['slab']).difference(upper_slab.buffer(.25))
    candidates=[r for r in f['rooms'] if geometry(r['polys']).area>10
        and geometry(r['polys']).intersection(exposed).area/geometry(r['polys']).area>.8
        and not any(t in ('stair','elev') for t in r.get('tags',[]))]
    if not candidates:return
    f.setdefault('outdoor_source_model',{k:copy.deepcopy(f[k]) for k in ('bands','glass','openings','rooms','ceiling')})
    for room in candidates:
        _model_terrace(f, room, upper, upper_slab)


def _model_terrace(f, room, upper, upper_slab):
'''+s[z:]
s=s.replace("    if not 110<terrace.area<125:return\n",'').replace("    f.setdefault('outdoor_source_model',{k:copy.deepcopy(f[k]) for k in ('bands','glass','openings','rooms','ceiling')})\n    indoor=",'    indoor=')
s=s.replace("    f['outdoor_spaces']=[dict(","    f['outdoor_spaces'].append(dict(")
s=s.replace("evidence='사용자 지적과 3F CAD 돌출부 대조에 따른 테라스 해석',changed_openings=changed,\n        classification_status='reviewed_interpretation_not_measured')]", "evidence='계단·승강기로 정렬된 해당 층과 직상층 바닥 비교',changed_openings=changed,\n        compared_floor=upper['name'],upper_slab_overlap_m2=terrace.intersection(upper_slab).area,\n        classification_status='aligned_floor_projection_rule'))")
s=s.replace('apply_outdoor_semantics(f,plan)','apply_outdoor_semantics(f,plan,b)')
p.write_text(s,'utf8')
