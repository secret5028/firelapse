"""Geometry checks shared by CAD extraction and its regression tests."""
import cv2
import numpy as np
from shapely.geometry import LineString, Point, Polygon


def room_rings(mask, to_world):
    """Preserve interior rings; return all components in source metres."""
    contours, hierarchy = cv2.findContours(mask.astype(np.uint8), cv2.RETR_CCOMP,
                                           cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return []
    def ring(contour):
        # Do not simplify away small columns/shafts or join neighboring rooms.
        return [[round(coordinate / 1000, 3) for coordinate in to_world(int(u), int(v))]
                for u, v in contour[:, 0]]
    result = []
    for i, contour in enumerate(contours):
        if hierarchy[0][i][3] != -1 or len(contour) < 3:
            continue
        holes = []
        child = hierarchy[0][i][2]
        while child != -1:
            if len(contours[child]) >= 3:
                holes.append(ring(contours[child]))
            child = hierarchy[0][child][0]
        outer = ring(contour)
        geometry = Polygon(outer, holes)
        if not geometry.is_empty and geometry.area > 0:
            result.append(dict(o=outer, h=holes))
    return sorted(result, key=lambda p: -Polygon(p['o'], p['h']).area)


def jamb_support(endpoint, outward, walls, tree, mate_lines=(), max_gap=300, offset=3):
    """Connect only outward along the closed leaf, never to a nearby side wall.

    max_gap/offset are drafting tolerances (mm), not passage-width standards.
    A meeting double-door leaf also supports the central endpoint.
    """
    p = Point(endpoint)
    if any(line.distance(p) <= offset for line in mate_lines):
        return tuple(endpoint)
    if tree is None:
        return None
    u = np.asarray(outward, dtype=float)
    length = np.linalg.norm(u)
    if length == 0:
        return None
    u /= length
    start = np.asarray(endpoint, dtype=float)
    ray = LineString([start, start + u * max_gap])
    best = None
    for index in tree.query(ray.buffer(offset)):
        wall = walls[index]
        if wall.distance(p) <= offset:
            return tuple(endpoint)
        hit = ray.intersection(wall)
        points = []
        if hit.geom_type == 'Point':
            points = [hit]
        elif hit.geom_type == 'LineString' and not hit.is_empty:
            points = [Point(c) for c in hit.coords]
        elif hasattr(hit, 'geoms'):
            points = [g for g in hit.geoms if g.geom_type == 'Point']
        for q in points:
            distance = p.distance(q)
            if offset < distance <= max_gap and (best is None or distance < best[0]):
                best = (distance, q.x, q.y)
    return None if best is None else best[1:]


def connection_status(opening, room_ids):
    sides = opening.get('sides') or []
    if len(sides) != 2 or any(s is None or (s != 'out' and s not in room_ids) for s in sides):
        return 'unresolved'
    if sides[0] == sides[1]:
        return 'internal_leaf' if opening['kind'] == 'door_internal' and sides[0] != 'out' else 'same_space'
    return 'exterior' if 'out' in sides else 'interior'
