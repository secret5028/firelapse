
    subroutine cfbt_initialize
    use setup_data, only: datapath, project
    use solver_data, only: stpmax
    use conduction_routines, only: wall_cache_enabled
    integer :: unit, ios
    logical :: exists
    namelist /CFBT/ mixture_enabled, jet_enabled, enabled, bulk_enabled, vent_gate_enabled, room_enabled, gas_ignition_C, hot_C, &
        oxygen_min_vol, fuel_min_mass_fraction, rate_ref_s_inv, reference_K, activation_J_mol, &
        vent_ignition_C, pilot_assumed, pilot_start_s, pilot_end_s, &
        force_room, force_time_s, force_duration_s, force_rate_s_inv, force_o2_min_vol, &
        mixture_smooth_enabled, mixture_o2_width_vol, mixture_temperature_width_C, mixture_fuel_width, mixture_mixing_time_s, &
        radiation_cache_enabled,wall_cache_enabled,adaptive_radiation_enabled, &
        adaptive_min_age_s,adaptive_stable_s,adaptive_refresh_s
    if (cfbt_loaded) return
    cfbt_loaded=.true.
    inquire(file=trim(datapath)//trim(project)//'.cfbt',exist=exists)
    if (.not.exists) return
    open(newunit=unit,file=trim(datapath)//trim(project)//'.cfbt',status='old',action='read',iostat=ios)
    if (ios/=0) error stop 'CFBT sidecar could not be opened'
    read(unit,nml=CFBT,iostat=ios)
    close(unit)
    if (ios/=0) error stop 'Invalid CFBT sidecar'
    if (adaptive_radiation_enabled.and.min(adaptive_min_age_s,adaptive_stable_s,adaptive_refresh_s)<=0._eb) &
        error stop 'Adaptive radiation requires positive age, stability and refresh times'
    if (.not.enabled) return
    if (mixture_smooth_enabled) then
        if (.not.mixture_enabled) error stop 'Smooth mixture requires mixture mode'
        if (min(mixture_o2_width_vol,mixture_temperature_width_C,mixture_fuel_width)<=0._eb) &
            error stop 'Positive mixture transition widths required'
        if (mixture_mixing_time_s<=0._eb.or.stpmax<=0._eb.or.stpmax>mixture_mixing_time_s) &
            error stop 'Mixture requires 0 < MAX_TIME_STEP <= mixing time'
    end if
    if (force_room<0.or.force_room>n_rooms.or.force_duration_s<=0._eb.or.force_rate_s_inv<0._eb) &
        error stop 'Invalid CFBT ignition window'
    if (oxygen_min_vol<=0._eb.or.oxygen_min_vol>=1._eb.or.rate_ref_s_inv<0._eb.or. &
        reference_K<=0._eb.or.activation_J_mol<0._eb.or.fuel_min_mass_fraction<0._eb) error stop 'Invalid CFBT parameters'
    if (vent_gate_enabled) tgignt=vent_ignition_C+273.15_eb
    end subroutine cfbt_initialize

    subroutine cfbt_schedule
    use solver_data, only: discon, ndisc
    use cparams, only: mxdiscon
    call cfbt_initialize
    if (.not.enabled.or..not.bulk_enabled.or.force_room==0) return
    if (ndisc+2>mxdiscon) error stop 'No room for CFBT ignition boundaries'
    discon(ndisc)=force_time_s
    discon(ndisc+1)=force_time_s+force_duration_s
    ndisc=ndisc+2
    end subroutine cfbt_schedule

    real(eb) function cfbt_oxygen_vol(iroom,layer) result(value)
    integer, intent(in) :: iroom,layer
    real(eb) :: mol, sm(ns)
    sm=max(0._eb,roominfo(iroom)%species_mass(layer,:))
    ! Gas-phase moles only: soot and diagnostic potential-product tracers excluded.
    mol=sm(n2)/.02802_eb+sm(o2)/.032_eb+sm(co2)/.04401_eb+sm(co)/.02801_eb+ &
        sm(hcn)/.027028_eb+sm(hcl)/.036458_eb+sm(h2o)/.018016_eb+sm(fuel_moles)
    value=0._eb
    if (mol>0._eb) value=(sm(o2)/.032_eb)/mol
    end function cfbt_oxygen_vol

    logical function cfbt_vent_allowed(ifrom,ito) result(allowed)
    integer, intent(in) :: ifrom,ito
    allowed=.true.
    if (.not.enabled.or..not.vent_gate_enabled) return
    allowed=roominfo(ifrom)%temp(u)>=vent_ignition_C+273.15_eb.and. &
        roominfo(ifrom)%species_fraction(u,fuel)>=fuel_min_mass_fraction.and. &
        cfbt_oxygen_vol(ito,l)>=oxygen_min_vol
    end function cfbt_vent_allowed

    subroutine cfbt_legacy_bulk(step,flows)
    use solver_data, only: i_speciesmap
    use setup_data, only: stime
    real(eb), intent(in) :: step
    real(eb), intent(inout) :: flows(mxrooms,ns+2,2)
    real(eb) :: mf, mo, mf_left, mo_left, horizon, k_rate, rate, entrainment, hoc, mw, xo, yo
    real(eb) :: ys, yc, yhcn, nu_s, nu_c, nu_hcn, nu_hcl, nu_co2, nu_h2o, nu_o2
    real(eb) :: nc, nh, no, nn, ncl, released, burned, ratio, xmass(ns), available(ns), factor
    integer :: i, p, j
    logical :: ignition, forced
    cfbt_q=0._eb; cfbt_burn=0._eb; cfbt_o2_used=0._eb
    if (.not.enabled.or..not.bulk_enabled) return
    horizon=max(abs(step),1.e-5_eb)
    do i=1,n_rooms
        if (.not.room_enabled(i)) cycle
        mf=max(0._eb,roominfo(i)%species_mass(u,fuel))
        mo=max(0._eb,roominfo(i)%species_mass(u,o2))
        if (mf<=1.e-12_eb.or.mo<=1.e-12_eb) cycle
        if (roominfo(i)%species_mass(u,fuel_moles)<=1.e-12_eb.or.roominfo(i)%species_mass(u,fuel_Q)<=0._eb) cycle
        xo=cfbt_oxygen_vol(i,u)
        forced=i==force_room.and.stime>=force_time_s.and.stime<force_time_s+force_duration_s
        if (xo<merge(force_o2_min_vol,oxygen_min_vol,forced).or.roominfo(i)%species_fraction(u,fuel)<fuel_min_mass_fraction) cycle
        ignition=roominfo(i)%temp(u)>=gas_ignition_C+273.15_eb
        ignition=ignition.or.forced
        if (pilot_assumed.and.stime>=pilot_start_s.and.stime<=pilot_end_s) &
            ignition=ignition.or.roominfo(i)%temp(u)>=hot_C+273.15_eb
        if (.not.ignition) cycle
        available=roominfo(i)%species_mass(u,:)
        ! Reserve the net native outgoing consumption before using the same pool.
        do p=3,ns+2
            j=i_speciesmap(p)-2
            if (j>=1.and.j<=ns) available(j)=max(0._eb,available(j)+min(0._eb,horizon*flows(i,p,u)))
        end do
        mf_left=available(fuel); mo_left=available(o2)
        if (mf_left<=0._eb.or.mo_left<=0._eb) cycle
        hoc=roominfo(i)%species_mass(u,fuel_Q)/mf
        mw=mf/roominfo(i)%species_mass(u,fuel_moles)
        ys=roominfo(i)%species_mass(u,fuel_soot)/mf
        yc=roominfo(i)%species_mass(u,fuel_co)/mf
        yhcn=roominfo(i)%species_mass(u,fuel_hcn)/mf
        nu_s=ys*mw/.01201_eb; nu_c=yc*mw/.02801_eb; nu_hcn=yhcn*mw/.027028_eb
        nu_hcl=roominfo(i)%species_mass(u,fuel_hcl)/mf*mw/.036458_eb
        nu_co2=roominfo(i)%species_mass(u,fuel_co2)/mf*mw/.04401_eb
        nu_h2o=roominfo(i)%species_mass(u,fuel_h2o)/mf*mw/.018016_eb
        nu_o2=roominfo(i)%species_mass(u,fuel_o2)/mf*mw/.032_eb
        nn=nu_hcn+2._eb*roominfo(i)%species_mass(u,fuel_n2)/mf*mw/.02802_eb
        ncl=nu_hcl; nh=2._eb*nu_h2o+nu_hcn+nu_hcl
        nc=nu_co2+nu_hcn+nu_c+nu_s; no=max(0._eb,2._eb*nu_co2-2._eb*nu_o2+nu_h2o+nu_c)
        ! Project exploration profile, not claimed as the exact Kudo coefficient fit.
        k_rate=rate_ref_s_inv*exp(min(40._eb,activation_J_mol/8.314462618_eb* &
            (1._eb/reference_K-1._eb/roominfo(i)%temp(u))))*(xo/.12_eb)
        if (forced) k_rate=force_rate_s_inv*(xo/.12_eb)
        rate=min(mf*k_rate,mf_left/horizon)
        yo=roominfo(i)%species_fraction(u,o2)
        entrainment=mo_left/(horizon*max(yo,1.e-12_eb))
        xmass=0._eb
        call chemistry(rate,mw,entrainment,hoc,ys,ys,0._eb,yc,yhcn,nc,nh,no,nn,ncl,yo,0._eb,released,burned,xmass)
        if (burned<=0._eb) cycle
        factor=1._eb
        if (-xmass(o2)*horizon>mo_left) factor=mo_left/(-xmass(o2)*horizon)
        xmass=xmass*factor; burned=burned*factor; released=released*factor
        ratio=burned/mf
        xmass(fuel_moles:ns)=-ratio*roominfo(i)%species_mass(u,fuel_moles:ns)
        do p=3,ns+2
            j=i_speciesmap(p)-2
            if (j>=1.and.j<=ns) flows(i,p,u)=flows(i,p,u)+xmass(j)
        end do
        ! Heat enters the gas equation; native layer emission computes radiation feedback.
        flows(i,q,u)=flows(i,q,u)+released
        cfbt_q(i)=released; cfbt_burn(i)=burned; cfbt_o2_used(i)=-xmass(o2)
    end do
    end subroutine cfbt_legacy_bulk

    subroutine cfbt_output(time)
    use setup_data, only: datapath, project
    use vent_data, only: n_vvents, vventinfo
    real(eb), intent(in) :: time
    integer :: i,a,b,j,source,destination,layer,direction
    real(eb) :: flow,area,rho,velocity,zmid
    call cfbt_extra_output(time)
    if (.not.enabled) return
    if (cfbt_room_unit==0) then
        open(newunit=cfbt_room_unit,file=trim(datapath)//trim(project)//'_cfbt_rooms.csv',status='replace')
        write(cfbt_room_unit,'(a)') 'time_s,room_index,T_upper_C,T_lower_C,interface_m,o2_upper_vol,o2_lower_vol,'// &
            'fuel_upper_kg,fuel_lower_kg,fuel_upper_J,bulk_HRR_W,bulk_burn_kg_s,bulk_o2_kg_s,k_upper_m_inv,'// &
            'k_lower_m_inv,floor_K,lower_wall_K,upper_wall_K,ceiling_K,upper_mass_kg,lower_mass_kg,'// &
            'floor_pressure_Pa,rho_upper_kg_m3,rho_lower_kg_m3'
        open(newunit=cfbt_vent_unit,file=trim(datapath)//trim(project)//'_cfbt_vents.csv',status='replace')
        write(cfbt_vent_unit,'(a)') 'time_s,vent_index,room_from,room_to,HRR_W,upper_stream_kg_s,fuel_stream_kg_s,'// &
            'entrained_air_kg_s,entrained_o2_kg_s'
        open(newunit=cfbt_slab_unit,file=trim(datapath)//trim(project)//'_cfbt_slabs.csv',status='replace')
        write(cfbt_slab_unit,'(a)') 'time_s,vent_index,room_from,room_to,source_layer,bottom_m,top_m,'// &
            'mass_kg_s,volume_m3_s,mean_velocity_m_s,o2_kg_s,fuel_kg_s,soot_kg_s,temperature_C,co_kg_s,chemical_W'
    end if
    do i=1,n_rooms
        write(cfbt_room_unit,'(es24.16,",",i0,22(",",es24.16))') time,i,roominfo(i)%temp(u)-273.15_eb, &
            roominfo(i)%temp(l)-273.15_eb,roominfo(i)%depth(l),cfbt_oxygen_vol(i,u),cfbt_oxygen_vol(i,l), &
            roominfo(i)%species_mass(u,fuel),roominfo(i)%species_mass(l,fuel),roominfo(i)%species_mass(u,fuel_Q), &
            cfbt_q(i),cfbt_burn(i),cfbt_o2_used(i),roominfo(i)%absorb(u),roominfo(i)%absorb(l), &
            roominfo(i)%t_surfaces(1,4),roominfo(i)%t_surfaces(1,3),roominfo(i)%t_surfaces(1,2), &
            roominfo(i)%t_surfaces(1,1),roominfo(i)%rho(u)*roominfo(i)%volume(u), &
            roominfo(i)%rho(l)*roominfo(i)%volume(l),roominfo(i)%relp,roominfo(i)%rho(u),roominfo(i)%rho(l)
    end do
    do i=1,n_hvents
        a=hventinfo(i)%room1; b=hventinfo(i)%room2
        write(cfbt_vent_unit,'(es24.16,3(",",i0),5(",",es24.16))') time,i,a,b,cfbt_vent_q(i,1), &
            vss(1,i)+vsa(1,i),roominfo(a)%species_fraction(u,fuel)*(vss(1,i)+vsa(1,i)), &
            vsas(2,i),vsas(2,i)*roominfo(b)%species_fraction(l,o2)
        write(cfbt_vent_unit,'(es24.16,3(",",i0),5(",",es24.16))') time,i,b,a,cfbt_vent_q(i,2), &
            vss(2,i)+vsa(2,i),roominfo(b)%species_fraction(u,fuel)*(vss(2,i)+vsa(2,i)), &
            vsas(1,i),vsas(1,i)*roominfo(a)%species_fraction(l,o2)
        if (hventinfo(i)%opening_fraction<=1.e-12_eb) cycle
        do j=1,hventinfo(i)%n_slabs
            flow=hventinfo(i)%flow_slab(j)
            if (abs(flow)<=1.e-12_eb) cycle
            source=a; destination=b
            if (flow<0._eb) then
                source=b; destination=a
            end if
            zmid=(hventinfo(i)%ybot_slab(j)+hventinfo(i)%ytop_slab(j))/2._eb
            layer=l
            if (zmid>=roominfo(source)%z0+roominfo(source)%depth(l)) layer=u
            rho=roominfo(source)%rho(layer)
            area=hventinfo(i)%width*hventinfo(i)%opening_fraction* &
                (hventinfo(i)%ytop_slab(j)-hventinfo(i)%ybot_slab(j))
            velocity=abs(flow)/max(1.e-12_eb,rho*area)
            write(cfbt_slab_unit,'(es24.16,4(",",i0),11(",",es24.16))') time,i,source,destination,layer, &
                hventinfo(i)%ybot_slab(j),hventinfo(i)%ytop_slab(j),abs(flow),abs(flow)/max(rho,1.e-12_eb), &
                velocity,abs(flow)*roominfo(source)%species_fraction(layer,o2), &
                abs(flow)*roominfo(source)%species_fraction(layer,fuel), &
                abs(flow)*roominfo(source)%species_fraction(layer,soot),hventinfo(i)%temp_slab(j)-273.15_eb, &
                abs(flow)*roominfo(source)%species_fraction(layer,co),abs(flow)*cfbt_specific_chemical(source,layer)
        end do
    end do
    ! Floor-vent transport is native CFAST transport, with the exact native outgoing layer split.
    ! The global diagnostic vent index follows wall vents, matching the scenario order.
    do i=1,n_vvents
        a=vventinfo(i)%room1; b=vventinfo(i)%room2
        write(cfbt_vent_unit,'(es24.16,3(",",i0),5(",",es24.16))') time,n_hvents+i,a,b,0._eb,0._eb,0._eb,0._eb,0._eb
        write(cfbt_vent_unit,'(es24.16,3(",",i0),5(",",es24.16))') time,n_hvents+i,b,a,0._eb,0._eb,0._eb,0._eb,0._eb
        if (vventinfo(i)%opening_fraction<=1.e-12_eb) cycle
        do direction=1,2
            source=b; destination=a
            if (direction==2) then
                source=a; destination=b
            end if
            zmid=roominfo(b)%z0+roominfo(b)%cheight
            do layer=1,2
                flow=vventinfo(i)%cfbt_from_mass(direction,layer)
                if (flow<=1.e-12_eb) cycle
                rho=roominfo(source)%rho(layer)
                area=vventinfo(i)%current_area
                velocity=flow/max(1.e-12_eb,rho*area)
                write(cfbt_slab_unit,'(es24.16,4(",",i0),11(",",es24.16))') time,n_hvents+i,source,destination,layer, &
                    zmid,zmid,flow,flow/max(rho,1.e-12_eb),velocity, &
                    flow*roominfo(source)%species_fraction(layer,o2),flow*roominfo(source)%species_fraction(layer,fuel), &
                    flow*roominfo(source)%species_fraction(layer,soot),roominfo(source)%temp(layer)-273.15_eb, &
                    flow*roominfo(source)%species_fraction(layer,co),flow*cfbt_specific_chemical(source,layer)
            end do
        end do
    end do
    flush(cfbt_room_unit); flush(cfbt_vent_unit); flush(cfbt_slab_unit)
    end subroutine cfbt_output

