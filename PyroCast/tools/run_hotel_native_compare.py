"""One authorized stock-CFAST comparison against frozen overnight hotel 5F input."""
import json
import msvcrt
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'simulation'), str(ROOT/'simulation/deps')]
from pyrocast_cfbt.room_rule_r8 import prepare
from pyrocast_cfbt.deck import make_deck, window_targets
from pyrocast_cfbt.native import digest
from run_room_rule_r7 import run_case, ENGINE

SOURCE = ROOT/'simulation/results/overnight-20261104/parkmarine/5F'
OUT = ROOT/'simulation/results/hotel-native-compare-20261105/5F'


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), 'utf-8')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with (ROOT/'simulation/results/overnight-20261104/batch.lock').open('r+b') as lock:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        if (OUT/'attempt.json').exists():
            raise RuntimeError('Already attempted: no automatic retry')
        raw = json.loads((SOURCE/'input.json').read_text('utf-8'))
        model, targets, manifest = prepare(raw)
        assert manifest == json.loads((SOURCE/'rule_manifest.json').read_text('utf-8'))
        assert not window_targets(model), 'Opening states must stay fixed in both engines'
        deck = make_deck(model, [], targets)
        assert '&CFBT' not in deck
        source_hashes = {name:digest(SOURCE/name) for name in ('input.json','rule_manifest.json','result.json','playback.json')}
        shutil.copyfile(SOURCE/'input.json', OUT/'source-scenario.json')
        save(OUT/'comparison-input-evidence.json', dict(
            lite_source=str(SOURCE), source_hashes=source_hashes,
            native_engine=str(ENGINE), engine_sha256=digest(ENGINE),
            manifest_identical=True, rooms=len(model['rooms']), sources=len(model['fuel_groups']),
            origin='CAD_5F_R16', duration_s=3600, native_budget_s=1800,
            opening_state='input_default, exact frozen source', window_breakage=False,
            native_runs=1, baseline_runs=0, lite_reruns=0,
            trigger_difference='native r8 plate_sensor; lite upper_layer_temperature',
            conditions_sha256=digest(ROOT/'simulation/pyrocast_cfbt/conditions.py')))
        save(OUT/'attempt.json', dict(started_utc=datetime.now(timezone.utc).isoformat(), retry=False))
        started=time.monotonic()
        try:
            report=run_case(OUT, model, targets, manifest, timeout=1800, display_root=OUT.parent)
            save(OUT/'comparison-run-status.json', dict(state='complete' if report['complete'] else 'incomplete',
                wall_s=time.monotonic()-started, native_report=report,
                source_unchanged={n:digest(SOURCE/n)==h for n,h in source_hashes.items()}, retry=False))
        except Exception as exc:
            save(OUT/'comparison-run-status.json', dict(state='failed', wall_s=time.monotonic()-started,
                error=f'{type(exc).__name__}: {exc}', retry=False))
            raise


if __name__ == '__main__':
    main()
