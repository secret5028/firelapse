"""Create a deterministic briefing alongside each completed playback."""
import argparse
import hashlib
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from lite_ai_briefing import briefing_value
from lite_ai_tools import ROOT, finite
from model_ai_tools import service_for_hash
from result_catalog import atomic_json, read
from runtime_storage import LEGACY_RESULTS, RESULTS

VERSION = 1
LOG = logging.getLogger(__name__)


def ensure(path, context=None):
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    target = path.with_name(path.stem + '-briefing.json')
    if os.name == 'nt':
        absolute = str(target.resolve())
        extended = '\\\\?\\UNC\\' + absolute[2:] if absolute.startswith('\\\\') else '\\\\?\\' + absolute
        target = Path(extended)
    saved = read(target, {})
    if saved.get('version') == VERSION and saved.get('source_sha256') == digest:
        return saved['briefing']

    playback = json.loads(raw)
    timeline = playback.get('time_s') or []
    if playback.get('complete') is not True or not timeline or not finite(timeline[-1]):
        raise ValueError('완료된 저장 결과를 선택하세요.')
    building = playback['building_sha256']
    case = (context or {}).get('case') or playback.get('case_id') or path.parent.name
    service = service_for_hash(building).bind_saved_case(case, path)
    value = briefing_value(service, dict(building=building, case=case, time_s=timeline[-1]))
    public = {key: value[key] for key in ('case', 'building', 'text', 'sections', 'template_version')}
    public['time_s'] = timeline[-1]
    public['tool_count'] = len(value['calls'])
    atomic_json(target, dict(version=VERSION, source_sha256=digest, briefing=public))
    return public


def for_case(service, context):
    path = service.case_path(context)
    value = ensure(path, context)
    if value['building'] != service.building(context['building'])[0]['sha']:
        raise ValueError('다른 건물의 결과')
    return {**value, 'case': context['case']}


def playback_files(root):
    if not root.is_dir():
        return
    for path in root.rglob('playback.json'):
        if path.resolve().is_relative_to(root.resolve()):
            yield path


def backfill():
    paths = [*playback_files(LEGACY_RESULTS), *(ROOT/'data/wando-coldstore').glob('*-playback.json')]

    def one(path):
        try:
            return ensure(path)['template_version']
        except Exception as exc:
            LOG.warning('%s: %s', path.relative_to(ROOT), exc)
            return 'skipped'

    counts = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for kind in pool.map(one, paths):
            counts[kind] = counts.get(kind, 0) + 1
    print(json.dumps(counts, ensure_ascii=False), flush=True)


def watch():
    seen = {}
    while True:
        current = {}
        for path in playback_files(RESULTS):
            try:
                stat = path.stat()
                stamp = stat.st_mtime_ns, stat.st_size
                if seen.get(path) != stamp:
                    ensure(path)
                current[path] = stamp
            except ValueError as exc:
                current[path] = stamp
                LOG.warning('Saved briefing for %s: %s', path.name, exc)
            except Exception as exc:
                LOG.warning('Saved briefing for %s: %s', path.name, exc)
        seen = current
        time.sleep(3)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--backfill', action='store_true')
    if parser.parse_args().backfill:
        backfill()
    else:
        watch()
