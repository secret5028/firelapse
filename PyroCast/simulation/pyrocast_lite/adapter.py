"""L1 adapter over frozen r8 preparation; no native execution or plate evaluation."""
from copy import deepcopy
import hashlib
import json
import math
import numpy as np
from .core import Model, PRM, P0, RG
from pyrocast_cfbt.room_rule_r8 import prepare as prepare_r8
from .shared_inputs import read_shared, FiniteWalls


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def prepare(raw, parameters=None):
    # Preserve the r8 manifest and curves exactly, including future vent caps.
    # Window breakage is disabled in the lite dynamics, NOT silently in the
    # native supply compiler. Its cap may therefore overestimate available air.
    if raw.get('cell_mode','legacy')!='legacy':raise ValueError('Only legacy cell partition is supported')
    model, _, manifest = prepare_r8(deepcopy(raw))
    if parameters and parameters.get('oxygen_inventory_mode'):
        raise ValueError('Room oxygen inventory mode has been removed')
    return LiteModel(model, manifest, parameters), manifest


class LiteModel(Model):
    def __init__(self, model, manifest, parameters=None):
        self.runtime_parameters = deepcopy(parameters)
        self.input_model = model
        self.manifest = manifest
        self.manifest_sha256 = digest(manifest)
        self.shared = read_shared(model)
        if parameters and set(parameters)&{'T_in','T_out','kpc','eps','chi_r','dHc','door_leak','win_leak','Cd','oxygen_limit_model','native_lower_oxygen_limit_mass'}:
            raise ValueError('Shared physical parameters must come from the native deck')
        first_mat=self.shared['materials_by_room'][model['rooms'][0]['id']]['wall']
        fuel_values=list(self.shared['fuels_by_room'].values())
        if len({f['heat_of_combustion_J_kg'] for f in fuel_values})!=1:
            raise ValueError('L1 legacy FGI condition needs a common Hc; mixed-Hc condition model is not implemented')
        self.P = {**PRM, 'pyro_feedback': False,
                  'T_in': self.shared['interior_K'], 'T_out': self.shared['exterior_K'],
                  'kpc':first_mat['kpc'],'eps':first_mat['EMISSIVITY'],
                  'chi_r':fuel_values[0]['radiative_fraction'],
                  'dHc':fuel_values[0]['heat_of_combustion_J_kg'],
                  'door_leak':0.,'win_leak':0.,
                  'Cd':0.70,'oxygen_limit_model':'native_mass_tanh',
                  'native_lower_oxygen_limit_mass':self.shared['native_LOL_mass'],
                  'gas_radiation_enabled':False,'remove_cumulative_state':True,
                  'smooth_state_bounds':False,'upper_combustion_enabled':False,
                  'upper_mixing_time_s':20.,
                  'door_jet_enabled':True,'door_jet_mixing_time_s':10.,'door_jet_onset_delta_K':200.,
                  'gas_ignition_C':model.get('gas',{}).get('gas_ignition_C'),
                  'reaction_temperature_width_K':.5,
                  **(parameters or {})}
        if self.P['upper_combustion_enabled'] and (self.P['gas_ignition_C'] is None or not math.isfinite(self.P['gas_ignition_C'])):
            raise ValueError('Upper reaction requires shared gas.gas_ignition_C')
        if not math.isfinite(self.P['upper_mixing_time_s']) or self.P['upper_mixing_time_s']<=0:
            raise ValueError('Positive finite mixing time required')
        if not isinstance(self.P['door_jet_enabled'],bool) or not math.isfinite(self.P['door_jet_mixing_time_s']) or self.P['door_jet_mixing_time_s']<=0:
            raise ValueError('Door jet requires a boolean switch and positive finite mixing time')
        if not isinstance(self.P['gas_radiation_enabled'],bool):
            raise ValueError('gas_radiation_enabled must be boolean')
        if self.P['pyro_feedback']:
            raise ValueError('L1 r8 supply mode requires pyro_feedback=False')
        self.floor = model.get('floor', 'selected_floor')
        self.nodes = []
        for r in model['rooms']:
            w, d, h = r['size_m']
            self.nodes.append(dict(id=r['id'], name=r.get('name', r['id']),
                                   kind=r.get('core_kind') or 'room',
                                   zf=r['origin_m'][2], H=h, A=w*d,
                                   per=2*(w+d)))
        self.N = len(self.nodes)
        self.rmap = {n['id']: i for i, n in enumerate(self.nodes)}
        self.zfa = np.array([n['zf'] for n in self.nodes])
        self.Ha = np.array([n['H'] for n in self.nodes])
        self.Aa = np.array([n['A'] for n in self.nodes])
        self.Va = self.Aa*self.Ha
        self.pera = np.array([n['per'] for n in self.nodes])
        self.Vmin = np.maximum(.001*self.Va, .005)
        self.rho_out = P0/(RG*self.P['T_out'])
        self.vents = []
        self.omitted_vertical = []
        for v in model['openings']:
            if v.get('type') == 'FLOOR':
                raise ValueError('L1 floor-only adapter cannot approximate FLOOR vents as WALL vents')
            schedule = v.get('schedule', [[0., 1.]])
            if any(row[1] != schedule[0][1] for row in schedule):
                raise ValueError('L1 openings must have fixed initial states')
            a, b = v['a'], v['b']
            if a == 'OUTSIDE':
                raise ValueError('Expected normalized native opening with interior a-side')
            i, j = self.rmap[a], self.rmap.get(b, self.N)
            if b != 'OUTSIDE' and b not in self.rmap:
                raise ValueError('Unknown opening endpoint: '+b)
            height = v['top_m']-v.get('bottom_m', 0.)
            if height <= 0 or v['width_m'] <= 0:
                raise ValueError('Invalid WALL vent dimensions')
            from pyrocast_cfbt.openings import is_window
            kind = 'window' if is_window(v) else 'door'
            leak = 0.  # Native leakage is a separate room-to-outside connection.
            # Schedules already contain the window 50% effective opening.
            self.vents.append([i, j, v['width_m'], self.zfa[i]+v.get('bottom_m',0.),
                               self.zfa[i]+v['top_m'], v['id'], kind,
                               schedule[0][1], leak/height])
        for leak in self.shared['leak_vents']:
            i=self.rmap[leak['room']]
            self.vents.append([i,self.N,leak['width'],self.zfa[i]+leak['bottom'],
                self.zfa[i]+leak['top'],'LEAK_'+leak['kind']+'_'+leak['room'],
                'native_compartment_leak',1.,0.])
        self.mechanical_flows={}
        for vent in model.get('mechanical_vents',[]):
            i=self.rmap[vent['comp']];index=len(self.vents)
            self.mechanical_flows[index]=vent
            self.vents.append([i,self.N,1.,self.zfa[i],self.zfa[i]+1.,vent['id'],'mechanical',1.,0.])
        V = self.vents
        self.vi = np.array([v[0] for v in V], int)
        self.vj = np.array([v[1] for v in V], int)
        self.vw = np.array([v[2] for v in V], float)
        self.vp0 = np.array([v[7] for v in V], float)
        self.vl = np.array([v[8] for v in V], float)
        physical={v['id'] for v in model['openings'] if v.get('type','WALL')=='WALL'
                  and v['b']!='OUTSIDE' and not v.get('virtual_cell_boundary',False)}
        self.door_jet_eligible=np.array([v[5] in physical for v in V],bool)
        # Only open paths fix a component's pressure reference to the exterior.
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components
        active = (self.vw*self.vp0+(1-self.vp0)*self.vl)>0
        graph = coo_matrix((np.ones(active.sum()),(self.vi[active],self.vj[active])),
                           shape=(self.N+1,self.N+1))
        _, component = connected_components(graph, directed=False)
        degree = np.asarray((graph+graph.T).tocsr().getnnz(axis=1))
        self.sealed_pressure_rooms = []
        for i in np.unique(component[:self.N]):
            if i==component[self.N]:
                continue
            rooms = np.flatnonzero(component==i)
            reference = rooms[np.argmin(degree[rooms])]
            self.sealed_pressure_rooms.append((rooms,reference))
        self.wb = np.array([], int); self.nb = 0; self.Tb = 0.
        bottom = np.array([v[3] for v in V]); top = np.array([v[4] for v in V])
        ns = self.P['n_slab']; fraction = (np.arange(ns)+.5)/ns
        self.Z = bottom[:,None]+(top-bottom)[:,None]*fraction[None,:]
        self.dZ = (top-bottom)[:,None]/ns*np.ones((1,ns))
        for index,vent in self.mechanical_flows.items():
            self.Z[index,:]=self.zfa[self.vi[index]]+vent['height']
        self.groups = deepcopy(model['fuel_groups'])
        if len({g['room'] for g in self.groups}) != len(self.groups):
            raise ValueError('L1 requires at most one fire per solver room')
        self.by_room = {g['room']: g for g in self.groups}
        self.activation = {g['room']: float(g['initial_time_s'])
                           for g in self.groups if 'initial_time_s' in g}
        self.events_log = []
        self.pending = {g['room'] for g in self.groups if 'initial_time_s' not in g}
        self.initial_room = manifest['initial_source']['room']
        self.ig = self.rmap[self.initial_room]
        self.plume_k = 1
        self.fire_point = None
        self.fire_info = {'room': self.initial_room, 'basis': 'r8 prescribed curves'}
        self.input_issues = {'vertical_zones': 'off; floor-only', 'window_breakage': 'off',
                             'legacy_pyro_feedback': 'off'}
        self.curves = {}
        for g in self.groups:
            c = g['room_rule_curve']
            times = np.array(c['t'], float); q = np.array(c['q'], float)*1000
            if np.any(np.diff(times) <= 0):
                raise ValueError('Supply curve times must strictly increase')
            height = g.get('solver_position_m',g['position_m'])[2]-self.zfa[self.rmap[g['room']]]
            if not 0 <= height < self.Ha[self.rmap[g['room']]]:
                raise ValueError('Invalid fire height')
            chemical=self.shared['fuels_by_room'][g['room']]
            self.curves[g['room']] = (times, q, chemical['heat_of_combustion_J_kg'],
                                      chemical['radiative_fraction'], height)
        self.finite_walls=FiniteWalls(self,self.shared)
        self.contract = {'parents_identical': manifest['parents'] == model['room_fire_rule']['parent_map'],
                         'curve_hashes': {g['room']: digest(g['room_rule_curve']) for g in self.groups},
                         'r8_manifest_sha256': self.manifest_sha256,
                         'no_plate_states': True, 'native_run_count': 0,
                         'trigger_basis': {'inter_room': 'upper_layer_temperature',
                                           'cell': 'upper_layer_temperature'},
                         'inactive_settings': [],
                         'window_supply_cap_note': 'r8 cap retained; dynamic breakage disabled'}
        self.contract['shared_input_deck_sha256']=self.shared['deck_sha256']
        self.contract['wall_model']='one_node_per_ceiling_wall_floor'
        self.contract['cumulative_state_removed']=bool(self.P.get('remove_cumulative_state'))
        self.contract['door_jet']={'enabled':self.P['door_jet_enabled'],
            'oxygen_basis':'receiving lower layer, shared budget across jets after plume withdrawal',
            'mixing_time_s':self.P['door_jet_mixing_time_s'],
            'ignition_source_K':'interior ambient +200K; CFAST input_namelist.f90:284',
            'scope':'internal physical WALL vents only; exterior, leaks, virtual cell interfaces excluded',
            'assumption':'inventory-rate cap replaces CFAST vent-plume air entrainment; no flame/CO-resolved chemistry',
            'heat_destination':'receiving upper layer; oxygen/products stay in lower-layer species ledger; no extra mass entrainment'}
        self.contract['gas_radiation']={'enabled':self.P['gas_radiation_enabled'],
            'kappa_upper_m_inv':0.50,'basis':'CFAST defabsup when fgasabsorb OFF; not species-dependent absorb()',
            'lower_absorption':False,'wall_temperature':'one capacity node, surface-temperature approximation',
            'legacy_gas_wall_radiation_replaced_not_added':True}

    def y0(self):
        gas=super().y0()
        for rooms,reference in self.sealed_pressure_rooms:
            gas[rooms] -= gas[reference]
        if self.P.get('remove_cumulative_state'):gas=np.delete(gas,8*self.N)
        return np.concatenate([gas,np.full(3*self.N,self.P['T_in'])])

    def integration_atol(self):
        n=self.N
        atol=np.concatenate([np.full(n,1e-3),self.Vmin*.1,np.full(2*n,.05),
            np.full(4*n,1e-6),[1e3],np.full(3*n,.05)])
        return np.delete(atol,8*n) if self.P.get('remove_cumulative_state') else atol

    def sparsity(self):
        from scipy.sparse import lil_matrix
        if self.P.get('remove_cumulative_state'):
            n=self.N;off=8*n
            adjacency=np.eye(n,dtype=bool)
            for i,j in zip(self.vi,self.vj):
                if j<n:adjacency[i,j]=adjacency[j,i]=True
            matrix=lil_matrix((11*n,11*n),dtype=bool)
            for a in range(8):
                for b in range(8):matrix[a*n:(a+1)*n,b*n:(b+1)*n]=adjacency
            for i in range(n):
                gas=[a*n+i for a in range(8)]
                walls=list(range(off+3*i,off+3*i+3))
                for w in walls:
                    matrix[w,w]=True
                    for g in gas:matrix[w,g]=True;matrix[g,w]=True
        else:
            base=super().sparsity();off=8*self.N+1
            matrix=lil_matrix((off+3*self.N,off+3*self.N),dtype=bool)
            matrix[:off,:off]=base
            for i in range(self.N):
                gas=[a*self.N+i for a in range(8)]+[8*self.N]
                walls=list(range(off+3*i,off+3*i+3))
                for w in walls:
                    matrix[w,w]=True
                    for g in gas:matrix[w,g]=True;matrix[g,w]=True
        for rooms,reference in self.sealed_pressure_rooms:
            columns=matrix.rows[reference][:]
            for room in rooms:
                matrix[room,columns]=True
        return matrix.tocsr()

    def fire_sources(self, t, E):
        result = []
        for room, at in self.activation.items():
            if t < at:
                continue
            times, q, hoc, chi, height = self.curves[room]
            supply = float(np.interp(t-at, times, q, left=0., right=0.))
            if supply > 0:
                result.append((self.rmap[room], supply, hoc, chi, 1, height))
        return result

    def key(self, room):
        p = self.manifest['parents'][room]
        return p['trigger_kind'], p['room']

    def trigger_value(self, key, t, y):
        kind, parent = key; i = self.rmap[parent]
        setting = 'cell_temperature_C' if kind == 'cell_flame' else 'temperature_C'
        return y[2*self.N+i]-273.15-self.manifest['rule_settings']['values'][setting]

    def activate(self, key, t):
        for room in sorted(list(self.pending)):
            if self.key(room) != key:
                continue
            parent = self.manifest['parents'][room]
            self.activation[room] = float(t)  # curve already contains delay
            self.pending.remove(room)
            self.events_log.append({'room': room, 'parent': parent['room'],
                'condition_time_s': float(t), 'delay_s': parent['delay_s'],
                'supply_start_s': float(t+parent['delay_s']),
                'trigger_basis': 'upper_layer_temperature',
                'threshold_C': self.manifest['rule_settings']['values'][
                    'cell_temperature_C' if key[0]=='cell_flame' else 'temperature_C']})
