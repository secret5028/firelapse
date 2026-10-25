program check_adaptive
use precision_parameters
use cparams, only: o2,mxfires
use room_data, only: roominfo,n_rooms
use fire_data, only: fireinfo,n_fires
use vent_data, only: n_hvents,n_vvents,hventinfo
use fire_routines, only: adaptive_radiation_enabled
use radiation_routines
implicit none
real(eb) :: key(21),original(21),w(4),g(2),o(4),weight,w2(4),g2(2),o2x(4),area(4)
real(eb) :: q(mxfires),x(mxfires),y(mxfires),z(mxfires),tl(mxfires,4),tu(mxfires,4),ang(4,mxfires)
logical ok
n_rooms=2;n_fires=2;n_hvents=1;n_vvents=0
allocate(roominfo(2),fireinfo(2),hventinfo(1))
roominfo(1)%species_fraction(:,o2)=.15_eb
roominfo(2)%species_fraction(:,o2)=.15_eb
fireinfo(1)%room=1;fireinfo(2)%room=2
fireinfo(:)%qdot_actual=1.e6_eb;fireinfo(:)%ignited=.true.;fireinfo(:)%ignition_time=0._eb
hventinfo(1)%opening_fraction=1._eb
adaptive_radiation_enabled=.true.
key=[600._eb,650._eb,400._eb,350._eb,800._eb,350._eb, .9_eb,.9_eb,.9_eb,.9_eb, &
     .5_eb,.01_eb,4._eb,4._eb,3._eb,1.2_eb,0._eb,350000._eb,2._eb,2._eb,.6_eb]
original=key
call cfbt_adaptive_evaluate(1,key,w,g,o,weight)
if (weight/=0) error stop 'Unbuilt room must stay native'
call cfbt_adaptive_build(1,200._eb,1,ok)
if (.not.ok) error stop 'Build rejected closed native radiation'
! Full temperature/HRR response is retained at the anchor optical geometry.
key(1:6)=key(1:6)+5._eb;key(18)=key(18)*1.02_eb
call cfbt_adaptive_evaluate(1,key,w,g,o,weight)
if (weight/=1) error stop 'Stable mature room not reduced'
q=0;x=0;y=0;z=0
q(1)=key(18);x(1)=key(19);y(1)=key(20);z(1)=key(21)
call rad4(key(1:4),key(5:6),key(7:10),key(11:12),1,key(13),key(14),key(15),key(16), &
    q,x,y,z,1,w2,g2,mxfires,tl,tu,ang,o2x,.false.)
if (maxval(abs([w-w2,g-g2,o-o2x]))>1.e-5_eb) error stop 'Operator fails native basis identity'
area=[16._eb,28.8_eb,19.2_eb,16._eb]
if (abs(sum(w*area)+sum(g)-q(1))>1.e-5_eb) error stop 'Radiation heat counted twice'
! New rooms have no operator even with identical states.
call cfbt_adaptive_evaluate(2,key,w,g,o,weight)
if (weight/=0) error stop 'New room was simplified'
! Trial perturbations cannot mutate the committed operator.
key=original;key(1)=key(1)+15._eb
call cfbt_adaptive_evaluate(1,key,w,g,o,weight)
if (abs(weight-.5_eb)>1.e-12_eb) error stop 'Smooth guard not half weight'
key(1)=original(1)+30._eb
call cfbt_adaptive_evaluate(1,key,w,g,o,weight)
if (weight/=0) error stop 'Large thermal change did not restore native'
key=original
call cfbt_adaptive_evaluate(1,key,w,g,o,weight)
if (weight/=1) error stop 'Rejected trial changed committed operator'
! Changed area must redistribute power without creating heat.
key(16)=key(16)+.02_eb
call cfbt_adaptive_evaluate(1,key,w,g,o,weight)
area=[16._eb,2._eb*(3._eb-key(16))*8._eb,2._eb*key(16)*8._eb,16._eb]
if (abs(sum(w*area)+sum(g)-key(18))>1.e-5_eb) error stop 'Current-area conservation failure'
! Vent and oxygen guards, then an accepted fallback, then dwell before return.
hventinfo(1)%opening_fraction=.5_eb
call cfbt_adaptive_evaluate(1,key,w,g,o,weight)
if (weight/=0) error stop 'Vent change did not restore native'
call cfbt_adaptive_accept(201._eb,1._eb)
if (cfbt_adaptive(1)%active.or.cfbt_adaptive(1)%fallbacks/=1) error stop 'Accepted fallback missing'
hventinfo(1)%opening_fraction=1._eb
call cfbt_adaptive_evaluate(1,original,w,g,o,weight)
call cfbt_adaptive_build(1,210._eb,1,ok)
roominfo(1)%species_fraction(1,o2)=.14_eb
call cfbt_adaptive_evaluate(1,original,w,g,o,weight)
if (weight/=0) error stop 'Oxygen guard failed'
call cfbt_adaptive_accept(211._eb,0._eb)
if (.not.cfbt_adaptive(1)%active) error stop 'Nonforward step committed a mode'
call cfbt_adaptive_accept(211._eb,1._eb)
if (cfbt_adaptive(1)%active) error stop 'Oxygen fallback not committed'
print *, 'PASS: native basis, heat closure, new-room protection, smooth guard, reentrant trial, area, vent/O2 fallback, accepted-only commit'
end program

subroutine post_process
end subroutine
