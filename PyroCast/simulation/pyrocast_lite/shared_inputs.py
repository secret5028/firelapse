"""Read the generated native deck as the authority for shared physical inputs.

Parser intentionally supports this project's generated namelist subset only.
It is not a general Fortran parser or a replacement CFAST input parser.
"""
import hashlib
import re
import numpy as np
from pyrocast_cfbt.deck import make_deck


def records(deck):
    result=[]
    for m in re.finditer(r'&(\w+)\s+(.*?)\s*/',deck,re.S):
        kind,body=m.groups()
        if kind not in ('INIT','MATL','COMP','CHEM','MISC'):continue
        fields={}
        keys=list(re.finditer(r'\b([A-Z][A-Z_0-9]*)\s*=',body))
        for i,key in enumerate(keys):
            value=body[key.end():keys[i+1].start() if i+1<len(keys) else len(body)].strip().strip(',')
            if value.startswith("'"):
                fields[key[1]]=value.strip("'")
            else:
                try:
                    v=[float(x.strip().replace('D','E')) for x in value.split(',')]
                    fields[key[1]]=v[0] if len(v)==1 else v
                except ValueError:fields[key[1]]=value
        result.append((kind,fields))
    return result


def read_shared(model):
    # Legacy input inspection consumes INIT/MATL/COMP/CHEM/MISC only, not
    # native output devices. Keep CFAST execution capacity checks unchanged.
    deck=make_deck(model,[],model.get('explicit_candidates',[]),include_floor_gauges=False)
    rec=records(deck)
    init=next(v for k,v in rec if k=='INIT')
    materials={v['ID']:v for k,v in rec if k=='MATL'}
    comps={v['ID']:v for k,v in rec if k=='COMP'}
    chem={v['ID']:v for k,v in rec if k=='CHEM'}
    wall_data={}
    for room in model['rooms']:
        c=comps[room['id']];wall_data[room['id']]={}
        for surface in ('CEILING','WALL','FLOOR'):
            mat=materials[c[surface+'_MATL_ID']]
            d={key:float(mat[key]) for key in ('CONDUCTIVITY','DENSITY','SPECIFIC_HEAT','THICKNESS','EMISSIVITY')}
            d['SPECIFIC_HEAT']*=1000  # native kJ/kg K -> SI
            if min(d[x] for x in ('CONDUCTIVITY','DENSITY','SPECIFIC_HEAT','THICKNESS'))<=0 or not 0<=d['EMISSIVITY']<=1:
                raise ValueError('Invalid native material')
            d['kpc']=d['CONDUCTIVITY']*d['DENSITY']*d['SPECIFIC_HEAT']
            wall_data[room['id']][surface.lower()]=d
    leaks=[]
    for room in model['rooms']:
        c=comps[room['id']];w,d,h=(c[x] for x in ('WIDTH','DEPTH','HEIGHT'))
        ratios=c['LEAK_AREA_RATIO']
        if len(ratios)!=2 or min(ratios)<0:raise ValueError('Invalid leakage ratios')
        # Source: initialize_leakage, CFAST 7.7.7 initialization.f90:218-283.
        wall_area=room.get('radial_perimeter_m',2*(w+d))*h*ratios[0]
        floor_area=w*d*ratios[1]
        if wall_area>0:leaks.append({'room':room['id'],'kind':'wall','width':wall_area/(.9*h),'bottom':.05*h,'top':.95*h,'area':wall_area})
        if floor_area>0:
            width=.9*(w+d)/2
            leaks.append({'room':room['id'],'kind':'floor','width':width,'bottom':0.,'top':floor_area/width,'area':floor_area})
    fuels={}
    for g in model['fuel_groups']:
        c=chem['F_'+g['id']]
        fuels[g['room']]={'heat_of_combustion_J_kg':c['HEAT_OF_COMBUSTION']*1000,
                         'radiative_fraction':c['RADIATIVE_FRACTION']}
    misc=next(v for k,v in rec if k=='MISC')
    return {'deck_sha256':hashlib.sha256(deck.encode()).hexdigest(),
            'interior_K':init['INTERIOR_TEMPERATURE']+273.15,
            'exterior_K':init['EXTERIOR_TEMPERATURE']+273.15,
            'materials_by_room':wall_data,'leak_vents':leaks,'fuels_by_room':fuels,
            'native_LOL_mass':misc.get('LOWER_OXYGEN_LIMIT',.15),
            'native_LOL_default_source':'cfast_parameters.f90:183',
            'notes':['LEAK_AREA_RATIO is per-compartment leakage to outside, not per-door leakage',
                     'native leakage geometry retained; Cd=0.70 (section 1.2)',
                     'native tanhsmooth on oxygen mass fraction, lower limit from MISC/default, width 0.01']}


class FiniteWalls:
    """One thermal-capacity node per wall/ceiling/floor, half-thickness resistances.

Rear boundary is exterior ambient, as unconnected native compartment surfaces.
Uniform fire radiation allocation is a declared reduced view-factor assumption.
"""
    def __init__(self,model,shared):
        self.N=model.N
        mats=[shared['materials_by_room'][n['id']] for n in model.nodes]
        order=('ceiling','wall','floor')
        self.area=np.stack([model.Aa,model.pera*model.Ha,model.Aa],axis=1)
        self.k=np.array([[m[s]['CONDUCTIVITY'] for s in order] for m in mats])
        self.rho=np.array([[m[s]['DENSITY'] for s in order] for m in mats])
        self.cp=np.array([[m[s]['SPECIFIC_HEAT'] for s in order] for m in mats])
        self.d=np.array([[m[s]['THICKNESS'] for s in order] for m in mats])
        self.eps=np.array([[m[s]['EMISSIVITY'] for s in order] for m in mats])
        self.capacity=self.area*self.rho*self.cp*self.d

    def exchange(self,model,y,Tu,Tl,interface,fire_radiation):
        offset=8*self.N+(0 if model.P.get('remove_cumulative_state') else 1)
        wall=y[offset:].reshape(self.N,3)
        halfR=self.d/(2*self.k)
        radiation_on=model.P.get('gas_radiation_enabled',False)
        def flux(gas):
            # New grey exchange replaces the old implicit black-gas term.
            hr=0. if radiation_on else self.eps*5.67e-8*(gas**2+wall**2)*(gas+wall)
            return (gas-wall)/(1/(model.P['h_conv']+hr)+halfR)
        au=np.stack([model.Aa,model.pera*(model.Ha-interface),np.zeros(self.N)],axis=1)
        al=self.area-au
        qu=flux(Tu[:,None])*au;ql=flux(Tl[:,None])*al
        outside=model.P['T_out']
        hrback=self.eps*5.67e-8*(outside**2+wall**2)*(outside+wall)
        back=(wall-outside)/(halfR+1/(model.P['h_conv']+hrback))*self.area
        gas_fire=np.zeros(self.N);gas_wall=np.zeros((self.N,3));gas_eps=np.zeros(self.N)
        if radiation_on:
            from .radiation import upper_absorptivity,wall_to_upper
            gas_eps,_=upper_absorptivity(model.Aa,model.pera,model.Ha-interface)
            gas_fire=gas_eps*fire_radiation
            gas_wall=wall_to_upper(Tu,wall,self.eps,au,gas_eps)
            qu=qu-gas_wall  # opposite signs in gas and wall balances
        absorbed=(fire_radiation-gas_fire)[:,None]*self.area/self.area.sum(axis=1)[:,None]
        stored=qu+ql+absorbed-back
        return (qu.sum(axis=1),ql.sum(axis=1),(stored/self.capacity).ravel(),
                {'wall_front_W':float((qu+ql).sum()),'wall_back_W':float(back.sum()),
                 'wall_fire_radiation_W':float(absorbed.sum()),'wall_storage_W':float(stored.sum()),
                 'gas_fire_radiation_W':float(gas_fire.sum()),'gas_wall_radiation_W':float(gas_wall.sum()),
                 'gas_absorptivity_max':float(gas_eps.max()),'gas_fire_radiation_by_room':gas_fire})
