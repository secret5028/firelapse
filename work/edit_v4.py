from pathlib import Path
root=Path(r'C:\Users\<user>\Documents\Codex\2026-09-07\2\CAD3D')
def edit(name,old,new):
    p=root/name;s=p.read_text(encoding='utf-8');assert old in s,(name,old[:80]);p.write_text(s.replace(old,new),encoding='utf-8')

edit('cad_plan.py','cad-plan-auto-20261014-v3','cad-plan-connectivity-20261014-v4')
edit('cad_build3d.py',"span=o.get('span'), door_h=o.get('door_h'),","span=sc*o['span'] if o.get('span') else None, door_h=o.get('door_h'),\n                      guessed=o.get('guessed',False), connection_evidence=o.get('connection_evidence'),")
edit('cad_build3d.py',"core_all.append(dict(kind=c_['kind'], x=sc * c_['cx'] - dx, y=sc * c_['cy'] - dy, w=sc * c_['w'], h=sc * c_['h'], z0=z, z1=z + H, floor=names[i]))",
"""room_id=c_.get('room_id')
            if room_id is None:
                cp=Point(sc*c_['cx']-dx,sc*c_['cy']-dy)
                matches=[r['id'] for r in rooms if c_['kind'] in r.get('tags',[]) and unary_union([Polygon(p['o'],p['h']) for p in r['polys']]).contains(cp)]
                room_id=matches[0] if len(matches)==1 else None
            core_all.append(dict(kind=c_['kind'], x=sc * c_['cx'] - dx, y=sc * c_['cy'] - dy, w=sc * c_['w'], h=sc * c_['h'], z0=z, z1=z + H, floor=names[i],room_id=room_id,align=how))""")
p=root/'cad_build3d.py';s=p.read_text(encoding='utf8');start=s.index('    # 수직 공간: 같은 종류 코어가');end=s.index('    json.dump(B,',start)
s=s[:start]+"""    from cad_connectivity import build_graph, match_vertical_cores
    B['dropped_parts'] = dropped_parts
    B['shafts'], B['unconfirmed_vertical_cores'] = match_vertical_cores(core_all)
    B['opening_unit'] = 'percent'
    B['schema_version'] = 2
    for floor in B['floors']:
        floor['simulation_graph'] = build_graph(floor['rooms'],floor['openings'],
            dict(room_h=floor.get('ceil_h') or floor['h'],door_h=floor['door_h'],sill=floor['sill'],head=floor['head']))
        floor['vertical_status'] = 'matched_adjacent_floors' if any(floor['name'] in shaft['floors'] for shaft in B['shafts']) else 'unconfirmed'
"""+s[end:];p.write_text(s,encoding='utf8')

edit('fire_zone.py',"        doors = scen.get('doors', {}); wins = scen.get('windows', {})", """        from cad_connectivity import opening_fraction, build_graph
        unit = scen.get('opening_unit', 'percent')
        doors = {k: opening_fraction(v,unit) for k,v in scen.get('doors',{}).items()}
        wins = {k: opening_fraction(v,unit) for k,v in scen.get('windows',{}).items()}
        if any(k not in {o['id'] for o in F['openings'] if o['kind'].startswith('door')} for k in doors):
            raise ValueError('Unknown door ID in scenario')
        if any(k not in {o['id'] for o in F['openings'] if o['kind'] in ('window','window_inner')} for k in wins):
            raise ValueError('Unknown window ID in scenario')""")
edit('fire_zone.py',"        dflt_door = scen.get('door_open_default', 0); dflt_win = scen.get('window_open_default', 0)","""        dflt_door = opening_fraction(scen.get('door_open_default',0),unit)
        dflt_win = opening_fraction(scen.get('window_open_default',0),unit)
        graph = build_graph(F['rooms'],F['openings'],dict(room_h=H_room,
            door_h=F.get('door_h',2.1),sill=F.get('sill',.9),head=F.get('head',2.2)))
        self.input_graph = graph
        self.input_issues = dict(isolated_rooms=graph['isolated_rooms'],excluded_openings=graph['excluded_openings'],
            vertical_status=F.get('vertical_status','unconfirmed'))
        link_map = {o['id']:o for o in graph['connections']}""")
edit('fire_zone.py',"            if g.is_empty or r['id'] not in used: continue", "            if g.is_empty: raise ValueError('Empty room geometry: '+r['id'])")
p=root/'fire_zone.py';s=p.read_text(encoding='utf8');start=s.index("            if 'stair' in r.get('tags', []):");end=s.index("            rmap[r['id']] = len(nodes)",start)
s=s[:start]+"""            matches=[k for k,s in enumerate(shafts) if s.get('room_ids',{}).get(floor)==r['id']]
            if len(matches)>1: raise ValueError('Room mapped to multiple shafts: '+r['id'])
            if matches:
                rmap[r['id']]=idx[('S',matches[0])]; continue
"""+s[end:];s=s.replace("kind='room', zf=zf, H=H_room,","kind=next((k for k in ('elev','stair') if k in r.get('tags',[])),'room'), zf=zf, H=H_room,")
s=s.replace("A=max(g.area, 0.5)","A=g.area")
s=s.replace("            if o['kind'] == 'vent': continue\n            s = [rmap.get", "            if o['id'] not in link_map: continue\n            dim = link_map[o['id']]['dimensions']\n            s = [rmap.get")
s=s.replace("            w = _span(o)","            w = dim['width_m']")
s=s.replace("p = wins.get(o['id'], dflt_win) / 100.0","p = wins.get(o['id'], dflt_win)")
s=s.replace("p = doors.get(o['id'], dflt_door) / 100.0","p = doors.get(o['id'], dflt_door)")
s=s.replace("zb, zt = zf + (F.get('sill') or 0.9), zf + (F.get('head') or 2.2)","zb, zt = zf + dim['bottom_m'], zf + dim['top_m']")
s=s.replace("dh = o.get('door_h') or F.get('door_h') or 2.1","dh = dim['height_m']")
s=s.replace("P['door_leak'] / dh)","(P['elev_leak'] if o['kind']=='door_elev' else P['door_leak']) / dh)")
start=s.index("                c = Point(s['x'], s['y']); best = None");end=s.index("                add(i, OUT, P['shaft_top_vent']",start)
s=s[:start]+"                # Landing doors above already connect explicit room IDs to this shaft.\n"+s[end:]
s=s.replace("        self.vi = np.array([v[0] for v in V]); self.vj = np.array([v[1] for v in V])","        self.vi = np.array([v[0] for v in V],dtype=int); self.vj = np.array([v[1] for v in V],dtype=int)")
s=s.replace("                    ok=bool(sol.success), msg=sol.message)","                    input_issues=self.input_issues, opening_unit='percent',\n                    ok=bool(sol.success), msg=sol.message)")
p.write_text(s,encoding='utf8')
print('Updated v4 source integration')
