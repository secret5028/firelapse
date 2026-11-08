"""Writable calculation data outside the installed application; legacy reads remain valid."""
import os
from pathlib import Path
from result_catalog import _io_path
ROOT = Path(__file__).resolve().parents[1]
LEGACY_RESULTS = ROOT/'simulation/results'
DATA_ROOT = Path(os.environ.get('FIRELAPSE_DATA_DIR') or (Path(os.environ.get('LOCALAPPDATA') or Path.home()/'.local/share')/'FireLapse')).expanduser().resolve()
if DATA_ROOT == ROOT or DATA_ROOT.is_relative_to(ROOT):
    raise ValueError('FIRELAPSE_DATA_DIR must be outside the application folder')
RESULTS = DATA_ROOT/'results'

def result_roots():
    return (RESULTS, LEGACY_RESULTS)

def locate(path):
    """Resolve a read in the new tree, falling back to the bundled/original result."""
    p=Path(path)
    if _io_path(p).exists(): return p
    try: rel=p.relative_to(RESULTS)
    except ValueError: return p
    return LEGACY_RESULTS/rel if _io_path(LEGACY_RESULTS/rel).exists() else p

def result_glob(base, pattern):
    base=Path(base); paths={}
    try: rel=base.relative_to(RESULTS)
    except ValueError:
        scan=_io_path(base)
        return [base/p.relative_to(scan) for p in scan.glob(pattern)]
    for root in reversed(result_roots()):
        scan=_io_path(root/rel)
        for p in scan.glob(pattern):
            logical=root/rel/p.relative_to(scan)
            paths[logical.relative_to(root).as_posix()]=logical
    return list(paths.values())

def result_relative(path):
    p=Path(path).resolve()
    for root in result_roots():
        if p.is_relative_to(root.resolve()): return p.relative_to(root.resolve())
    raise ValueError('Result outside managed data roots')

def is_result_path(path, subdir=''):
    p=Path(path).resolve()
    return any(p.is_relative_to((r/subdir).resolve()) for r in result_roots())


def app_path(path):
    """Resolve portable configuration paths against the application, not cwd."""
    p=Path(path)
    return p if p.is_absolute() else ROOT/p


def playback_path(path):
    """Accept only an existing final replay in either managed result tree."""
    p=locate(app_path(path)).resolve()
    if p.name!='playback.json' or not is_result_path(p) or not _io_path(p).is_file():
        raise ValueError('Invalid lite path')
    return _io_path(p)
