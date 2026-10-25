    ! Experimental, default-off reduced radiation operator for mature fires.
    ! No species source is added. The operator REPLACES native radiation only.
    type cfbt_adaptive_entry
        real(eb), allocatable :: pending(:), anchor(:), stable(:), response(:,:)
        real(eb) :: stable_since=-1._eb, built_at=-1._eb
        logical :: active=.false.
        integer :: builds=0, fallbacks=0, rejected=0
        integer(kind=8) :: approx_calls=0, blend_calls=0, full_calls=0
        real(eb) :: max_closure_W=0._eb
    end type
    type(cfbt_adaptive_entry), save :: cfbt_adaptive(mxrooms)
    integer, save :: cfbt_adaptive_unit=0
    public cfbt_adaptive_accept, cfbt_adaptive_output
    ! Exposed for the standalone native verification harness.
    public cfbt_adaptive, cfbt_adaptive_evaluate, cfbt_adaptive_build, cfbt_adaptive_distance, rad4
