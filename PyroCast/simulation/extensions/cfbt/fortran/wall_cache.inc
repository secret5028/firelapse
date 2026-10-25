    logical function cfbt_keys_equal(a,b) result(same)
    use, intrinsic :: iso_c_binding, only: c_int,c_ptr,c_size_t,c_loc
    real(eb), contiguous, target, intent(in) :: a(:),b(:)
    interface
        integer(c_int) function cfbt_memcmp(first,second,count) bind(C,name='memcmp')
            import c_int,c_ptr,c_size_t
            type(c_ptr), value :: first,second
            integer(c_size_t), value :: count
        end function
    end interface
    same=.false.
    if (size(a)/=size(b).or.size(a)==0) return
    same=cfbt_memcmp(c_loc(a(1)),c_loc(b(1)),int(size(a),c_size_t)*int(storage_size(a(1))/8,c_size_t))==0
    end function

    logical function cfbt_wall_get(room,wall,key,gradient,derivative) result(hit)
    integer, intent(in) :: room,wall
    real(eb), intent(in) :: key(:)
    real(eb), intent(out) :: gradient(2),derivative
    integer :: slot
    hit=.false.
    if (.not.wall_cache_enabled) return
    do slot=1,2
        if (.not.allocated(cfbt_wall_cache(slot,wall,room)%key)) cycle
        if (size(cfbt_wall_cache(slot,wall,room)%key)/=size(key)) cycle
        ! Stored keys are finite (checked on insertion). NaN/Inf can never match.
        if (.not.cfbt_keys_equal(key,cfbt_wall_cache(slot,wall,room)%key)) cycle
        gradient=cfbt_wall_cache(slot,wall,room)%gradient
        derivative=cfbt_wall_cache(slot,wall,room)%derivative
        cfbt_wall_recent(wall,room)=slot
        cfbt_wall_hits=cfbt_wall_hits+1
        hit=.true.
        return
    end do
    cfbt_wall_misses=cfbt_wall_misses+1
    end function

    subroutine cfbt_wall_put(room,wall,key,gradient,derivative)
    use, intrinsic :: ieee_arithmetic, only: ieee_is_finite
    integer, intent(in) :: room,wall
    real(eb), intent(in) :: key(:),gradient(2),derivative
    integer :: slot
    if (.not.wall_cache_enabled) return
    if (.not.all(ieee_is_finite(key)).or..not.all(ieee_is_finite(gradient)).or..not.ieee_is_finite(derivative)) return
    slot=3-cfbt_wall_recent(wall,room)
    cfbt_wall_cache(slot,wall,room)%key=key
    cfbt_wall_cache(slot,wall,room)%gradient=gradient
    cfbt_wall_cache(slot,wall,room)%derivative=derivative
    cfbt_wall_recent(wall,room)=slot
    end subroutine

    subroutine cfbt_wall_output(time)
    use setup_data, only: datapath,project
    real(eb), intent(in) :: time
    if (.not.wall_cache_enabled) return
    if (cfbt_wall_unit==0) then
        open(newunit=cfbt_wall_unit,file=trim(datapath)//trim(project)//'_cfbt_wall_cache.csv',status='replace')
        write(cfbt_wall_unit,'(a)') 'time_s,exact_hits,misses'
    end if
    write(cfbt_wall_unit,'(es16.8,2(",",i0))') time,cfbt_wall_hits,cfbt_wall_misses
    flush(cfbt_wall_unit)
    end subroutine
