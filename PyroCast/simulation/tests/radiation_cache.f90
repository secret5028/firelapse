program cache_check
    use precision_parameters
    use fire_routines, only: cfbt_rad_get,cfbt_rad_put,radiation_cache_enabled
    use conduction_routines, only: cfbt_wall_get,cfbt_wall_put,wall_cache_enabled
    use, intrinsic :: ieee_arithmetic, only: ieee_value,ieee_quiet_nan
    implicit none
    real(eb) :: key(21),changed(21),wall(4),layer(2),outgoing(4),w(4),l(2),o(4)
    integer :: i
    key=[(real(i,eb),i=1,21)]
    wall=[1._eb,2._eb,3._eb,4._eb];layer=[5._eb,6._eb];outgoing=wall+10._eb
    call cfbt_rad_put(1,key,wall,layer,outgoing)
    if (cfbt_rad_get(1,key,w,l,o)) error stop 'Default must be off'
    radiation_cache_enabled=.true.
    call cfbt_rad_put(1,key,wall,layer,outgoing)
    if (.not.cfbt_rad_get(1,key,w,l,o)) error stop 'Exact hit missing'
    if (any(w/=wall).or.any(l/=layer).or.any(o/=outgoing)) error stop 'Output mismatch'
    if (cfbt_rad_get(2,key,w,l,o)) error stop 'Room leakage'
    if (cfbt_rad_get(1,key(:17),w,l,o)) error stop 'Fire count mismatch not detected'
    do i=1,size(key)
        changed=key;changed(i)=nearest(key(i),1._eb)
        if (cfbt_rad_get(1,changed,w,l,o)) error stop 'One ULP change not detected'
        call cfbt_rad_put(1,changed,wall*2,layer*2,outgoing*2)
        if (.not.cfbt_rad_get(1,key,w,l,o)) error stop 'Base state lost during perturbation'
        if (any(w/=wall).or.any(l/=layer).or.any(o/=outgoing)) error stop 'Perturbed output leaked'
    end do
    changed=key;changed(1)=0._eb
    call cfbt_rad_put(3,changed,wall,layer,outgoing)
    changed(1)=-0._eb
    if (cfbt_rad_get(3,changed,w,l,o)) error stop 'Signed zero must differ'
    changed(1)=ieee_value(0._eb,ieee_quiet_nan)
    call cfbt_rad_put(4,changed,wall,layer,outgoing)
    if (cfbt_rad_get(4,changed,w,l,o)) error stop 'NaN must not be cached'
    radiation_cache_enabled=.false.
    if (cfbt_rad_get(1,key,w,l,o)) error stop 'Off must bypass existing entries'
    if (cfbt_wall_get(1,1,key,l,o(1))) error stop 'Wall default must be off'
    wall_cache_enabled=.true.
    call cfbt_wall_put(1,1,key,layer,3._eb)
    if (.not.cfbt_wall_get(1,1,key,l,o(1))) error stop 'Wall exact hit missing'
    if (any(l/=layer).or.o(1)/=3._eb) error stop 'Wall output mismatch'
    if (cfbt_wall_get(1,2,key,l,o(1))) error stop 'Wall surface leakage'
    if (cfbt_wall_get(2,1,key,l,o(1))) error stop 'Wall room leakage'
    do i=1,size(key)
        changed=key;changed(i)=nearest(key(i),1._eb)
        if (cfbt_wall_get(1,1,changed,l,o(1))) error stop 'Wall ULP change not detected'
        call cfbt_wall_put(1,1,changed,layer*2,6._eb)
        if (.not.cfbt_wall_get(1,1,key,l,o(1))) error stop 'Wall base state lost'
        if (any(l/=layer).or.o(1)/=3._eb) error stop 'Wall perturbed output leaked'
    end do
    print *, 'PASS: wall default, output, surface/room isolation, all key ULPs, two slots'
    print *, 'PASS: disabled, exact output, rooms, lengths, all key ULPs, two slots, signed zero, NaN'
end program

! The harness never invokes simulation termination; main-program helper stub.
subroutine post_process
end subroutine
