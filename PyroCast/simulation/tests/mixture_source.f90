! Direct call of the built extension source, before native species rescaling.
program mixture_source_check
 use precision_parameters
 use cparams
 use room_data, only: roominfo,n_rooms
 use setup_data, only: datapath,project,stime
 use solver_data, only: i_speciesmap
 use fire_routines, only: cfbt_bulk
 implicit none
 real(eb) :: flows(mxrooms,ns+2,2),base(mxrooms,ns+2,2),again(mxrooms,ns+2,2)
 real(eb) :: old(2,ns),s(ns),mf,mc,mo,mw,yc,ys,nco,nsoot,nco2,no2,df,dc,ar,cr,hr,orr
 real(eb) :: mass_error, common_error, repeat_error,remaining_o2,tau
 integer :: k,j
 character(16) :: mode
 character(32) :: tau_arg
 call get_command_argument(1,mode)
 tau=1._eb
 if(trim(mode)=='smooth')then
  call get_command_argument(2,tau_arg)
  read(tau_arg,*)tau
 end if
 n_rooms=1;allocate(roominfo(1));datapath='';project='source-check';stime=1._eb
 do j=1,ns+2
  i_speciesmap(j)=j
 end do
 mw=.01201_eb+4._eb*.001008_eb;yc=.1_eb;ys=.02_eb
 nco=yc*mw/.02801_eb;nsoot=ys*mw/.01201_eb;nco2=1._eb-nco-nsoot
 no2=nco2+(2._eb+nco)/2._eb
 print '(a)', 'case,mass_residual_kg_s,C_residual_kg_s,H_residual_kg_s,O_residual_kg_s,common_rate_error,repeat_error'
 do k=1,8
  mf=1._eb;mc=.2_eb;mo=5._eb
  if(k==1)mc=0._eb
  if(k==2)mf=0._eb
  if(k==4)mo=0._eb
  if(k==5)then
   mf=0._eb;mc=0._eb
  end if
  roominfo(1)%species_mass=0._eb
  roominfo(1)%temp=900._eb
  if(k==6)roominfo(1)%temp=273.15_eb
  roominfo(1)%rho=1._eb;roominfo(1)%volume=20._eb
  roominfo(1)%species_mass(u,n2)=10._eb
  roominfo(1)%species_mass(u,fuel)=mf
  roominfo(1)%species_mass(u,co)=mc
  roominfo(1)%species_mass(u,o2)=mo
  roominfo(1)%species_mass(u,fuel_moles)=mf/mw
  roominfo(1)%species_mass(u,fuel_Q)=mf*18.e6_eb
  roominfo(1)%species_mass(u,fuel_o2)=mf*no2*.032_eb/mw
  roominfo(1)%species_mass(u,fuel_co2)=mf*nco2*.04401_eb/mw
  roominfo(1)%species_mass(u,fuel_co)=mf*yc
  roominfo(1)%species_mass(u,fuel_h2o)=mf*2._eb*.018016_eb/mw
  roominfo(1)%species_mass(u,fuel_soot)=mf*ys
  old=roominfo(1)%species_mass;base=0._eb
  if(k==7)base(1,o2+2,u)=-.99_eb*mo/tau
  if(k==8)then
   base(1,fuel+2,u)=-.8_eb*mf/tau;base(1,co+2,u)=-.75_eb*mc/tau
  end if
  remaining_o2=mo+tau*base(1,o2+2,u)
  flows=base;call cfbt_bulk(1._eb,flows)
  again=base;call cfbt_bulk(1._eb,again)
  repeat_error=maxval(abs(flows-again))
  if (trim(mode)=='smooth') then
   again=base;call cfbt_bulk(.01_eb,again)
   if(any(flows/=again))error stop 'Reaction depends on DASSL trial step'
   again=base;call cfbt_bulk(.5_eb,again)
   if(any(flows/=again))error stop 'Reaction depends on DASSL trial step'
  end if
  if(any(roominfo(1)%species_mass/=old))error stop 'Residual mutated inventory'
  s=flows(1,3:ns+2,u)-base(1,3:ns+2,u)
  df=-s(fuel);dc=yc*df-s(co)
  mass_error=sum(s(1:ns_mass))
  cr=s(fuel)*.01201_eb/mw+s(co)*.01201_eb/.02801_eb+s(co2)*.01201_eb/.04401_eb+s(soot)
  hr=s(fuel)*.004032_eb/mw+s(h2o)*.002016_eb/.018016_eb
  orr=s(o2)+s(co)*.016_eb/.02801_eb+s(co2)*.032_eb/.04401_eb+s(h2o)*.016_eb/.018016_eb
  common_error=0._eb
  if(mf>0._eb.and.mc>0._eb) &
   common_error=abs(df/(mf+tau*base(1,fuel+2,u))-dc/(mc+tau*base(1,co+2,u)))
  ! New CO uses current NIST molecular weights; native chemistry uses rounded masses.
  if(max(abs(mass_error),abs(cr),abs(hr),abs(orr))>2.e-6_eb)error stop 'Element source imbalance'
  if(common_error>1.e-12_eb.or.repeat_error>0._eb)error stop 'Not one deterministic progress rate'
  if(-s(o2)*tau>remaining_o2+1.e-12_eb)error stop 'Reused reserved native oxygen'
  if(df*tau>mf+tau*base(1,fuel+2,u)+1.e-12_eb.or.dc*tau>mc+tau*base(1,co+2,u)+1.e-12_eb)error stop 'Fuel stock exceeded'
  if(abs((flows(1,q,u)-base(1,q,u))-(df*18.e6_eb+dc*10102784.35278703_eb))>1.e-6_eb) &
      error stop 'Heat differs from shared fuel progress'
  if((k==4.or.k==5.or.k==6).and.maxval(abs(s))>0._eb)error stop 'Inactive source released mass'
  print '(i0,6(",",es24.16))', k,mass_error,cr,hr,orr,common_error,repeat_error
 end do
end program

! Only needed to link unused solve.o; this test never runs the full solver.
subroutine post_process
 error stop 'Unexpected full-solver post_process in source-only test'
end subroutine
