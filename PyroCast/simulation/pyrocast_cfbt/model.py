from copy import deepcopy
import math
import re
from .openings import DEFAULT_POLICY, window_targets

DEFAULTS = {
    "duration_s": 180.0, "output_step_s": 1.0, "max_time_step_s": 0.05,
    "ambient_C": 20.0,
    "engine_optimization": {"radiation_cache": False,"wall_cache":False,
                            "adaptive_radiation":False,"adaptive_min_age_s":120.,
                            "adaptive_stable_s":30.,"adaptive_refresh_s":10.},
    "window_breakage": DEFAULT_POLICY,
    "wall_material": {"conductivity_W_mK":0.12,"density_kg_m3":800.0,
                      "specific_heat_kJ_kgK":1.0,"thickness_m":0.02,"emissivity":0.94,
                      "assumed":True,"basis":"declared_project_boundary_assumption"},
    "gas": {"mixture_enabled": False, "jet_enabled": False, "mixture_smooth_enabled":False,
            "mixture_o2_width_vol":.01,"mixture_temperature_width_C":10.,"mixture_fuel_width":.0001,"mixture_mixing_time_s":10.,
            "energy_basis": "total_potential_assumption", "enabled": True, "bulk_enabled": True, "vent_gate_enabled": True,
            "gas_ignition_C": 520.0, "hot_C": 300.0, "oxygen_min_vol_percent": 12.0,
            "fuel_min_mass_fraction": 0.001, "rate_ref_s_inv": 0.1,
            "reference_K": 800.0, "activation_J_mol": 170000.0,
            "vent_ignition_C": 520.0, "pilot_assumed": False,
            "native_lower_oxygen_limit_mass_fraction": 0.15,
            "pilot_start_s": 0.0, "pilot_end_s": 1e9,
            "profile_id": "project_arrhenius_exploration_v1",
            "basis": "project_assumption_not_a_validated_Kudo_fit"},
    "spread": {"enabled": True, "max_added_ignitions": 3, "max_runs": 4,
               "iteration_mode": "earliest_single", "max_passes": 5,
               "converge_abs_s": None, "converge_rel": 0.01,
               "wall_time_budget_s": 900.0, "run_timeout_s": 300.0,
               "event_tolerance_s": 0.00001, "exposure_case": "local",
               "quadrature_n": 12, "djet_radiative_fraction": 0.3,
               "djet_r_min_m": 0.5, "near_flame_m": 1.0,
               "candidate_offsets_m": [0.5, 1.5], "candidate_heights_m": [0.75, 1.5],
               "plate_dt_s": 0.05, "plate_nodes": 49,
               "causality_abs": {"ULT": 0.2, "LLT": 0.2, "HGT": 0.002, "HRR": 20.0, "DJET": 20.0},
               "causality_rel": 1e-4},
    "criteria": {"oxygen_deficient_vol_percent": 10.0, "hot_C": 300.0,
                 "fuel_rich_mass_fraction": 0.1, "rapid_C_s": 5.0, "window_s": 30.0,
                 "fo_temperature_C": 600.0, "fo_flux_kW_m2": 20.0,
                 "fgi_fuel_mass_fraction": .005, "fgi_oxygen_vol_percent": 10.0},
    "flashover": {"enabled": False, "criterion": "temperature", "transition_s": 30.0,
                  "hrrpua_kW_m2": None, "decay_fraction": 0.3,
                  "area_basis": "floor", "occupancy_fraction": 0.31, "radiation_points": 1,
                  "basis": "user_threshold_and_prescribed_finite_room_supply_not_NIST_default"},
    "material": {"id": "paper_proxy", "conductivity_W_mK": 0.04184,
                 "density_kg_m3": 500.0, "specific_heat_kJ_kgK": 2.092,
                 "thickness_m": 0.025, "absorptivity": 0.9, "emissivity": 0.9,
                 "ignition_C": 369.0, "proxy": True, "pilot": "assumed"},
}


def merge(base, patch):
    result = deepcopy(base)
    for key, value in patch.items():
        result[key] = merge(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else deepcopy(value)
    return result


def normalize(raw):
    model = merge(DEFAULTS, raw)
    if model.get('room_fire_rule',{}).get('prepared') and not model['room_fire_rule'].get('enabled'):
        raise ValueError('Use the original scenario to return to legacy spread; prepared room-rule budgets cannot be reversed')
    def finite(value):
        if isinstance(value,dict):
            for item in value.values():finite(item)
        elif isinstance(value,list):
            for item in value:finite(item)
        elif isinstance(value,(int,float)) and not math.isfinite(value):
            raise ValueError('All numeric inputs must be finite')
    finite(model)
    if model['spread']['converge_abs_s'] is None:
        model['spread']['converge_abs_s']=2*model['output_step_s']
    if model['spread']['iteration_mode'] not in ('earliest_single','fixed_point'):
        raise ValueError('Unknown iteration mode')
    if isinstance(model['spread']['max_passes'],bool) or int(model['spread']['max_passes'])!=model['spread']['max_passes'] or model['spread']['max_passes']<1:
        raise ValueError('max_passes must be a positive integer')
    if min(model['spread']['converge_abs_s'],model['spread']['converge_rel'])<0:
        raise ValueError('Invalid iteration tolerance')
    if not model.get("rooms") or not model.get("fuel_groups"):
        raise ValueError("rooms and fuel_groups are required")
    identifiers = [r["id"] for r in model["rooms"]]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Duplicate room IDs")
    all_ids = identifiers + [v["id"] for v in model.get("openings", [])] + [f["id"] for f in model["fuel_groups"]]
    if any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,45}", i) for i in all_ids):
        raise ValueError("Native IDs must be short ASCII identifiers")
    for room in model["rooms"]:
        if len(room["origin_m"]) != 3 or len(room["size_m"]) != 3 or min(room["size_m"]) <= 0 or min(room['size_m'][:2])<=.6:
            raise ValueError("Invalid room box")
    if len(identifiers)>100:
        raise ValueError('CFAST supports at most 100 interior compartments; reduce the selected scope')
    force=model.get('ignition_assumption')
    if force:
        if force.get('room') not in identifiers or not 0<=force['time_s']<model['duration_s'] or not 1<=force['duration_s']<=60 or not .01<=force['rate_s_inv']<=1:
            raise ValueError('Invalid ignition assumption')
        if not .1<=force.get('oxygen_min_vol_percent',10.)<=21:
            raise ValueError('Invalid assumed ignition oxygen threshold')
        if not model['gas']['enabled'] or not model['gas']['bulk_enabled']:
            raise ValueError('Gas reaction must be enabled for an ignition assumption')
    groups = set()
    for group in model["fuel_groups"]:
        if group["id"] in groups or group["room"] not in identifiers:
            raise ValueError("Invalid fuel-group identity")
        groups.add(group["id"])
        group.setdefault('co_yield',.01)
        if group.get('fuel_units'):
            if any(not 0<u['budget_fraction']<=1 for u in group['fuel_units']) or not math.isclose(sum(u['budget_fraction'] for u in group['fuel_units']),1.,abs_tol=1e-10):
                raise ValueError('Fuel unit shares must sum to the shared room budget')
            for unit in group['fuel_units']:
                unit['energy_MJ']=group['energy_MJ']*unit['budget_fraction']
        if not 0<=group['co_yield']<1:raise ValueError('Invalid CO yield')
        if 'fuel_area_m2' in group and group['fuel_area_m2']<=0:
            raise ValueError('Invalid fuel footprint area')
        group.setdefault('formula',{'carbon':1.0,'hydrogen':1.7,'oxygen':0.72,'nitrogen':0.0,'chlorine':0.0})
        group.setdefault('formula_assumed',True)
        if set(group['formula'])-{'carbon','hydrogen','oxygen','nitrogen','chlorine'} or min(group['formula'].values())<0:
            raise ValueError('Invalid effective fuel formula')
        for key in ("energy_MJ", "heat_of_combustion_kJ_kg", "growth_kW_s2", "peak_kW", "hrrpua_kW_m2"):
            if not math.isfinite(group[key]) or group[key] <= 0:
                raise ValueError(f"Invalid fuel parameter: {key}")
        from .mixture import primary_ratio,validate_stoichiometry
        primary_ratio(model,group)
        if model['gas'].get('mixture_enabled'):validate_stoichiometry(group)
    seed=model.get('native_prefix_seed')
    if seed:
        if seed.get('basis')!='computed_native_prefix' or not 0<seed.get('horizon_s',0)<=model['duration_s']:
            raise ValueError('Invalid native prefix seed provenance')
        if model['spread']['iteration_mode']!='fixed_point':raise ValueError('Prefix assessment seeds require fixed-point re-evaluation')
        byid={g['id']:g for g in model['fuel_groups']}
        seen=set()
        for event in seed.get('events',[]):
            if event['group'] in seen or event['group'] not in byid or 'initial_time_s' in byid[event['group']]:
                raise ValueError('Invalid prefix fuel event')
            seen.add(event['group'])
            if event['room']!=byid[event['group']]['room'] or not 0<=event['t_ign_s']<=seed['horizon_s']:
                raise ValueError('Prefix event exceeds evaluated horizon')
        for event in seed.get('transitions',[]):
            if event['room'] not in identifiers or not 0<=event['t_ign_s']<=seed['horizon_s']:
                raise ValueError('Invalid prefix FO event')
    for opening in model.get("openings", []):
        vertical=opening.get('type')=='FLOOR'
        if opening["a"] not in identifiers + (["OUTSIDE"] if vertical else []) or opening["b"] not in identifiers + ["OUTSIDE"]:
            raise ValueError("Unknown opening room")
        if opening["a"] == opening["b"] or (not vertical and opening["face"] not in ("FRONT", "REAR", "LEFT", "RIGHT")):
            raise ValueError("Invalid opening")
        schedule = opening.get("schedule", [[0, 1]])
        if not schedule or schedule[0][0] != 0 or any(not 0 <= row[1] <= 1 for row in schedule):
            raise ValueError("Opening schedule must begin at zero with fractions in [0,1]")
        if any(b[0] <= a[0] for a, b in zip(schedule, schedule[1:])):
            raise ValueError("Opening times must strictly increase")
        if vertical and opening['area_m2']<=0:
            raise ValueError('Invalid vertical aperture area')
        if not vertical and (opening["width_m"] <= 0 or opening["top_m"] <= opening.get("bottom_m", 0)):
            raise ValueError("Invalid aperture dimensions")
    if any(v.get('type')!='FLOOR' for v in model.get('openings',[])[next((i for i,v in enumerate(model.get('openings',[])) if v.get('type')=='FLOOR'),len(model.get('openings',[]))):]):
        raise ValueError('Wall vents must precede floor vents for native diagnostic indexing')
    if model["spread"]["exposure_case"] != "local":
        raise ValueError("First implementation supports the local exposure loop only")
    if any(not isinstance(model['engine_optimization'][key],bool) for key in ('radiation_cache','wall_cache','adaptive_radiation')):
        raise ValueError('Execution cache flags must be boolean')
    for key in ('adaptive_min_age_s','adaptive_stable_s','adaptive_refresh_s'):
        value=model['engine_optimization'][key]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
            raise ValueError('Adaptive radiation times must be finite and positive')
    gas = model["gas"]
    if not isinstance(gas['mixture_smooth_enabled'],bool):raise ValueError('Invalid smooth mixture flag')
    if gas['mixture_smooth_enabled']:
        if not gas['mixture_enabled']:raise ValueError('Smooth mixture requires mixture mode')
        if gas['mixture_mixing_time_s']<=0 or model['max_time_step_s']>gas['mixture_mixing_time_s']:
            raise ValueError('Mixture requires max_time_step_s <= positive mixing time')
        if min(gas[k] for k in ('mixture_o2_width_vol','mixture_temperature_width_C','mixture_fuel_width'))<=0:
            raise ValueError('Positive mixture transition widths required')
    if any(not isinstance(gas[k],bool) for k in ('mixture_enabled','jet_enabled')):raise ValueError('Invalid mixture/jet flag')
    if not 0 < gas["oxygen_min_vol_percent"] < 100 or gas["rate_ref_s_inv"] < 0 or gas["reference_K"] <= 0:
        raise ValueError("Invalid gas profile")
    if gas["activation_J_mol"] < 0 or not 0 <= gas["fuel_min_mass_fraction"] < 1:
        raise ValueError("Invalid reaction parameters")
    if not 0 <= gas['native_lower_oxygen_limit_mass_fraction'] < 1:
        raise ValueError('Invalid native oxygen-rate limit')
    if min(model["duration_s"], model["output_step_s"], model["max_time_step_s"]) <= 0:
        raise ValueError("Invalid time resolution")
    if not math.isclose(model['duration_s']/model['output_step_s'],round(model['duration_s']/model['output_step_s']),abs_tol=1e-8):
        raise ValueError('duration_s must be a multiple of output_step_s')
    if model["spread"]["max_runs"] < 1 or model["spread"]["max_added_ignitions"] < 0:
        raise ValueError("Invalid execution budget")
    for key in ('max_runs','max_added_ignitions','quadrature_n','plate_nodes'):
        value=model['spread'][key]
        if isinstance(value,bool) or int(value)!=value:
            raise ValueError('Execution counts must be integers: '+key)
    if min(model['spread'][k] for k in ('wall_time_budget_s','run_timeout_s','plate_dt_s','quadrature_n'))<=0 or model['spread']['plate_nodes']<3:
        raise ValueError('Invalid execution/thermal budget')
    mat = model["material"]
    fo = model['flashover']
    if not 0<model['criteria']['fgi_fuel_mass_fraction']<1 or not 0<model['criteria']['fgi_oxygen_vol_percent']<=21:
        raise ValueError('Invalid FGI screening thresholds')
    if fo['area_basis'] not in ('fuel','floor') or not 0<fo['occupancy_fraction']<=1 or fo['radiation_points'] not in (1,4,9):
        raise ValueError('Invalid flashover area/radiation settings')
    if fo['criterion'] not in ('temperature', 'temperature_or_flux') or fo['transition_s'] <= 0 or not 0 < fo['decay_fraction'] < 1:
        raise ValueError('Invalid flashover transition settings')
    for rid,cap in fo.get('max_supply_by_room_kW',{}).items():
        if rid not in identifiers or not isinstance(cap,(int,float)) or cap<=0:raise ValueError('Invalid per-room FO supply cap')
    if fo.get('max_supply_kW') is not None and fo['max_supply_kW']<=0:raise ValueError('Invalid prescribed FO supply cap')
    if fo['hrrpua_kW_m2'] is not None and fo['hrrpua_kW_m2'] <= 0:
        raise ValueError('Invalid post-transition HRR per unit area')
    if model['criteria']['fo_temperature_C'] <= model['ambient_C'] or model['criteria']['fo_flux_kW_m2'] <= 0:
        raise ValueError('Invalid flashover thresholds')
    if fo['enabled']:
        for rid in identifiers:
            fuels = [g for g in model['fuel_groups'] if g['room'] == rid]
            if fuels and any(g['formula'] != fuels[0]['formula'] or g['heat_of_combustion_kJ_kg'] != fuels[0]['heat_of_combustion_kJ_kg'] or g['co_yield']!=fuels[0]['co_yield'] for g in fuels):
                raise ValueError('Room fuel pooling requires identical effective fuel chemistry and heat of combustion')
    if min(mat[k] for k in ('conductivity_W_mK','density_kg_m3','specific_heat_kJ_kgK','thickness_m'))<=0:
        raise ValueError('Invalid thermal material properties')
    if mat["pilot"] not in ("none", "assumed") or not 0 < mat["emissivity"] <= 1 or not 0 <= mat["absorptivity"] <= 1:
        raise ValueError("Invalid material/pilot assumption")
    window_targets(model)
    if model.get('execution_profile')=='practical':
        from .practical import bound_execution
        model['spread']=bound_execution(model['spread'], model['duration_s'])
    from .ventilation import validate_ventilation
    validate_ventilation(model)
    from .leakage import apply_minimum_leakage
    apply_minimum_leakage(model)
    return model
