"""Read-only presentation counts from saved playback; never run a solver."""
from copy import deepcopy
from functools import lru_cache
import json
import math

TYPES = ('FO', 'FGI', 'backdraft')


@lru_cache(maxsize=512)
def _sample(path, mtime_ns, size, building_sha):
    unknown = {key: {'rooms': 0, 'unknown': True} for key in TYPES}
    try:
        with open(path, encoding='utf-8') as stream:
            value = json.load(stream)
        if (not value.get('complete') or value.get('building_sha256') != building_sha
                or value.get('schema') != 'pyrocast-cad-playback-1'):
            return unknown
        rooms, times = value.get('rooms', []), value.get('time_s', [])
        result = {}
        for key in TYPES:
            reached, missing = set(), not rooms or not times
            for room in rooms:
                degrees = value.get('solvers', {}).get(room.get('solver_id'), {}).get('conditions', {}).get(key, {}).get('scores', {}).get('degree')
                if not isinstance(degrees, list) or len(degrees) != len(times):
                    missing = True
                    continue
                for degree in degrees:
                    if isinstance(degree, bool) or not isinstance(degree, (int, float)) or not math.isfinite(degree):
                        missing = True
                    elif degree >= 1:
                        reached.add(room.get('original_room') or room['key'])
            result[key] = {'rooms': len(reached), 'unknown': bool(missing)}
        return result
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return unknown


def rooms_max(folder, rows, building_sha):
    """Same ≥100, whole-time, original-room deduplication as the former UI loop.

    Cache includes file metadata and building identity; changed/arriving files
    invalidate counts. Missing data remains unknown, never a safe zero.
    """
    result = {key: {'rooms': 0, 'unknown': False} for key in TYPES}
    completed = 0
    for i, row in enumerate(rows):
        if not row.get('complete'):
            continue
        completed += 1
        path = folder / f'S{i:02d}' / 'playback.json'
        try:
            stat = path.stat()
            sample = _sample(str(path.resolve()), stat.st_mtime_ns, stat.st_size, building_sha)
        except OSError:
            sample = {key: {'rooms': 0, 'unknown': True} for key in TYPES}
        for key in TYPES:
            result[key]['rooms'] = max(result[key]['rooms'], sample[key]['rooms'])
            result[key]['unknown'] |= sample[key]['unknown']
    if not completed:
        for item in result.values():
            item['unknown'] = True
    return deepcopy(result)
