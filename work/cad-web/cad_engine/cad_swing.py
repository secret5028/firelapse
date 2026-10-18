"""Display the complete recorded swing, including both sides of double-action doors."""
import math


def swing_points(leaf,steps=48):
    h=leaf['hinge'];r=leaf['r']
    def angle(p):return math.atan2(p[1]-h[1],p[0]-h[0])
    def delta(a,b):return (b-a+math.pi)%(2*math.pi)-math.pi
    closed=angle(leaf['closed']);opened=angle(leaf['open'])
    if leaf.get('open2') is not None:
        # Use CLOSED to disambiguate which half-circle belongs to this leaf.
        # A shortest-path interpolation of antipodal endpoints can mirror it.
        start=opened;end=angle(leaf['open2'])
        span=delta(start,closed)+delta(closed,end)
    else:start=closed;span=delta(closed,opened)
    return [(h[0]+r*math.cos(start+span*i/steps),h[1]+r*math.sin(start+span*i/steps)) for i in range(steps+1)]
