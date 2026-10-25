from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from engine_sources import VENDOR, ORDER, verify_upstream
from prepare_engine import prepare
from verify_engine_boundary import verify_generated
from extensions.cfbt.hooks import render
import fetch_cfast


@contextmanager
def local_temp():
    base=ROOT/'build/unit_tmp';base.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=base) as value:
        path=Path(value).resolve()
        if not path.is_relative_to(ROOT.resolve()):raise ValueError('Unsafe test cleanup target')
        yield path


class EngineBoundaryTests(unittest.TestCase):
    def test_pinned_upstream_is_intact(self):
        self.assertEqual(verify_upstream()['verified_files'],28)

    def test_changed_upstream_and_changed_lock_are_rejected(self):
        with local_temp() as folder:
            copy=folder/'vendor';shutil.copytree(VENDOR,copy)
            source=copy/'Source/fire.f90';source.write_bytes(source.read_bytes()+b'\n! changed\n')
            with self.assertRaisesRegex(ValueError,'Upstream CFAST was modified'):
                verify_upstream(copy)
            lock=copy/'sources.json';lock.write_bytes(lock.read_bytes()+b'\n')
            with self.assertRaisesRegex(ValueError,'source lock was modified'):
                verify_upstream(copy)

    def test_extra_vendor_code_and_ambiguous_hook_anchor_are_rejected(self):
        with local_temp() as folder:
            copy=folder/'vendor';shutil.copytree(VENDOR,copy)
            (copy/'Source/project_code.f90').write_text('! project code')
            with self.assertRaisesRegex(ValueError,'inventory changed'):
                verify_upstream(copy)
        originals={n+'.f90':(VENDOR/'Source'/(n+'.f90')).read_text() for n in ORDER}
        originals['fire.f90']=originals['fire.f90'].replace('    nfire = 0\n','    nfire = 0\n    nfire = 0\n')
        with self.assertRaisesRegex(ValueError,'anchor changed'):
            render(originals)

    def test_generated_sources_are_reproducible_and_edits_are_detected(self):
        with local_temp() as folder:
            prepare(folder)
            report=verify_generated(folder)
            self.assertEqual(report['hook_count'],31)
            self.assertEqual(len(report['patched_generated_files']),7)
            source=folder/'Source/fire.f90';source.write_bytes(source.read_bytes()+b'\n! manual edit\n')
            with self.assertRaisesRegex(ValueError,'Generated file was edited'):
                verify_generated(folder)

    def test_fetch_is_read_only_for_existing_verified_sources(self):
        before=(VENDOR/'sources.json').read_bytes()
        with patch('fetch_cfast.urllib.request.urlopen',side_effect=AssertionError('No network expected')):
            record=fetch_cfast.fetch('fire')
        self.assertEqual(record['file'],'fire.f90')
        self.assertEqual(before,(VENDOR/'sources.json').read_bytes())


if __name__=='__main__':unittest.main()
