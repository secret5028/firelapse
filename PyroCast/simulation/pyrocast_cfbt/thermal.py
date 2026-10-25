"""Passive one-dimensional material response, separate from gas combustion."""
import math
import numpy as np

SIGMA=5.670374419e-8


def plate(material,t,qfront,qback,gasfront,gasback,initial_C=20.,nodes=49,dt=.05,normal_z=0.):
    if nodes<3 or dt<=0:
        raise ValueError('Invalid plate integration settings')
    k=material['conductivity_W_mK']; rc=material['density_kg_m3']*material['specific_heat_kJ_kgK']*1000
    dx=material['thickness_m']/(nodes-1)
    if min(k,rc,dx)<=0:
        raise ValueError('Invalid material properties')
    alpha=material['absorptivity']; eps=material['emissivity']
    convection_coefficient=1.52 if abs(normal_z)>=math.sqrt(.5) else 1.31
    temp=np.full(nodes,initial_C+273.15); surface=[initial_C]; absorbed=[0.]
    cumulative=0.; crossing=None; integrated_net=0.
    initial_energy=rc*dx*(temp.sum()-.5*temp[0]-.5*temp[-1])
    for i in range(1,len(t)):
        interval=t[i]-t[i-1]
        maxT=max(temp.max(),gasfront[i]+273.15,gasback[i]+273.15,300.)
        surface_derivative=4*eps*SIGMA*maxT**3+3*convection_coefficient*maxT**(1/3)
        stable=.8/(2*k/(rc*dx*dx)+2*surface_derivative/(rc*dx))
        steps=math.ceil(interval/min(dt,stable)); step=interval/steps
        for j in range(steps):
            fraction=(j+.5)/steps
            interpolate=lambda a:(1-fraction)*a[i-1]+fraction*a[i]
            front=interpolate(qfront)*1000; back=interpolate(qback)*1000
            delta=interpolate(gasfront)-(temp[0]-273.15)
            delta_b=interpolate(gasback)-(temp[-1]-273.15)
            net=alpha*front-eps*SIGMA*temp[0]**4+convection_coefficient*abs(delta)**(1/3)*delta
            net_b=alpha*back-eps*SIGMA*temp[-1]**4+convection_coefficient*abs(delta_b)**(1/3)*delta_b
            derivative=np.zeros(nodes)
            derivative[1:-1]=k/(rc*dx*dx)*(temp[:-2]-2*temp[1:-1]+temp[2:])
            derivative[0]=2*(net+k*(temp[1]-temp[0])/dx)/(rc*dx)
            derivative[-1]=2*(net_b+k*(temp[-2]-temp[-1])/dx)/(rc*dx)
            before=temp[0]-273.15
            temp+=step*derivative
            integrated_net+=step*(net+net_b)
            cumulative+=step*alpha*front/1000
            now=temp[0]-273.15
            if crossing is None and before<material['ignition_C']<=now:
                crossing=float(t[i-1]+(j+(material['ignition_C']-before)/(now-before))*step)
        surface.append(float(temp[0]-273.15)); absorbed.append(cumulative)
        if not np.isfinite(temp).all() or temp.min()<=0:
            raise ValueError('Unstable plate solution')
    residual=rc*dx*(temp.sum()-.5*temp[0]-.5*temp[-1])-initial_energy-integrated_net
    if abs(residual)>max(.01,abs(integrated_net)*1e-9):
        raise ValueError('Plate heat budget did not close')
    return {'surface_C':np.array(surface),'crossing_s':crossing,'absorbed_kJ_m2':np.array(absorbed),
            'energy_residual_kJ_m2':residual/1000}


def crossing_value(t,y,threshold):
    hits=np.flatnonzero(y>=threshold)
    if not len(hits): return None
    i=int(hits[0])
    if i==0:return float(t[0])
    return float(t[i-1]+(threshold-y[i-1])/(y[i]-y[i-1])*(t[i]-t[i-1]))


# Optional compiled evaluation of the identical explicit plate update; Python stays the reference.
_plate_python=plate
_plate_library=None

def plate(material,t,qfront,qback,gasfront,gasback,initial_C=20.,nodes=49,dt=.05,normal_z=0.):
    global _plate_library
    from pathlib import Path
    import ctypes
    library=Path(__file__).resolve().parents[1]/'build/plate.dll'
    if not library.is_file():return _plate_python(material,t,qfront,qback,gasfront,gasback,initial_C,nodes,dt,normal_z)
    if nodes<3 or dt<=0:raise ValueError('Invalid plate integration settings')
    k=material['conductivity_W_mK'];rc=material['density_kg_m3']*material['specific_heat_kJ_kgK']*1000;dx=material['thickness_m']/(nodes-1)
    if min(k,rc,dx)<=0:raise ValueError('Invalid material properties')
    if _plate_library is None:
        dll=ctypes.CDLL(str(library));pointer=np.ctypeslib.ndpointer(dtype=np.float64,ndim=1,flags='C_CONTIGUOUS')
        dll.plate_run.argtypes=[ctypes.c_int,ctypes.c_int]+[pointer]*5+[ctypes.c_double]*9+[pointer]*2+[ctypes.POINTER(ctypes.c_double)]*2
        dll.plate_run.restype=ctypes.c_int;_plate_library=dll
    values=[np.ascontiguousarray(a,dtype=np.float64) for a in (t,qfront,qback,gasfront,gasback)];n=len(values[0])
    if not all(len(a)==n for a in values):raise ValueError('Misaligned plate inputs')
    surface=np.empty(n);absorbed=np.empty(n);cross=ctypes.c_double();residual=ctypes.c_double()
    conv=1.52 if abs(normal_z)>=math.sqrt(.5) else 1.31
    code=_plate_library.plate_run(n,nodes,*values,k,rc,dx,material['absorptivity'],material['emissivity'],material['ignition_C'],initial_C,dt,conv,surface,absorbed,ctypes.byref(cross),ctypes.byref(residual))
    if code:raise ValueError('Compiled plate integration failed: '+str(code))
    return {'surface_C':surface,'crossing_s':None if math.isnan(cross.value) else cross.value,
            'absorbed_kJ_m2':absorbed,'energy_residual_kJ_m2':residual.value/1000}
