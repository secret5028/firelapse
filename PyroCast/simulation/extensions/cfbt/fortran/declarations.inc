
    ! Project CFBT extension. Disabled without an explicit per-run sidecar.
    logical, save :: cfbt_loaded=.false., enabled=.false., bulk_enabled=.false., vent_gate_enabled=.false.
    logical, save :: room_enabled(mxrooms)=.true., pilot_assumed=.false.
    real(eb), save :: gas_ignition_C=520._eb, hot_C=300._eb, oxygen_min_vol=.12_eb
    real(eb), save :: fuel_min_mass_fraction=.001_eb, rate_ref_s_inv=.1_eb
    real(eb), save :: reference_K=800._eb, activation_J_mol=170000._eb
    real(eb), save :: vent_ignition_C=520._eb, pilot_start_s=0._eb, pilot_end_s=huge(1._eb)
    real(eb), save :: cfbt_q(mxrooms)=0._eb, cfbt_burn(mxrooms)=0._eb, cfbt_o2_used(mxrooms)=0._eb
    real(eb), save :: cfbt_vent_q(1000,2)=0._eb
    integer, save :: cfbt_room_unit=0, cfbt_vent_unit=0, cfbt_slab_unit=0
    ! Optional finite ignition-assistance window; consumes existing upper gas only.
    integer, save :: force_room=0
    real(eb), save :: force_time_s=0._eb, force_duration_s=30._eb, force_rate_s_inv=.2_eb
    real(eb), save :: force_o2_min_vol=.10_eb


    logical, save :: mixture_enabled=.false., jet_enabled=.false.
    ! Opt-in r3 regularization. Native combustion is unchanged.
    logical, save :: mixture_smooth_enabled=.false.
    real(eb), save :: mixture_o2_width_vol=.01_eb, mixture_temperature_width_C=10._eb, mixture_fuel_width=.0001_eb
    real(eb), save :: mixture_mixing_time_s=10._eb
    logical, save :: cfbt_rate_capped(mxrooms)=.false., cfbt_reserved_out(mxrooms)=.false.
    integer, save :: cfbt_accepted_steps=0, cfbt_cap_room_steps=0, cfbt_reserved_room_steps=0, cfbt_step_violations=0
    real(eb), save :: cfbt_max_accepted_dt=0._eb
    integer, save :: cfbt_reaction_unit=0
    real(eb), parameter :: cfbt_co_heat=10102784.35278703_eb, cfbt_co_o2=15.9994_eb/28.0101_eb
    real(eb), save :: cfbt_co_burn(mxrooms)=0._eb, cfbt_fuel_burn(mxrooms)=0._eb
    integer, save :: cfbt_mix_unit=0, cfbt_jet_unit=0

    ! Exact memoization only: no rounding, temporal lag, or change to native RAD4.
    logical, save :: radiation_cache_enabled=.false.
    logical, save :: adaptive_radiation_enabled=.false.
    real(eb), save :: adaptive_min_age_s=120._eb,adaptive_stable_s=30._eb,adaptive_refresh_s=10._eb
    type cfbt_rad_entry
        real(eb), allocatable :: key(:)
        real(eb) :: wall(4), layer(2), outgoing(4)
    end type
    type(cfbt_rad_entry), save :: cfbt_rad_cache(2,mxrooms)
    integer, save :: cfbt_rad_recent(mxrooms)=1, cfbt_rad_unit=0
    integer(kind=8), save :: cfbt_rad_hits=0, cfbt_rad_misses=0
