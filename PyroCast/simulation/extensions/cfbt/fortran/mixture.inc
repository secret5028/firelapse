
    ! One-sided C1 transition: never reacts below a configured threshold.
    real(eb) function cfbt_gate(value,threshold,width) result(gate)
    real(eb), intent(in) :: value,threshold,width
    real(eb) :: x
    x=max(0._eb,min(1._eb,(value-threshold)/width))
    gate=x*x*(3._eb-2._eb*x)
    end function cfbt_gate

    ! Differential mixing-limited progress, independent of solver step size.
    ! Actual integration remains with DASSL; do not insert a step-average RHS.
    real(eb) function cfbt_mixing_rate(k,demand,oxygen,tau) result(rate)
    real(eb), intent(in) :: k,demand,oxygen,tau
    rate=0._eb
    if (demand>0._eb) rate=min(max(0._eb,k),1._eb/tau)*min(1._eb,max(0._eb,oxygen)/demand)
    end function cfbt_mixing_rate

    ! Observation only, called outside residual evaluations after native acceptance.
    ! No clipping or exponential finite-step correction is applied to native state.
    subroutine cfbt_accept_step(step)
    real(eb), intent(in) :: step
    if (.not.enabled.or..not.bulk_enabled.or..not.mixture_smooth_enabled.or.step<=0._eb) return
    cfbt_accepted_steps=cfbt_accepted_steps+1
    cfbt_cap_room_steps=cfbt_cap_room_steps+count(cfbt_rate_capped(1:n_rooms))
    cfbt_reserved_room_steps=cfbt_reserved_room_steps+count(cfbt_reserved_out(1:n_rooms))
    cfbt_max_accepted_dt=max(cfbt_max_accepted_dt,step)
    if (step>mixture_mixing_time_s*(1._eb+1.e-8_eb)) then
        cfbt_step_violations=cfbt_step_violations+1
        error stop 'Accepted step exceeds mixture stock-bound horizon'
    end if
    end subroutine cfbt_accept_step

    subroutine cfbt_bulk(step,flows)
    real(eb), intent(in) :: step
    real(eb), intent(inout) :: flows(mxrooms,ns+2,2)
    call cfbt_initialize
    if (mixture_enabled) then
        call cfbt_mixture(step,flows)
    else
        call cfbt_legacy_bulk(step,flows)
    end if
    end subroutine cfbt_bulk

    real(eb) function cfbt_specific_chemical(i,layer) result(value)
    integer, intent(in) :: i,layer
    real(eb) :: mass
    mass=roominfo(i)%rho(layer)*roominfo(i)%volume(layer)
    value=max(0._eb,roominfo(i)%species_mass(layer,fuel_Q))
    if (mixture_enabled) value=value+cfbt_co_heat*max(0._eb, &
        roominfo(i)%species_mass(layer,co)+roominfo(i)%species_mass(layer,fuel_co))
    value=value/max(mass,1.e-12_eb)
    end function cfbt_specific_chemical

    subroutine cfbt_mixture(step,flows)
    use solver_data, only: i_speciesmap
    use setup_data, only: stime
    real(eb), intent(in) :: step
    real(eb), intent(inout) :: flows(mxrooms,ns+2,2)
    real(eb) :: available(ns), xmass(ns), unitmass(ns), mf,mc,mo,rawf,mw,hoc,ys,yc,yhcn
    real(eb) :: nc,nh,no,nn,ncl,nu_hcl,nu_co2,nu_h2o,nu_o2,rate,horizon,demand,energy
    real(eb) :: released,burned,yo,xo,k,ratio,stock,df,dc,gate,ignition_gate,ycomb
    integer :: i,p,j
    logical :: ignition,forced
    cfbt_q=0._eb;cfbt_burn=0._eb;cfbt_o2_used=0._eb;cfbt_co_burn=0._eb;cfbt_fuel_burn=0._eb
    cfbt_rate_capped=.false.;cfbt_reserved_out=.false.
    if (.not.enabled.or..not.bulk_enabled) return
    horizon=max(abs(step),1.e-5_eb)
    ! Reserve native consumption/outflow over a fixed mixing horizon, not a
    ! DASSL trial step. Conservative allocation; this is a model assumption.
    if (mixture_smooth_enabled) horizon=mixture_mixing_time_s
    do i=1,n_rooms
        if (.not.room_enabled(i)) cycle
        rawf=max(0._eb,roominfo(i)%species_mass(u,fuel))
        stock=max(1.e-12_eb,roominfo(i)%rho(u)*roominfo(i)%volume(u))
        ycomb=(rawf+max(0._eb,roominfo(i)%species_mass(u,co)))/stock
        if (ycomb<fuel_min_mass_fraction) cycle
        xo=cfbt_oxygen_vol(i,u)
        forced=i==force_room.and.stime>=force_time_s.and.stime<force_time_s+force_duration_s
        if (xo<merge(force_o2_min_vol,oxygen_min_vol,forced)) cycle
        ignition=roominfo(i)%temp(u)>=gas_ignition_C+273.15_eb.or.forced
        if (pilot_assumed.and.stime>=pilot_start_s.and.stime<=pilot_end_s) &
            ignition=ignition.or.roominfo(i)%temp(u)>=hot_C+273.15_eb
        if (.not.ignition) cycle
        gate=1._eb
        if (mixture_smooth_enabled) then
            ignition_gate=cfbt_gate(roominfo(i)%temp(u)-273.15_eb,gas_ignition_C,mixture_temperature_width_C)
            if (pilot_assumed.and.stime>=pilot_start_s.and.stime<=pilot_end_s) &
                ignition_gate=max(ignition_gate,cfbt_gate(roominfo(i)%temp(u)-273.15_eb,hot_C,mixture_temperature_width_C))
            if (forced) ignition_gate=1._eb
            gate=ignition_gate*cfbt_gate(xo,merge(force_o2_min_vol,oxygen_min_vol,forced),mixture_o2_width_vol)* &
                cfbt_gate(ycomb,fuel_min_mass_fraction,mixture_fuel_width)
            if (gate<=0._eb) cycle
        end if
        available=max(0._eb,roominfo(i)%species_mass(u,:))
        do p=3,ns+2
            j=i_speciesmap(p)-2
            if (j>=1.and.j<=ns) available(j)=max(0._eb,available(j)+min(0._eb,horizon*flows(i,p,u)))
        end do
        mf=available(fuel);mc=available(co);mo=available(o2)
        if (mixture_smooth_enabled) cfbt_reserved_out(i)= &
            (mo<=1.e-12_eb.or.mf+mc<=1.e-12_eb)
        if (mf+mc<=1.e-12_eb.or.mo<=1.e-12_eb) cycle
        unitmass=0._eb;hoc=0._eb
        if (mf>1.e-12_eb.and.rawf>1.e-12_eb) then
            if (roominfo(i)%species_mass(u,fuel_moles)<=1.e-12_eb) cycle
            hoc=roominfo(i)%species_mass(u,fuel_Q)/rawf
            mw=rawf/roominfo(i)%species_mass(u,fuel_moles)
            ys=roominfo(i)%species_mass(u,fuel_soot)/rawf
            yc=roominfo(i)%species_mass(u,fuel_co)/rawf
            yhcn=roominfo(i)%species_mass(u,fuel_hcn)/rawf
            nu_hcl=roominfo(i)%species_mass(u,fuel_hcl)/rawf*mw/.036458_eb
            nu_co2=roominfo(i)%species_mass(u,fuel_co2)/rawf*mw/.04401_eb
            nu_h2o=roominfo(i)%species_mass(u,fuel_h2o)/rawf*mw/.018016_eb
            nu_o2=roominfo(i)%species_mass(u,fuel_o2)/rawf*mw/.032_eb
            nn=yhcn*mw/.027028_eb+2._eb*roominfo(i)%species_mass(u,fuel_n2)/rawf*mw/.02802_eb
            ncl=nu_hcl;nh=2._eb*nu_h2o+yhcn*mw/.027028_eb+nu_hcl
            nc=nu_co2+yhcn*mw/.027028_eb+yc*mw/.02801_eb+ys*mw/.01201_eb
            no=max(0._eb,2._eb*nu_co2-2._eb*nu_o2+nu_h2o+yc*mw/.02801_eb)
            ! Stoichiometry per kg at abundant oxygen; only the common mixture limiter sets the rate.
            call chemistry(1._eb,mw,1.e12_eb,hoc,ys,ys,0._eb,yc,yhcn,nc,nh,no,nn,ncl, &
                .23_eb,0._eb,released,burned,unitmass)
        end if
        demand=mf*max(0._eb,-unitmass(o2))+mc*cfbt_co_o2
        energy=mf*hoc+mc*cfbt_co_heat
        if (demand<=0._eb.or.energy<=0._eb) cycle
        k=rate_ref_s_inv*exp(min(40._eb,activation_J_mol/8.314462618_eb* &
            (1._eb/reference_K-1._eb/roominfo(i)%temp(u))))*(xo/.12_eb)
        if (forced) k=force_rate_s_inv*(xo/.12_eb)
        if (mixture_smooth_enabled) then
            cfbt_rate_capped(i)=k>1._eb/mixture_mixing_time_s
            rate=gate*cfbt_mixing_rate(k,demand,mo,mixture_mixing_time_s)
        else
            rate=min(k,1._eb/horizon,mo/(horizon*demand))
        end if
        df=rate*mf;dc=rate*mc
        xmass=unitmass*df
        xmass(co)=xmass(co)-dc
        xmass(co2)=xmass(co2)+dc*(1._eb+cfbt_co_o2)
        xmass(o2)=xmass(o2)-dc*cfbt_co_o2
        if (rawf>1.e-12_eb) then
            ratio=df/rawf
            xmass(fuel_moles:ns)=-ratio*roominfo(i)%species_mass(u,fuel_moles:ns)
        end if
        do p=3,ns+2
            j=i_speciesmap(p)-2
            if (j>=1.and.j<=ns) flows(i,p,u)=flows(i,p,u)+xmass(j)
        end do
        released=rate*energy
        flows(i,q,u)=flows(i,q,u)+released
        cfbt_q(i)=released;cfbt_burn(i)=df+dc;cfbt_fuel_burn(i)=df;cfbt_co_burn(i)=dc
        cfbt_o2_used(i)=-xmass(o2)
    end do
    end subroutine cfbt_mixture

    subroutine cfbt_extra_output(time)
    real(eb), intent(in) :: time
    real(eb) :: mf,mc,stored,xyz(3),tg,vg(4),h,rr,theta,delta
    integer :: i,j,k,ifire,best,ring,sample_id
    if (.not.enabled) return
    if (mixture_smooth_enabled) then
        if (cfbt_reaction_unit==0) then
            block
            use setup_data, only: datapath, project
            open(newunit=cfbt_reaction_unit,file=trim(datapath)//trim(project)//'_cfbt_reaction_steps.csv',status='replace')
            end block
            write(cfbt_reaction_unit,'(a)') 'time_s,accepted_forward_steps,rate_cap_room_steps,'// &
                'native_reservation_exhausted_room_steps,step_bound_violations,max_accepted_dt_s'
        end if
        write(cfbt_reaction_unit,'(es24.16,4(",",i0),",",es24.16)') time,cfbt_accepted_steps,cfbt_cap_room_steps, &
            cfbt_reserved_room_steps,cfbt_step_violations,cfbt_max_accepted_dt
        flush(cfbt_reaction_unit)
    end if
    if (mixture_enabled) then
        if (cfbt_mix_unit==0) then
            block
            use setup_data, only: datapath, project
            open(newunit=cfbt_mix_unit,file=trim(datapath)//trim(project)//'_cfbt_mixture.csv',status='replace')
            end block
            write(cfbt_mix_unit,'(a)') 'time_s,room_index,combustible_upper_kg,co_upper_kg,co2_upper_kg,'// &
                'available_heat_J,total_chemical_J,mixture_HRR_W,mixture_o2_kg_s,fuel_burn_kg_s,co_burn_kg_s'
        end if
        do i=1,n_rooms
            mf=max(0._eb,roominfo(i)%species_mass(u,fuel));mc=max(0._eb,roominfo(i)%species_mass(u,co))
            stored=0._eb
            do j=1,2
                stored=stored+cfbt_specific_chemical(i,j)*roominfo(i)%rho(j)*roominfo(i)%volume(j)
            end do
            write(cfbt_mix_unit,'(es24.16,",",i0,9(",",es24.16))') time,i,mf+mc,mc,roominfo(i)%species_mass(u,co2), &
                max(0._eb,roominfo(i)%species_mass(u,fuel_Q))+mc*cfbt_co_heat,stored,cfbt_q(i), &
                cfbt_o2_used(i),cfbt_fuel_burn(i),cfbt_co_burn(i)
        end do
        flush(cfbt_mix_unit)
    end if
    if (.not.jet_enabled) return
    if (cfbt_jet_unit==0) then
        block
        use setup_data, only: datapath, project
        open(newunit=cfbt_jet_unit,file=trim(datapath)//trim(project)//'_cfbt_jets.csv',status='replace')
        end block
        write(cfbt_jet_unit,'(a)') 'time_s,room_index,sample_index,x_m,y_m,z_m,vx_m_s,vy_m_s,temperature_C,thickness_m'
    end if
    do i=1,n_rooms
        best=0
        do ifire=1,n_fires
            if (fireinfo(ifire)%room/=i) cycle
            if (best==0) then
                best=ifire
            else if (fireinfo(ifire)%qdot_actual>fireinfo(best)%qdot_actual) then
                best=ifire
            end if
        end do
        if (best==0) cycle
        h=roominfo(i)%cheight-fireinfo(best)%z_position-fireinfo(best)%z_offset
        if (h<=.05_eb) cycle
        do ring=1,2
            do k=0,7
                theta=k*6.283185307179586_eb/8._eb
                rr=h*(.5_eb+real(ring-1,eb))
                xyz(1)=min(roominfo(i)%cwidth-.05_eb,max(.05_eb,fireinfo(best)%x_position+rr*cos(theta)))
                xyz(2)=min(roominfo(i)%cdepth-.05_eb,max(.05_eb,fireinfo(best)%y_position+rr*sin(theta)))
                xyz(3)=roominfo(i)%cheight-.025_eb
                call get_gas_temp_and_velocity(i,xyz(1),xyz(2),xyz(3),tg,vg)
                rr=sqrt((xyz(1)-fireinfo(best)%x_position)**2+(xyz(2)-fireinfo(best)%y_position)**2)
                delta=h*.112_eb*(1._eb-exp(-2.24_eb*max(.26_eb,rr/h)))
                if (fireinfo(best)%qdot_actual<=1.e-4_eb) vg=0._eb
                sample_id=(ring-1)*8+k+1
                write(cfbt_jet_unit,'(es24.16,2(",",i0),7(",",es24.16))') time,i,sample_id, &
                    xyz(1),xyz(2),xyz(3),vg(1),vg(2),tg-273.15_eb,delta
            end do
        end do
    end do
    flush(cfbt_jet_unit)
    end subroutine cfbt_extra_output
