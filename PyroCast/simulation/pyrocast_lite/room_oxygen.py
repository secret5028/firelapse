"""Section 3.0: one integrated oxygen mass per solver room/cell.

The second legacy O2 block exists only in a temporary RHS workspace, never in
the integrated state. No new solver, door-jet reaction, or transition rule.
"""
import numpy as np
from .adapter import LiteModel
from .core import Model,P0,RG,H_O2
from .numerics import bounded,lower


def upper_inventory_reaction(mu,yf,stock,temperature,primary_oxygen_rate,p):
    stoich=p['dHc']/H_O2
    remaining=np.maximum(stock/p['oxygen_inventory_tau_s']-primary_oxygen_rate,0.)
    delta=np.maximum(temperature-273.15-p['gas_ignition_C'],0.)
    thermal=-np.expm1(-np.minimum(delta/p['reaction_temperature_width_K'],30.)**2)
    xi=np.minimum(mu*np.maximum(yf,0.)/p['upper_mixing_time_s'],remaining/stoich)*thermal
    return xi,xi*stoich,xi*p['dHc']


class RoomOxygenModel(LiteModel):
    def __init__(self,model,manifest,parameters):
        p={'door_jet_enabled':False,**parameters,'remove_cumulative_state':False,'oxygen_inventory_mode':True,'oxygen_inventory_tau_s':10.,
           'fresh_air_oxygen_mass_fraction':.23}
        # Stage1 has fixed specified assumptions; no tuning or unrelated options.
        for key in ('oxygen_inventory_tau_s','fresh_air_oxygen_mass_fraction'):
            if key in parameters and parameters[key]!=p[key]:raise ValueError('Stage1 fixed '+key)
        super().__init__(model,manifest,p)
        self.P['oxygen_limit_model']='room_inventory_linear_cap'
        self.contract['oxygen_model']={'kind':'room_inventory_linear_cap','inventory_states':self.N,
            'tau_s':10.,'fresh_air_mass_fraction':.23,'layer_oxygen_states':0,
            'internal_transport':'donor concentration, not fresh-air .23',
            'display':'mO2/m_room mass-ratio proxy; not physical volume fraction',
            'incoming_fuel':'combusts with active prescribed fires only; no door-jet reaction',
            'upper_reaction':'existing temperature condition and fuel mixing20s, shared remaining oxygen cap',
            'atol':'old mass-fraction atol times initial room mass; new state units kg'}

    def keep(self):
        n=self.N
        return np.r_[np.arange(5*n),np.arange(6*n,11*n+1)]

    def compact(self,full):return full[self.keep()]

    def expand(self,state):
        n=self.N
        if state.ndim==1:return np.r_[state[:5*n],np.zeros(n),state[5*n:]]
        return np.concatenate([state[:5*n],np.zeros((n,state.shape[1])),state[5*n:]],axis=0)

    def room_mass(self,full):
        n=self.N;shape=(n,)+(1,)*(full.ndim-1)
        vmin=self.Vmin.reshape(shape);va=self.Va.reshape(shape)
        if self.P.get('smooth_state_bounds'):
            vu=bounded(full[n:2*n],vmin,va-vmin,vmin)
            tu=lower(full[2*n:3*n],200.,.5);tl=lower(full[3*n:4*n],200.,.5)
        else:
            vu=np.clip(full[n:2*n],vmin,va-vmin);tu=np.maximum(full[2*n:3*n],200);tl=np.maximum(full[3*n:4*n],200)
        return P0/RG*(vu/tu+(va-vu)/tl)

    def oxygen_indicator(self,state):
        full=self.expand(state)
        return np.maximum(full[4*self.N:5*self.N],0.)/self.room_mass(full)

    def y0(self):
        y=LiteModel.y0(self);n=self.N
        y[4*n:5*n]=self.P['fresh_air_oxygen_mass_fraction']*self.room_mass(y)
        return self.compact(y)

    def evaluation_atol(self):
        a=LiteModel.integration_atol(self)
        a[4*self.N:5*self.N]=1e-6*P0/(RG*self.P['T_in'])*self.Va
        return a

    def integration_atol(self):return self.compact(self.evaluation_atol())

    def sparsity(self):
        full=LiteModel.sparsity(self);k=self.keep()
        return full[k,:][:,k].tocsr()

    def rhs(self,t,y,diag=False):
        result=Model.rhs(self,t,self.expand(y),diag)
        return result if diag else self.compact(result)

    def result(self):
        y=self.expand(self.sol.y);n=self.N;t=self.sol.t;p=self.P
        vu=np.clip(y[n:2*n],self.Vmin[:,None],self.Va[:,None]-self.Vmin[:,None])
        hl=(self.Va[:,None]-vu)/self.Aa[:,None];tu=y[2*n:3*n];tl=y[3*n:4*n]
        oxygen=self.oxygen_indicator(self.sol.y);fuel=np.maximum(y[6*n:7*n],0.)
        lfl=p['LFL0_hrr']/p['dHc']*np.clip(1-(tu-293)/1300,.2,1.)
        deep=self.Ha[:,None]-hl>=p['d_min']
        flags={'flash':tu>=p['T_fo'],'backdraft':(fuel>=p['Yf_backdraft'])&(oxygen<p['LOC'])&deep,
            'fgi':(fuel>=lfl)&(oxygen>=p['LOC'])&(tu<p['T_ai'])&deep,
            'unten':(hl<p['z_ten'])&(tu>p['T_ten'])}
        rooms=[]
        for i,node in enumerate(self.nodes):
            def first(key):
                hits=np.flatnonzero(flags[key][i]);return float(t[hits[0]]) if len(hits) else None
            rooms.append({'id':node['id'],'name':node['name'],'kind':node['kind'],
                'z_int':hl[i].tolist(),'T_u':(tu[i]-273.15).tolist(),'T_l':(tl[i]-273.15).tolist(),
                'oxygen_room_mass_kg':y[4*n+i].tolist(),'oxygen_room_indicator':oxygen[i].tolist(),
                'Yf_u':fuel[i].tolist(),'t_flashover':first('flash'),'t_backdraft':first('backdraft'),
                't_fgi':first('fgi'),'t_untenable':first('unten')})
        dg=[self.rhs(ts,self.sol.y[:,j],True) for j,ts in enumerate(t)]
        return {'floor':self.floor,'window_broken':{},'fire_room':self.initial_room,'fire':self.fire_info,
            't':t.tolist(),'HRR_kW':[d['Q']/1000 for d in dg],'flame_L':[d['Lf'] for d in dg],
            'flags':flags,'rooms':rooms,'input_issues':self.input_issues,'opening_unit':'percent',
            'ok':bool(self.sol.success),'msg':self.sol.message,'oxygen_model':self.contract['oxygen_model']}
