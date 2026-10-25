"""v8 4.2/4.3 condition colours and CAD display; no thermal integration."""
from copy import deepcopy
import hashlib,json
import numpy as np
from shapely.geometry import Polygon,box,Point
from shapely.ops import unary_union

def states(model,result):
    n=model.N;y=model.sol.y;out={}
    for i,node in enumerate(model.nodes):
        rid=node['id'];rec=result['shared_conditions']['rooms'][rid]
        temp=y[2*n+i]-273.15;oxygen=y[4*n+i]*29/32;fuel=np.maximum(y[6*n+i],0.)
        z=(model.Va[i]-np.clip(y[n+i],model.Vmin[i],model.Va[i]-model.Vmin[i]))/model.Aa[i]
        lfl=model.P['LFL0_hrr']/model.P['dHc']*np.clip(1-(temp+273.15-293)/1300,.2,1.)
        hot=temp>=model.input_model['gas']['hot_C'];rich=fuel>=lfl
        accumulated=(model.Ha[i]-z>=.3)|(z<=1.8)
        count=hot.astype(int)+rich.astype(int)+accumulated.astype(int)
        stage=np.where(count==3,2,np.where(count>0,1,0))
        reaction=np.asarray(result['rooms'][i]['upper_reaction_kg_s'])
        roller=(stage==2)&(oxygen>=model.P['LOC'])&((temp+273.15>=model.P['T_ai'])|(reaction>0))
        fgi=(stage==2)&(oxygen>=model.P['LOC']);bd=(stage==2)&(oxygen<model.P['LOC'])
        fo=np.array([v is True for v in rec['FO']['scores']['all_met']])
        colors=np.where(fo,'#ef4444',np.where(fgi,'#a855f7',np.where(bd,'#facc15',np.where(stage==1,'#9ca3af',''))))
        labels=np.where(fo,'FO 조건 충족',np.where(roller,'롤오버 진행 조건',np.where(fgi,'FGI 가능',np.where(bd,'백드래프트 잠재',np.where(stage==1,'연기 주의','위험 조건 없음')))))
        out[rid]=dict(smoke_stage=stage.tolist(),smoke_factors_met=count.tolist(),phenomenon=labels.tolist(),
            color=colors.tolist(),rollover_band=(roller&~fo).tolist(),
            boundary=(np.abs(temp-model.manifest['rule_settings']['values']['temperature_C'])<=30).tolist(),
            factors=dict(hot=hot.tolist(),fuel=rich.tolist(),accumulated=accumulated.tolist()),
            source='v8 sections4.2/4.3; layer oxygen; LOC from existing core setting',
            LOC_vol_fraction=model.P['LOC'],boundary_threshold_C=model.manifest['rule_settings']['values']['temperature_C'])
    return out

def package(model,result,raw,label):
    if not result['ok']:raise ValueError('Incomplete results are not operational playback')
    originals={r['id']:r for r in raw['rooms']};cells=model.input_model['rooms'];t=np.array(result['t']);N=model.N
    colors=states(model,result);rows=[];solvers={};geometries={};cellmap={r['id']:r for r in cells}
    for i,c in enumerate(cells):
        original=originals[c.get('parent_room',c['id'])];polys=original['cad_polys']
        shape=unary_union([Polygon(p['o'],p.get('h',[])) for p in polys]);bounds=shape.bounds
        def project(xy):return [bounds[k]+(xy[k]-original['origin_m'][k])/original['size_m'][k]*(bounds[k+2]-bounds[k]) for k in (0,1)]
        lo=project(c['origin_m']);hi=project([c['origin_m'][k]+c['size_m'][k] for k in (0,1)])
        cut=shape.intersection(box(*lo,*hi));parts=list(cut.geoms) if hasattr(cut,'geoms') else [cut]
        parts=[p for p in parts if p.geom_type=='Polygon' and p.area>1e-8]
        if not parts:continue
        clipped=unary_union(parts);center=clipped.representative_point();rid=c['id'];geometries[rid]=(clipped,original,bounds)
        rows.append(dict(key=rid,solver_id=rid,original_room=c.get('parent_room',rid),cad_floor=c['cad_floor'],
            cad_room=rid.removeprefix('CAD_'+c['cad_floor']+'_'),cad_names=c.get('cad_names',[]),
            cad_center_m=[center.x,center.y],cad_polys=[dict(o=list(p.exterior.coords),h=[list(h.coords) for h in p.interiors]) for p in parts],
            area_m2=float(clipped.area),z_m=c['origin_m'][2],height_m=c['size_m'][2]))
        y=model.sol.y;tu=y[2*N+i]-273.15;h=(model.Va[i]-np.clip(y[N+i],model.Vmin[i],model.Va[i]-model.Vmin[i]))/model.Aa[i]
        # Constant optical appearance is ONLY a renderer input, never a measured OD.
        visible=(y[N+i]>3*model.Vmin[i])&(tu>model.P['T_in']-273.15+1)
        series=result['rooms'][i]
        solvers[rid]=dict(Tu=tu.tolist(),Tl=(y[3*N+i]-273.15).tolist(),h=h.tolist(),
            Ou=(y[4*N+i]*29/32).tolist(),Ol=(y[5*N+i]*29/32).tolist(),Fu=np.maximum(y[6*N+i],0).tolist(),
            ODu=np.where(visible,.24,0.).tolist(),ODl=[0.]*len(t),height_m=c['size_m'][2],
            Qbulk_kW=series['upper_HRR_kW'],Qvent_kW=series['door_jet_HRR_kW'],Qsolid_kW=series['actual_HRR_kW'],
            conditions=result['shared_conditions']['rooms'][rid],display_v8=colors[rid])
    events={e['room']:e for e in result['events']};fires=[];units=[]
    for g in model.input_model['fuel_groups']:
        rid=g['room']
        if rid not in geometries:continue
        shp,original,bounds=geometries[rid];c=cellmap[rid];pt=g['position_m']
        xy=[bounds[k]+(pt[k]-original['origin_m'][k])/original['size_m'][k]*(bounds[k+2]-bounds[k]) for k in (0,1)]
        if not shp.contains(Point(xy)):p=shp.representative_point();xy=[p.x,p.y]
        # Small symbols uniformly cover the CAD cell. These do not add fires or fuel.
        xmin,ymin,xmax,ymax=shp.bounds;step=max(2.,np.sqrt(shp.area/12.))
        for x in np.arange(xmin+step/2,xmax,step):
            for y in np.arange(ymin+step/2,ymax,step):
                if shp.contains(Point(x,y)):units.append(dict(room=rid,position_m=[float(x),float(y),c['origin_m'][2]+.2]))
        e=events.get(rid);initial='initial_time_s' in g
        if not initial and not e:continue
        at=0. if initial else e['supply_start_s'];q=np.array(solvers[rid]['Qsolid_kW'])
        # Always compact in viewer: height is display-only, not native flame length.
        fires.append(dict(id=g['id'],solver_id=rid,cad_key=rid,cad_floor=c['cad_floor'],cad_room=rid.removeprefix('CAD_'+c['cad_floor']+'_'),
            position_m=[*xy,c['origin_m'][2]],time_s=at,kind='initial' if initial else 'additional',Q_kW=q.tolist(),
            condition_time_s=0. if initial else e['condition_time_s'],
            visuals=dict(base_height_m=0.,flame_height_m=np.where(q>0,.9,0.).tolist(),area_m2=[.25]*len(t),radiative_fraction=.35,
                basis='compact display symbol only; no quantitative flame dimensions')))
    return dict(schema='pyrocast-cad-playback-1',engine_kind='pyrocast_lite',condition_version='lite_v8_two_stage',
        complete=True,time_s=t.tolist(),building_sha256=raw['cad']['building_sha256'],label=label,
        fire_key=next((f['cad_key'] for f in fires if f['kind']=='initial'),rows[0]['key']),
        rooms=rows,solvers=solvers,fires=fires,fuel_symbols=units,fuel_units=[],events=result['events'],
        original_room_count=len(originals),door_jet=result['door_jet'],integration=result['integration'],
        scene_geometry_basis='solver rectangular cells affinely mapped to original CAD bounds, then clipped to actual polygons; display approximation',
        smoke_basis='calculated upper-layer extent; constant gray opacity for display only; no soot or optical-density calculation',
        limits=['조건 충족 단계이며 발생 예측 아님','회색 연기: 계산된 상층 범위의 표시용 농도. 실제 광학밀도·연기 전면은 미계산.',
            '문 분출 연소는 받는 실 하층 산소를 소비하는 근사이며 롤오버와 별도.',
            '셀 배치는 계산 직사각형을 CAD 경계 안에 대응한 근사. 화염·연료 큐브는 표시 기호.',
            '창 파괴·수직 전파 OFF. 실제 HRR가 양수인 곳만 고체 화염 표시.'],
        provenance=dict(manifest_sha256=result['r8_manifest_sha256'],door_jet_enabled=True,
            engine_sha256=hashlib.sha256(b''.join(p.read_bytes() for p in sorted(__import__('pathlib').Path(__file__).parent.glob('*.py')))).hexdigest()))
