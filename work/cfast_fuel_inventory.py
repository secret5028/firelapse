"""Editable unit inventory rendered on a grid, linked to representative native fires."""
import math

def energy_mj(curve):
    return sum((b[0]-a[0])*(a[1]+b[1])/2 for a,b in zip(curve,curve[1:]))/1000

def add_fuel_inventory(result):
    scenario=result.get('ignition_scenario',{})
    if not any('fuel_fraction' in f for f in result['fires']):return
    profiles=scenario.get('unit_profiles',{'desk':{'height_m':.75,'depth_limit_m':.8},'cabinet':{'height_m':1.2,'depth_limit_m':.65},'tall_cabinet':{'height_m':1.8,'depth_limit_m':.65}})
    total_energy=total_mass=0
    for f in result['fires']:
        primary=f['id']=='ExampleFire'
        growth=result['design_fire'] if primary else scenario['growth']
        fraction=f.get('fuel_fraction',1.)
        energy=energy_mj(growth['hrr_kW'])*fraction
        mass=energy/(growth['heat_of_combustion_kJ_kg']/1000)
        f['inventory_energy_MJ']=energy;f['inventory_equivalent_fuel_kg']=mass
        f['prescribed_peak_kW']=max(q for _,q in growth['hrr_kW'])*fraction
        total_energy+=energy;total_mass+=mass
        n=4 if fraction==1 else 2
        nx=2;ny=n//2
        w=f.get('width_m',math.sqrt(f['area']));d=f.get('depth_m',math.sqrt(f['area']))
        units=[]
        for i in range(n):
            ix=i%nx;iy=i//nx
            kind=['desk','cabinet','desk','tall_cabinet'][i]
            h=profiles[kind]['height_m']
            assert h>0
            units.append(dict(id=f['id']+'_U'+str(i+1),representative_fire_id=f['id'],grid=[ix,iy],
                position=[f['position'][0]+(ix-(nx-1)/2)*w/nx,f['position'][1]+(iy-(ny-1)/2)*d/ny],
                width_m=w/nx*.88,depth_m=min(d/ny*.88,profiles[kind]['depth_limit_m']),height_m=h,shape=kind,
                energy_MJ=energy/n,equivalent_fuel_kg=mass/n,representative_weight=1/n,
                heat_of_combustion_MJ_kg=growth['heat_of_combustion_kJ_kg']/1000,
                target_material_ref=None if primary else scenario['material']['id'],
                geometry_is_envelope=True,mass_source='prescribed curve energy share / heat of combustion; not envelope volume times density',
                dimension_basis='illustrative furniture unit; not surveyed inventory',
                ignition_model='shared representative target; no individual-cell ignition'))
        f['fuel_units']=units
    result['fuel_inventory']=dict(version=30,unit_count=sum(len(f['fuel_units']) for f in result['fires']),
        representative_fire_count=len(result['fires']),prescribed_energy_MJ=total_energy,equivalent_fuel_kg=total_mass,
        basis='Integral of declared 1800-second source curves / heat of combustion; scenario fuel equivalent, not measured building stock',
        heights_m=[.75,1.2,1.8],grid_cells_are_independent_fires=False)
    result['assumptions'].append('격자 단위는 가구 재고의 단순화 표시이며 대표 화원에 연결됨. 책상 0.75m·수납장 1.2/1.8m는 표시용 가정. 각 단위의 열량/환산질량 합은 대표 묶음과 같음. 판정 표면 높이와 화원 기저 높이는 기존 입력을 유지하며 가구 표시 높이와 구분. 작은 묶음의 HRR/면적 비례 분할은 시나리오 근사이며 별도 가구 연소시험이 아님.')
