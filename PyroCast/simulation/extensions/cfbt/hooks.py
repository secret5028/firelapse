"""Project-owned insertion rules. Never edit the upstream CFAST files.

render() returns patched copies plus a reviewable catalog. Actual reaction and
diagnostic implementation lives in fortran/, not in a copied CFAST module.
"""
from pathlib import Path

HERE=Path(__file__).resolve().parent


def rules():
    declarations=(HERE/'fortran/declarations.inc').read_text(encoding='utf-8')
    routines='\n'.join((HERE/'fortran'/name).read_text(encoding='utf-8') for name in ('routines.inc','mixture.inc','radiation_cache.inc'))
    wall_declarations=(HERE/'fortran/wall_cache_declarations.inc').read_text(encoding='utf-8')
    wall_routines=(HERE/'fortran/wall_cache.inc').read_text(encoding='utf-8')
    catalog = [
        ('wall_cache_declarations','conduction.f90','Optional exact wall derivative cache; no accepted-state caching',
         '    public conduction, conductive_flux, cylindrical_conductive_flux\n',
         '    public conduction, conductive_flux, cylindrical_conductive_flux\n'+wall_declarations),
        ('wall_cache_routines','conduction.f90','Project cache stored separately from native conduction formulas',
         '    contains\n','    contains\n'+wall_routines),
        ('wall_cache_key','conduction.f90','Complete conductive_flux input key, including previous profile and trial dt',
         '    real(eb) :: tgrad(2), vtgrad(4*mxrooms), wtemps(nnodes), walldx(nnodes)',
         '    real(eb) :: cfbt_wall_key(8+4*mxslb+2*nnodes)\n    real(eb) :: tgrad(2), vtgrad(4*mxrooms), wtemps(nnodes), walldx(nnodes)'),
        ('wall_cache_call','conduction.f90','Only update=0 is side-effect free; update 1/2 always run original function',
         '            call conductive_flux (update,twint,twext,dt,k_w,c_w,rho_w, &\n'
         '                wtemps,walldx,n_nodes,nslab_w,wfluxin,wfluxout,iwb,tgrad,tderv)',
         '            if (wall_cache_enabled.and.update==0) then\n'
         '                cfbt_wall_key=[twint,twext,dt,wfluxin,wfluxout,real(iwb,eb),real(nslab_w,eb), &\n'
         '                    real(n_nodes,eb),k_w,c_w,rho_w,wtemps,walldx]\n'
         '                if (.not.cfbt_wall_get(iroom,iwall,cfbt_wall_key,tgrad,tderv)) then\n'
         '                    call conductive_flux (update,twint,twext,dt,k_w,c_w,rho_w, &\n'
         '                        wtemps,walldx,n_nodes,nslab_w,wfluxin,wfluxout,iwb,tgrad,tderv)\n'
         '                    call cfbt_wall_put(iroom,iwall,cfbt_wall_key,tgrad,tderv)\n'
         '                end if\n'
         '            else\n'
         '                call conductive_flux (update,twint,twext,dt,k_w,c_w,rho_w, &\n'
         '                    wtemps,walldx,n_nodes,nslab_w,wfluxin,wfluxout,iwb,tgrad,tderv)\n'
         '            end if'),
        ('vertical_source_storage','cfast_structures.f90','Store exact source-layer split for diagnostics',
         '        real(eb) :: mflow(2,2)',
         '        real(eb) :: cfbt_from_mass(2,2) = 0.0_eb ! exact outgoing layer split for vertical diagnostics\n        real(eb) :: mflow(2,2)'),
        ('vertical_reset','flowvertical.f90','Reset the diagnostic split',
         '        ventptr%mflow(1:2,1:2) = 0.0_eb',
         '        ventptr%mflow(1:2,1:2) = 0.0_eb\n        ventptr%cfbt_from_mass = 0.0_eb'),
        ('vertical_record','flowvertical.f90','Record the native source-layer mass flow',
         '            fromtq = fromqu + fromql',
         '            ventptr%cfbt_from_mass(iflow,u) = frommu\n            ventptr%cfbt_from_mass(iflow,l) = fromml\n            fromtq = fromqu + fromql'),
        ('extension_state','fire.f90','Insert project extension declarations',
         '    implicit none\n','    implicit none\n'+declarations),
        ('extension_routines','fire.f90','Insert project reaction and diagnostic procedures',
         '    contains\n','    public cfbt_bulk, cfbt_output, cfbt_schedule, cfbt_gate, cfbt_mixing_rate, cfbt_accept_step\n    public cfbt_rad_get, cfbt_rad_put, cfbt_rad_output, radiation_cache_enabled\n\n    contains\n'+routines),
        ('extension_initialize','fire.f90','Read per-run extension settings',
         '    nfire = 0\n','    nfire = 0\n    call cfbt_initialize\n'),
        ('door_diagnostic_reset','fire.f90','Reset directional door reaction diagnostics',
         '    roominfo(1:n_rooms+1)%qdot_doorjet = 0.0_eb',
         '    roominfo(1:n_rooms+1)%qdot_doorjet = 0.0_eb\n    cfbt_vent_q = 0.0_eb'),
        ('door_diagnostic_record','fire.f90','Record each native door direction separately',
         '                ! sum the flows for return to the source routine\n',
         '                cfbt_vent_q(i,1) = qpyrol2\n                cfbt_vent_q(i,2) = qpyrol1\n\n                ! sum the flows for return to the source routine\n'),
        ('door_temperature_gate','fire.f90','Apply optional project gas-ignition gate',
         '    hrr = 0.0_eb\n    vent_jet_flow_flag = .false.',
         '    hrr = 0.0_eb\n    species_mass_rate = 0.0_eb\n    vent_jet_flow_flag = .false.\n    if (.not.cfbt_vent_allowed(ifrom,ito)) return'),
        ('bulk_import','solve.f90','Import the added bulk reaction source',
         'only: fire, vent_jets,','only: cfbt_schedule, cfbt_bulk, cfbt_accept_step, fire, vent_jets,'),
        ('accepted_step_diagnostic','solve.f90','Count model rate limits only after native accepted steps; no state correction',
         '            call integrate_mass (dt)',
         '            call cfbt_accept_step(dt)\n            call integrate_mass (dt)'),
        ('ignition_boundaries','solve.f90','Stop at the finite ignition-assistance window boundaries',
         '        ! put the discontinuity array into order',
         '        call cfbt_schedule\n\n        ! put the discontinuity array into order'),
        ('bulk_rhs','solve.f90','Add reaction to the existing mass/energy residual',
         '    if (update==all) then\n        if (residprn) then',
         '    call cfbt_bulk(dt,flows_total)\n\n    if (update==all) then\n        if (residprn) then'),
        ('diagnostic_import','outputspreadsheet.f90','Import project diagnostic output',
         'only : flame_height','only : flame_height, cfbt_output, cfbt_rad_output'),
        ('diagnostic_output','outputspreadsheet.f90','Write separate CFBT CSV outputs',
         '    if (radi_verification_flag) call output_spreadsheet_diag(time)',
         '    if (radi_verification_flag) call output_spreadsheet_diag(time)\n    call cfbt_output(time)\n    call cfbt_rad_output(time)'),
        ('radiation_cache_import','radiation.f90','Optional exact RAD4 memoization; native math unchanged',
         'only: flame_height','only: flame_height, cfbt_rad_get, cfbt_rad_put, radiation_cache_enabled'),
        ('radiation_cache_key','radiation.f90','Complete per-room RAD4 inputs; two exact entries per room',
         '    logical black\n    \n    type(room_type)',
         '    logical black\n    real(eb) :: cfbt_rad_key(17+4*mxfires)\n    integer :: cfbt_rad_n\n    \n    type(room_type)'),
        ('radiation_cache_call','radiation.f90','Reuse only bit-identical native inputs; work arrays are not used after this call',
         '        call rad4(twall,tg,emis,rabsorb,i,roomptr%cwidth,roomptr%cdepth,roomptr%cheight,roomptr%depth(l), &\n'
         '            qrfire,xrfire,yrfire,zrfire,nrmfire, &\n'
         '            qflxw,qlay,mxfires,taufl,taufu,firang,roomptr%rad_qout,black)',
         '        if (radiation_cache_enabled) then\n'
         '            cfbt_rad_n=17+4*nrmfire\n'
         '            cfbt_rad_key(1:cfbt_rad_n)=[twall,tg,emis,rabsorb,roomptr%cwidth,roomptr%cdepth,roomptr%cheight, &\n'
         '                roomptr%depth(l),merge(1._eb,0._eb,black),qrfire(1:nrmfire),xrfire(1:nrmfire), &\n'
         '                yrfire(1:nrmfire),zrfire(1:nrmfire)]\n'
         '            if (.not.cfbt_rad_get(i,cfbt_rad_key(1:cfbt_rad_n),qflxw,qlay,roomptr%rad_qout)) then\n'
         '                call rad4(twall,tg,emis,rabsorb,i,roomptr%cwidth,roomptr%cdepth,roomptr%cheight,roomptr%depth(l), &\n'
         '                    qrfire,xrfire,yrfire,zrfire,nrmfire,qflxw,qlay,mxfires,taufl,taufu,firang,roomptr%rad_qout,black)\n'
         '                call cfbt_rad_put(i,cfbt_rad_key(1:cfbt_rad_n),qflxw,qlay,roomptr%rad_qout)\n'
         '            end if\n'
         '        else\n'
         '            call rad4(twall,tg,emis,rabsorb,i,roomptr%cwidth,roomptr%cdepth,roomptr%cheight,roomptr%depth(l), &\n'
         '                qrfire,xrfire,yrfire,zrfire,nrmfire,qflxw,qlay,mxfires,taufl,taufu,firang,roomptr%rad_qout,black)\n'
         '        end if'),
    ]
    adaptive_decl=(HERE/'fortran/adaptive_radiation_declarations.inc').read_text(encoding='utf-8')
    adaptive_code=(HERE/'fortran/adaptive_radiation.inc').read_text(encoding='utf-8')
    # Wrap the existing exact-cache path. Disabled mode executes exactly the
    # old path; adaptive mode never adds another radiation/species source.
    index=next(i for i,r in enumerate(catalog) if r[0]=='radiation_cache_call')
    rule=catalog[index]
    prefix=('        cfbt_weight=0._eb\n'
        '        if (adaptive_radiation_enabled) then\n'
        '            cfbt_rad_n=17+4*nrmfire\n'
        '            cfbt_rad_key(1:cfbt_rad_n)=[twall,tg,emis,rabsorb,roomptr%cwidth,roomptr%cdepth,roomptr%cheight, &\n'
        '                roomptr%depth(l),merge(1._eb,0._eb,black),qrfire(1:nrmfire),xrfire(1:nrmfire), &\n'
        '                yrfire(1:nrmfire),zrfire(1:nrmfire)]\n'
        '            call cfbt_adaptive_evaluate(i,cfbt_rad_key(1:cfbt_rad_n),cfbt_awall,cfbt_alayer,cfbt_aout,cfbt_weight)\n'
        '        end if\n        if (cfbt_weight<1._eb) then\n')
    suffix=('\n        end if\n'
        '        if (cfbt_weight==1._eb) then\n'
        '            qflxw=cfbt_awall;qlay=cfbt_alayer;roomptr%rad_qout=cfbt_aout\n'
        '        else if (cfbt_weight>0._eb) then\n'
        '            qflxw=cfbt_weight*cfbt_awall+(1._eb-cfbt_weight)*qflxw\n'
        '            qlay=cfbt_weight*cfbt_alayer+(1._eb-cfbt_weight)*qlay\n'
        '            roomptr%rad_qout=cfbt_weight*cfbt_aout+(1._eb-cfbt_weight)*roomptr%rad_qout\n'
        '        end if')
    catalog[index]=(*rule[:4],prefix+rule[4]+suffix)
    catalog.extend([
        ('adaptive_config_public','fire.f90','Expose default-off project radiation settings',
         '    public cfbt_rad_get, cfbt_rad_put, cfbt_rad_output, radiation_cache_enabled\n',
         '    public cfbt_rad_get, cfbt_rad_put, cfbt_rad_output, radiation_cache_enabled\n'
         '    public adaptive_radiation_enabled,adaptive_min_age_s,adaptive_stable_s,adaptive_refresh_s\n'),
        ('adaptive_import','radiation.f90','Read project settings without modifying native chemistry',
         'only: flame_height, cfbt_rad_get, cfbt_rad_put, radiation_cache_enabled',
         'only: flame_height, cfbt_rad_get, cfbt_rad_put, radiation_cache_enabled, &\n'
         '        adaptive_radiation_enabled,adaptive_min_age_s,adaptive_stable_s,adaptive_refresh_s'),
        ('adaptive_declarations','radiation.f90','Separate adaptive operator state',
         '    public radiation, absorb, solid_angle_triangle\n',
         '    public radiation, absorb, solid_angle_triangle\n'+adaptive_decl),
        ('adaptive_routines','radiation.f90','Native-derived radiation operator; trial-state smooth fallback',
         '    contains\n','    contains\n'+adaptive_code),
        ('adaptive_work','radiation.f90','Temporary output buffers',
         '    real(eb) :: cfbt_rad_key(17+4*mxfires)\n',
         '    real(eb) :: cfbt_rad_key(17+4*mxfires)\n    real(eb) :: cfbt_weight,cfbt_awall(4),cfbt_alayer(2),cfbt_aout(4)\n'),
        ('adaptive_accept_import','solve.f90','Accepted-step-only operator commits',
         'use radiation_routines, only: radiation\n',
         'use radiation_routines, only: radiation, cfbt_adaptive_accept\n'),
        ('adaptive_accept','solve.f90','Commit only after native event rollback/reintegration is complete',
         '            call cfbt_accept_step(dt)\n',
         '            call cfbt_adaptive_accept(t,dt)\n            call cfbt_accept_step(dt)\n'),
        ('adaptive_diagnostic_import','outputspreadsheet.f90','Separate experiment diagnostics',
         'module spreadsheet_routines\n\n    use precision_parameters',
         'module spreadsheet_routines\n    use radiation_routines, only: cfbt_adaptive_output\n\n    use precision_parameters'),
        ('adaptive_diagnostic_output','outputspreadsheet.f90','Audit activations, reversions and radiation closure',
         '    call cfbt_rad_output(time)\n','    call cfbt_rad_output(time)\n    call cfbt_adaptive_output(time)\n'),
    ])
    return catalog


def render(originals):
    """Exact one-anchor patches against the pinned release; fail on drift."""
    patched=dict(originals);catalog=[]
    for identity,filename,purpose,old,new in rules():
        if filename not in patched or patched[filename].count(old)!=1:
            raise ValueError('Pinned CFAST hook anchor changed: '+identity)
        patched[filename]=patched[filename].replace(old,new,1)
        catalog.append({'id':identity,'upstream_file':filename,'purpose':purpose,
                        'anchor':old,'replacement':new})
    return patched,catalog
