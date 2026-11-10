"""Replay the saved October 26 checkpoint; starting does not run a simulation."""
import argparse
import json
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8780)
    args = parser.parse_args()
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT / 'tools'))
    from restore_saved_results import restore
    restore(ROOT)
    config = json.loads((ROOT / 'simulation/config/lite-viewer.json').read_text('utf-8'))
    sys.path.insert(0, str(ROOT / 'tools'))
    sys.argv = [str(ROOT / 'tools/serve_cfbt_building.py'), str(ROOT / 'cad-project'),
                '--building', str(ROOT / 'cad-project/building.json'),
                '--result', str(ROOT / config['active_path']), '--port', str(args.port)]
    runpy.run_path(sys.argv[0], run_name='__main__')


if __name__ == '__main__':
    main()
