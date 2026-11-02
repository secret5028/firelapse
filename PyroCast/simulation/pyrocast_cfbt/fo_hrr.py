"""Shared FO diagnostic revision; never adds heat or consumes oxygen."""
import numpy as np

REVISION = 'fo_own_plus_received_door_jet_v1'


def apply_fo_hrr(record, own_kW, received_kW, required_kW):
    """Replace only the fuel factor, retaining the saved T/O2 definitions.

    own_kW includes the pre-existing source + upper-reaction contribution.
    received_kW is the receiving-room total, never an outgoing jet or a
    second addition of the same per-vent/native room total.
    Missing samples stay unknown. Reapplying is idempotent (not incremental).
    """
    from .conditions import screening_scores, _finite
    old = record['scores']; n = len(old['degree'])
    own = np.asarray(own_kW, dtype=float); jet = np.asarray(received_kW, dtype=float)
    required = np.asarray(required_kW, dtype=float)
    if any(a.shape != (n,) for a in (own, jet, required)):
        raise ValueError('FO HRR series must match the output time grid')
    def factor(name):
        flags = old.get('unbounded_factors', {}).get(name, [False]*n)
        return [float('inf') if flags[i] else x for i,x in enumerate(old['factors'][name])]
    # FO T/O2 ratios have positive fixed denominators, so unbounded inputs
    # indicate an invalid source rather than a value to silently clamp.
    for name in ('temperature','oxygen'):
        if any(old.get('unbounded_factors', {}).get(name, [])):
            raise ValueError('Unexpected unbounded FO temperature/oxygen ratio')
    total = own + jet
    new = screening_scores((factor('temperature'),1.,False),
        (total,required,False),(factor('oxygen'),1.,False),n,old.get('legacy_context_met'))
    assert new['factors']['temperature'] == old['factors']['temperature']
    assert new['factors']['oxygen'] == old['factors']['oxygen']
    record['scores'] = {**new, 'revision':REVISION}
    record.setdefault('score_basis', {}).update(
        revision=REVISION, Q_required_kW=_finite(required), Q_own_kW=_finite(own),
        Q_received_door_jet_kW=_finite(jet), Q_actual_kW=_finite(total),
        actual_formula='Q_actual = Q_own + Q_received_door_jet',
        own_definition='actual solid-source HRR + actual upper-layer reaction HRR (existing own contribution)',
        receiving_definition='receiving-compartment total, once; outgoing/outside jets excluded',
        scope='condition diagnostics only; no heat/oxygen integration or ignition feedback')
    if 'actual_quantities' in record:
        quantities=record['actual_quantities']
        quantities.setdefault('Q_source_kW',quantities.get('Q_actual_kW'))
        quantities['Q_actual_kW']=_finite(total)
        if 'intensity' in record:
            record['intensity']['Q_actual_kW']=[float(v) if record['all_met'][i] is True and np.isfinite(v) else None for i,v in enumerate(total)]
    return record
