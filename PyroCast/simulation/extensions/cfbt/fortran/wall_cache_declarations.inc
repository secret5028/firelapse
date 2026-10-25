    ! Project execution optimization; only derivative (update=0) calls are cached.
    logical, save, public :: wall_cache_enabled=.false.
    type cfbt_wall_entry
        real(eb), allocatable :: key(:)
        real(eb) :: gradient(2), derivative
    end type
    type(cfbt_wall_entry), save :: cfbt_wall_cache(2,nwal,mxrooms)
    integer, save :: cfbt_wall_recent(nwal,mxrooms)=1,cfbt_wall_unit=0
    integer(kind=8), save :: cfbt_wall_hits=0,cfbt_wall_misses=0
    public cfbt_wall_get,cfbt_wall_put,cfbt_wall_output,cfbt_keys_equal
