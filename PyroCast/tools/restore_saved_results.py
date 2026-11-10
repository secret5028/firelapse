"""Restore tracked replay/test inputs without overwriting a user's results."""
import argparse
import gzip
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def restore(root=ROOT):
    root = Path(root).resolve()
    source = root / 'saved_results'
    destination = root / 'simulation/results'
    count = 0
    for archive in sorted(source.rglob('*.gz')):
        target = destination / archive.relative_to(source).with_suffix('')
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as output:
            temporary = Path(output.name)
            try:
                with gzip.open(archive, 'rb') as stream:
                    shutil.copyfileobj(stream, output)
            except BaseException:
                output.close()
                temporary.unlink(missing_ok=True)
                raise
        try:
            # Another process may have restored it while we were decompressing.
            if not target.exists():
                temporary.rename(target)
                count += 1
        finally:
            temporary.unlink(missing_ok=True)
    return count

if __name__ == '__main__':
    print('Restored saved files:', restore())
