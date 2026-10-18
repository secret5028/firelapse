"""Geometric evidence for door symbols; distances in the caller's units."""
import math
import numpy as np
from shapely.geometry import LineString, Point, MultiPoint


def diameter_leaf(points, arc, scale=1.):
    """A thin, straight diameter passing through a semicircle hinge.

    Some CAD libraries draw both open positions as one 2r-long leaf line.
    This is symbol geometry, not a wall bisecting the vestibule.
    """
    if arc is None or not 150 < (arc[4]-arc[3]) % 360 < 195: return False
    q=np.asarray(points)*scale; h=np.asarray(arc[:2])*scale; r=arc[2]*scale
    if len(q)<2 or r<=0:return False
    rect=MultiPoint(q).minimum_rotated_rectangle
    if rect.geom_type=='Polygon':
        xy=np.asarray(rect.exterior.coords[:4]); lengths=np.linalg.norm(np.roll(xy,-1,axis=0)-xy,axis=1)
        if min(lengths)>.08 or max(lengths)<1.7*r or max(lengths)>2*r+.08:return False
    elif rect.length<1.7*r or rect.length>2*r+.08:return False
    if LineString(q).distance(Point(h))>.06:return False
    if np.max(np.linalg.norm(q-h,axis=1))>r+.08:return False
    a=math.radians(arc[3]);u=np.array([math.cos(a),math.sin(a)])
    return bool(np.min((q-h)@u)<-.8*r and np.max((q-h)@u)>.8*r)


def gap_axis_score(hinge, end, wall_lines, tree):
    """Reward a jamb at the closed tip; penalize closing along existing wall.

    Uses metre coordinates. Pair-door evidence is evaluated by the caller.
    """
    h=np.asarray(hinge);e=np.asarray(end);length=np.linalg.norm(e-h)
    if length<.3 or tree is None:return 0.
    u=(e-h)/length;tip=Point(e);axis=LineString([h+u*.15,e-u*.15])
    near=tree.query(LineString([h,e]).buffer(.15))
    distance=min((wall_lines[int(i)].distance(tip) for i in near),default=99.)
    overlap=max((wall_lines[int(i)].intersection(axis.buffer(.05,cap_style=2)).length for i in near),default=0.)
    return (6. if distance<.12 else 0.)-(6. if overlap>axis.length*.55 else 0.)
