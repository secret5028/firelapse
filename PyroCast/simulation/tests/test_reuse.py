import unittest
import json,tempfile
from pathlib import Path
from unittest.mock import patch
from pyrocast_cfbt.reuse import scalar_sidecar,prime_completed
from pyrocast_cfbt.native import digest,execute

class ReuseTests(unittest.TestCase):
    def test_only_order_and_numeric_notation_are_equated(self):
        self.assertEqual(scalar_sidecar('&CFBT a=1e-2 b=.TRUE. /'),scalar_sidecar('&cfbt B=.true., a=0.010d0 /'))
        self.assertNotEqual(scalar_sidecar('&CFBT a=1 /'),scalar_sidecar('&CFBT a=1.00000000000001 /'))
        self.assertNotEqual(scalar_sidecar('&CFBT a=1 /'),scalar_sidecar('&CFBT a=1 b=.false. /'))
        self.assertNotEqual(scalar_sidecar('&CFBT a=1 /'),scalar_sidecar('&CFBT a=.true. /'))
        self.assertNotEqual(scalar_sidecar('&CFBT a=0 /'),scalar_sidecar('&CFBT a=-0 /'))

    def test_ambiguous_or_unsupported_syntax_is_rejected(self):
        for value in ('&CFBT a=1 A=2 /','&CFBT a(1)=1 /','&CFBT a=NaN /','&CFBT a=1 / trailing','&CFBT a=1 b= /'):
            with self.subTest(value=value),self.assertRaises(ValueError):scalar_sidecar(value)

    def test_reuse_checks_signatures_outputs_and_future_exact_deck(self):
        root=Path(__file__).resolve().parents[1]/'build/unit_tmp';root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as tmp:
            self.assertTrue(Path(tmp).resolve().is_relative_to(root.resolve()))
            folder=Path(tmp);source=folder/'source';source.mkdir();engine=folder/'engine';engine.write_bytes(b'test engine')
            (source/'case.in').write_text('exact deck\n','ascii')
            (source/'case.cfbt').write_text('&CFBT a=1 b=.true. /','ascii')
            (source/'case.log').write_text('NORMAL EXIT','ascii')
            (source/'case_compartments.csv').write_text('test output','ascii')
            saved={'signature':{'engine':digest(engine),'input':digest(source/'case.in'),'sidecar':digest(source/'case.cfbt'),
                                'required_horizon_s':180.,'flags':['-V'],'validator_version':2},
                   'run':{'normal_exit':True,'wall_seconds':10.},
                   'files':{name:digest(source/name) for name in ('case.log','case_compartments.csv')}}
            (source/'completed.json').write_text(json.dumps(saved),'utf-8')
            side='&CFBT b=.TRUE. a=1.0 /'
            with patch('pyrocast_cfbt.reuse.load_result'):
                prime_completed(source,folder/'copy',engine,side,180.)
                with self.assertRaisesRegex(ValueError,'settings differ'):
                    prime_completed(source,folder/'different',engine,'&CFBT a=2 b=.true. /',180.)
                with self.assertRaisesRegex(ValueError,'signature mismatch'):
                    prime_completed(source,folder/'short',engine,side,3600.)
                (source/'case_compartments.csv').write_text('corrupt','ascii')
                with self.assertRaisesRegex(ValueError,'output changed'):
                    prime_completed(source,folder/'corrupt',engine,side,180.)
            with patch('pyrocast_cfbt.native.subprocess.Popen',side_effect=RuntimeError('Would launch new native calculation')),patch('pyrocast_cfbt.native.load_result',return_value='reused') as loader:
                self.assertEqual(execute(engine,folder/'copy','exact deck\n',side,180.,60.),'reused')
                self.assertTrue(loader.call_args.args[2]['cache_hit'])
                with self.assertRaisesRegex(RuntimeError,'Would launch'):
                    execute(engine,folder/'copy','different deck\n',side,180.,60.)

if __name__=='__main__':unittest.main()
