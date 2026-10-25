    function cfbt_adaptive_context(key) result(state)
    use cparams, only: o2
    use vent_data, only: n_hvents,hventinfo,n_vvents,vventinfo
    real(eb), intent(in) :: key(:)
    real(eb) :: state(size(key)+n_hvents+n_vvents)
    integer j
    state(1:size(key))=key
    do j=1,n_hvents
        state(size(key)+j)=hventinfo(j)%opening_fraction
    end do
    do j=1,n_vvents
        state(size(key)+n_hvents+j)=vventinfo(j)%opening_fraction
    end do
    end function

    real(eb) function cfbt_adaptive_distance(a,b,n) result(distance)
    use, intrinsic :: ieee_arithmetic, only: ieee_is_finite
    integer, intent(in) :: n
    real(eb), intent(in) :: a(:),b(:)
    integer last
    distance=huge(1._eb)
    if (size(a)/=size(b).or.size(a)<19+4*n) return
    if (.not.all(ieee_is_finite(a)).or..not.all(ieee_is_finite(b))) return
    if (any(a(7:10)/=b(7:10)).or.any(a(13:15)/=b(13:15)).or.a(17)/=b(17)) return
    distance=maxval(abs(a(1:6)-b(1:6)))/20._eb
    distance=max(distance,maxval(abs(a(11:12)-b(11:12))/max(.01_eb,abs(b(11:12))))/.10_eb)
    distance=max(distance,abs(a(16)-b(16))/.10_eb)
    if (n>0) then
        distance=max(distance,maxval(abs(a(18:17+n)-b(18:17+n))/max(1000._eb,abs(b(18:17+n))))/.10_eb)
        distance=max(distance,maxval(abs(a(18+n:17+4*n)-b(18+n:17+4*n)))/.10_eb)
    end if
    last=17+4*n
    distance=max(distance,maxval(abs(a(last+1:last+2)-b(last+1:last+2)))/.005_eb)
    if (size(a)>last+2) distance=max(distance,maxval(abs(a(last+3:)-b(last+3:)))/.01_eb)
    end function

    subroutine cfbt_adaptive_areas(key,area)
    real(eb), intent(in) :: key(:)
    real(eb), intent(out) :: area(4)
    area=[key(13)*key(14),2._eb*(key(15)-key(16))*(key(13)+key(14)), &
          2._eb*key(16)*(key(13)+key(14)),key(13)*key(14)]
    end subroutine

    subroutine cfbt_adaptive_evaluate(room,key,wall,layer,outgoing,weight)
    use cparams, only: o2
    use, intrinsic :: ieee_arithmetic, only: ieee_is_finite
    integer, intent(in) :: room
    real(eb), intent(in) :: key(:)
    real(eb), intent(out) :: wall(4),layer(2),outgoing(4),weight
    real(eb), allocatable :: state(:),basis(:)
    real(eb) :: distance,x,values(10),area(4),closure
    integer n
    weight=0._eb;wall=0._eb;layer=0._eb;outgoing=0._eb
    if (.not.adaptive_radiation_enabled) return
    n=(size(key)-17)/4
    state=cfbt_adaptive_context([key,roominfo(room)%species_fraction(:,o2)])
    ! A scratch sample is overwritten by every RHS; only the final accepted RHS
    ! may commit an anchor. Trial evaluations never change the active operator.
    cfbt_adaptive(room)%pending=state
    if (.not.cfbt_adaptive(room)%active) then
        cfbt_adaptive(room)%full_calls=cfbt_adaptive(room)%full_calls+1
        return
    end if
    distance=cfbt_adaptive_distance(state,cfbt_adaptive(room)%anchor,n)
    if (distance>=1._eb) then
        cfbt_adaptive(room)%full_calls=cfbt_adaptive(room)%full_calls+1
        return
    end if
    x=max(0._eb,min(1._eb,2._eb*(1._eb-distance)))
    weight=x*x*(3._eb-2._eb*x)
    basis=[(key(1:6)/1000._eb)**4,key(18:17+n)/1.e6_eb]
    values=matmul(cfbt_adaptive(room)%response,basis)
    call cfbt_adaptive_areas(key,area)
    closure=abs(sum(values(1:6))-sum(key(18:17+n)))
    if (minval(area)<=0._eb.or..not.all(ieee_is_finite(values)).or. &
        closure>1.e-6_eb*max(1._eb,sum(abs(values(1:6))))) then
        weight=0._eb
        cfbt_adaptive(room)%full_calls=cfbt_adaptive(room)%full_calls+1
        return
    end if
    cfbt_adaptive(room)%max_closure_W=max(cfbt_adaptive(room)%max_closure_W,closure)
    wall=values(1:4)/area;layer=values(5:6);outgoing=values(7:10)
    if (weight==1._eb) then
        cfbt_adaptive(room)%approx_calls=cfbt_adaptive(room)%approx_calls+1
    else
        cfbt_adaptive(room)%blend_calls=cfbt_adaptive(room)%blend_calls+1
    end if
    end subroutine

    subroutine cfbt_adaptive_build(room,time,n,ok)
    integer, intent(in) :: room,n
    real(eb), intent(in) :: time
    logical, intent(out) :: ok
    real(eb), allocatable :: key(:),matrix(:,:)
    real(eb) :: tw(4),tg(2),qf(mxfires),xf(mxfires),yf(mxfires),zf(mxfires)
    real(eb) :: wall(4),layer(2),outgoing(4),area(4),tu(mxfires,4),tl(mxfires,4),angles(4,mxfires),expected
    integer j
    ok=.false.;key=cfbt_adaptive(room)%pending
    ! Native minimum-layer radiation_fix breaks the simple closed exchange
    ! identity; these near-empty layers are always evaluated by native RAD4.
    if (min(key(16),key(15)-key(16))<.01_eb*key(15).or.key(17)/=0._eb) return
    call cfbt_adaptive_areas(key,area)
    xf=0._eb;yf=0._eb;zf=0._eb
    xf(1:n)=key(18+n:17+2*n);yf(1:n)=key(18+2*n:17+3*n);zf(1:n)=key(18+3*n:17+4*n)
    allocate(matrix(10,6+n))
    do j=1,6+n
        tw=0._eb;tg=0._eb;qf=0._eb
        if (j<=4) then
            tw(j)=1000._eb
        else if (j<=6) then
            tg(j-4)=1000._eb
        else
            qf(j-6)=1.e6_eb
        end if
        call rad4(tw,tg,key(7:10),key(11:12),room,key(13),key(14),key(15),key(16), &
            qf,xf,yf,zf,n,wall,layer,mxfires,tl,tu,angles,outgoing,.false.)
        matrix(:,j)=[wall*area,layer,outgoing]
        expected=merge(1.e6_eb,0._eb,j>6)
        if (abs(sum(matrix(1:6,j))-expected)>1.e-6_eb*max(1._eb,sum(abs(matrix(1:6,j))))) return
    end do
    cfbt_adaptive(room)%anchor=key
    cfbt_adaptive(room)%response=matrix
    cfbt_adaptive(room)%active=.true.
    cfbt_adaptive(room)%built_at=time
    cfbt_adaptive(room)%builds=cfbt_adaptive(room)%builds+1
    ok=.true.
    end subroutine

    subroutine cfbt_adaptive_accept(time,dt)
    real(eb), intent(in) :: time,dt
    real(eb) :: newest,qtotal,distance
    integer room,j,n,burning_rooms
    logical ok,eligible
    if (.not.adaptive_radiation_enabled.or.dt<=0._eb) return
    burning_rooms=0
    do room=1,n_rooms
        qtotal=0._eb
        do j=1,n_fires
            if (fireinfo(j)%room==room) qtotal=qtotal+fireinfo(j)%qdot_actual
        end do
        if (qtotal>1000._eb) burning_rooms=burning_rooms+1
    end do
    do room=1,n_rooms
        if (.not.allocated(cfbt_adaptive(room)%pending)) cycle
        n=0;newest=-huge(1._eb);qtotal=0._eb
        do j=1,n_fires
            if (fireinfo(j)%room/=room) cycle
            n=n+1
            qtotal=qtotal+fireinfo(j)%qdot_actual
            if (fireinfo(j)%ignited) newest=max(newest,fireinfo(j)%ignition_time)
        end do
        eligible=burning_rooms>=2.and.qtotal>1000._eb.and.time-newest>=adaptive_min_age_s
        if (cfbt_adaptive(room)%active) then
            distance=cfbt_adaptive_distance(cfbt_adaptive(room)%pending,cfbt_adaptive(room)%anchor,n)
            if (distance>=1._eb.or..not.eligible) then
                cfbt_adaptive(room)%active=.false.
                cfbt_adaptive(room)%fallbacks=cfbt_adaptive(room)%fallbacks+1
                cfbt_adaptive(room)%stable_since=-1._eb
            end if
        end if
        if (.not.eligible) then
            cfbt_adaptive(room)%stable_since=-1._eb
            cycle
        end if
        if (cfbt_adaptive(room)%stable_since<0._eb) then
            cfbt_adaptive(room)%stable=cfbt_adaptive(room)%pending
            cfbt_adaptive(room)%stable_since=time
        end if
        distance=cfbt_adaptive_distance(cfbt_adaptive(room)%pending,cfbt_adaptive(room)%stable,n)
        if (distance>.5_eb) then
            cfbt_adaptive(room)%stable=cfbt_adaptive(room)%pending
            cfbt_adaptive(room)%stable_since=time
        end if
        if (.not.cfbt_adaptive(room)%active.and.time-cfbt_adaptive(room)%stable_since<adaptive_stable_s) cycle
        if (cfbt_adaptive(room)%active.and.time-cfbt_adaptive(room)%built_at<adaptive_refresh_s) cycle
        call cfbt_adaptive_build(room,time,n,ok)
        if (.not.ok) then
            cfbt_adaptive(room)%rejected=cfbt_adaptive(room)%rejected+1
            cfbt_adaptive(room)%active=.false.
            cfbt_adaptive(room)%stable_since=-1._eb
        end if
    end do
    end subroutine

    subroutine cfbt_adaptive_output(time)
    use setup_data, only: datapath,project
    real(eb), intent(in) :: time
    integer i
    if (.not.adaptive_radiation_enabled) return
    if (cfbt_adaptive_unit==0) then
        open(newunit=cfbt_adaptive_unit,file=trim(datapath)//trim(project)//'_cfbt_adaptive.csv',status='replace')
        write(cfbt_adaptive_unit,'(a)') 'time_s,room_index,active,builds,fallbacks,rejected,approx_calls,blend_calls,full_calls,max_closure_W'
    end if
    do i=1,n_rooms
        write(cfbt_adaptive_unit,'(es24.16,8(",",i0),",",es24.16)') time,i,merge(1,0,cfbt_adaptive(i)%active), &
            cfbt_adaptive(i)%builds,cfbt_adaptive(i)%fallbacks,cfbt_adaptive(i)%rejected, &
            cfbt_adaptive(i)%approx_calls,cfbt_adaptive(i)%blend_calls,cfbt_adaptive(i)%full_calls,cfbt_adaptive(i)%max_closure_W
    end do
    flush(cfbt_adaptive_unit)
    end subroutine
