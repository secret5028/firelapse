"""Export exact scenario inputs needed for official plume postprocessing."""
import re

def add_plume_metadata(result, input_path):
    blocks={}
    for kind,body in re.findall(r'&(\w+)\s+(.*?)/',input_path.read_text(encoding='utf8'),re.S):
        m=re.search(r"\bID='([^']+)'",body)
        if m: blocks.setdefault((kind,m[1]),[]).append(body)
    def field(body,key):
        m=re.search(r'\b'+key+r"\s*=\s*('[^']*'|[^\s/]+)",body)
        if not m: raise ValueError(f'Missing {key}')
        return m[1].strip("'")
    for f in result['fires']:
        fire=blocks['FIRE',f['id']][0]
        comp=blocks['COMP',field(fire,'COMP_ID')][0]
        fuel=field(fire,'FIRE_ID');chem=blocks['CHEM',fuel][0]
        tabs=blocks['TABL',fuel]
        labels=re.findall(r"'([^']+)'",tabs[0].split('LABELS=')[1])
        values=[list(map(float,field(t,'DATA').split(','))) for t in tabs if 'DATA=' in t]
        def constant(k):
            seq=[v[labels.index(k)] for v in values]
            if max(seq)-min(seq)>1e-8: raise ValueError('Time-varying '+k+' needs series export')
            return seq[0]
        location=list(map(float,field(fire,'LOCATION').split(',')))
        width=float(field(comp,'WIDTH'));depth=float(field(comp,'DEPTH'))
        area=constant('AREA');base=constant('HEIGHT')+(location[2] if len(location)>2 else 0)
        corner=4 if min(location[0],width-location[0])<=area**.5/2 and min(location[1],depth-location[1])<=area**.5/2 else 1
        f['plume_inputs']=dict(area=area,base=base,chi=float(field(chem,'RADIATIVE_FRACTION')),height=float(field(comp,'HEIGHT')),corner_factor=corner,hall="HALL=.TRUE." in comp.upper(),solver_location=location,solver_width=width,solver_depth=depth)
    result['plume_postprocess']=dict(version=29,source='CFAST-7.7.7/Source/CFAST/fire.f90',method='official correlations evaluated on existing 5-second outputs',not_solver_rerun=True)
