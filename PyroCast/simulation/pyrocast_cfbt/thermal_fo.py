"""Display-only FO thermal proximity; no ignition or combustion feedback.

For saved cases without floor irradiation, report the measured upper-layer
temperature ratio explicitly. Do not turn absent source HRR into a zero score,
or fabricate unavailable floor heat flux / fuel / oxygen factors.
"""
import math


def temperature_scores(temperatures_C, threshold_C):
    if not math.isfinite(threshold_C) or threshold_C <= 0:
        raise ValueError('FO temperature threshold must be positive and finite')
    ratio = [float(t) / threshold_C if t is not None and math.isfinite(t) else None
             for t in temperatures_C]
    n = len(ratio)
    return dict(
        factors=dict(temperature=ratio, fuel=[None]*n, oxygen=[None]*n),
        unbounded_factors={k:[False]*n for k in ('temperature','fuel','oxygen')},
        degree=ratio,
        weakest=['temperature' if x is not None else None for x in ratio],
        strongest=['temperature' if x is not None else None for x in ratio],
        all_met=[x >= 1 if x is not None else None for x in ratio],
        basis='upper_layer_temperature_only_v1', threshold_C=threshold_C,
        floor_flux_status='not_evaluated',
        meaning='FO thermal proximity: upper-layer Celsius temperature / configured Celsius threshold; '
                'not probability, physical temperature fraction, actual flashover or secondary ignition prediction')
