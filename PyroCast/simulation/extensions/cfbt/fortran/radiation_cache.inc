    logical function cfbt_rad_get(room,key,wall,layer,outgoing) result(hit)
    use conduction_routines, only: cfbt_keys_equal
    integer, intent(in) :: room
    real(eb), intent(in) :: key(:)
    real(eb), intent(out) :: wall(4),layer(2),outgoing(4)
    integer :: slot
    hit=.false.
    if (.not.radiation_cache_enabled) return
    do slot=1,2
        if (.not.allocated(cfbt_rad_cache(slot,room)%key)) cycle
        if (size(cfbt_rad_cache(slot,room)%key)/=size(key)) cycle
        ! Exact byte identity including signed zero. Stored keys are finite.
        if (.not.cfbt_keys_equal(key,cfbt_rad_cache(slot,room)%key)) cycle
        wall=cfbt_rad_cache(slot,room)%wall
        layer=cfbt_rad_cache(slot,room)%layer
        outgoing=cfbt_rad_cache(slot,room)%outgoing
        cfbt_rad_recent(room)=slot
        cfbt_rad_hits=cfbt_rad_hits+1
        hit=.true.
        return
    end do
    cfbt_rad_misses=cfbt_rad_misses+1
    end function

    subroutine cfbt_rad_put(room,key,wall,layer,outgoing)
    use, intrinsic :: ieee_arithmetic, only: ieee_is_finite
    integer, intent(in) :: room
    real(eb), intent(in) :: key(:),wall(4),layer(2),outgoing(4)
    integer :: slot
    if (.not.radiation_cache_enabled) return
    if (.not.all(ieee_is_finite(key)).or..not.all(ieee_is_finite(wall)).or. &
        .not.all(ieee_is_finite(layer)).or..not.all(ieee_is_finite(outgoing))) return
    slot=3-cfbt_rad_recent(room)
    cfbt_rad_cache(slot,room)%key=key
    cfbt_rad_cache(slot,room)%wall=wall
    cfbt_rad_cache(slot,room)%layer=layer
    cfbt_rad_cache(slot,room)%outgoing=outgoing
    cfbt_rad_recent(room)=slot
    end subroutine

    subroutine cfbt_rad_output(time)
    use setup_data, only: datapath,project
    use conduction_routines, only: cfbt_wall_output
    real(eb), intent(in) :: time
    call cfbt_wall_output(time)
    if (.not.radiation_cache_enabled) return
    if (cfbt_rad_unit==0) then
        open(newunit=cfbt_rad_unit,file=trim(datapath)//trim(project)//'_cfbt_radiation_cache.csv',status='replace')
        write(cfbt_rad_unit,'(a)') 'time_s,exact_hits,misses'
    end if
    write(cfbt_rad_unit,'(es16.8,2(",",i0))') time,cfbt_rad_hits,cfbt_rad_misses
    flush(cfbt_rad_unit)
    end subroutine
