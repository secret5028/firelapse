program boundary_check
use precision_parameters
use fire_routines, only: cfbt_gate,cfbt_mixing_rate
implicit none
real(eb) :: x,g,previous,h,k,frac,mass
integer :: i,j
previous=0._eb
do i=-100,1100
 x=.12_eb+real(i,eb)*.00001_eb
 g=cfbt_gate(x,.12_eb,.01_eb)
 if (g<previous.or.g<0._eb.or.g>1._eb) error stop 'Nonmonotonic gate'
 if (x<=.12_eb.and.g/=0._eb) error stop 'Reaction below threshold'
 previous=g
end do
if (cfbt_gate(520._eb,520._eb,10._eb)/=0._eb) error stop 'Threshold nonzero'
if (cfbt_gate(530._eb,520._eb,10._eb)/=1._eb) error stop 'End point not one'
if (cfbt_gate(.001_eb,.001_eb,.0001_eb)/=0._eb) error stop 'Fuel threshold nonzero'
if (cfbt_gate(.12_eb+1.e-8_eb,.12_eb,.01_eb)>1.e-10_eb) error stop 'Boundary jump'
k=.1_eb
if (cfbt_mixing_rate(k,2._eb,0._eb,10._eb)/=0._eb) error stop 'No oxygen consumption'
if (abs(cfbt_mixing_rate(k,2._eb,1._eb,10._eb)-.05_eb)>1.e-14_eb) error stop 'Oxygen proportion'
if (abs(cfbt_mixing_rate(k,2._eb,3._eb,10._eb)-k)>1.e-14_eb) error stop 'Fuel limit'
if (abs(cfbt_mixing_rate(1.e8_eb,2._eb,3._eb,10._eb)-.1_eb)>1.e-14_eb) error stop 'High-temperature rate not capped'
do i=0,100
 x=real(i,eb)/10._eb
 g=cfbt_mixing_rate(k,2._eb,x,10._eb)
 if (g<0._eb.or.g>k.or.g*2._eb>k*x+1.e-14_eb) error stop 'Mixing budget exceeded'
end do
print *, 'PASS: continuous gates and shared oxygen-limited mixing rate'
end program
subroutine post_process
error stop 'Unexpected solver call'
end subroutine
