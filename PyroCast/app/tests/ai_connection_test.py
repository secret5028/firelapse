import sys, json, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import ai_connection as con
import lite_ai_fuel as fuel
import model_import

class ConnectionTest(unittest.TestCase):
    def setUp(self):
        self.p=patch.object(con,'HOSTING',True);self.p.start();con.disconnect()
        self.body=dict(action='connect',base_url='https://example.invalid/v1',model='vision-test',api_key='test-secret-not-a-real-key')
    def tearDown(self):con.disconnect();self.p.stop()
    def connect(self):return con.connect(self.body,lambda *args:'OK')
    def test_status_contains_no_key(self):
        result=self.connect();self.assertTrue(result['connected']);self.assertNotIn(self.body['api_key'],json.dumps(result));self.assertNotIn('api_key',result)
    def test_probe_failure_does_not_replace_connection(self):
        self.connect()
        with self.assertRaises(ValueError):con.connect(dict(self.body,model='bad'),lambda *a:(_ for _ in ()).throw(Exception(self.body['api_key'])))
        self.assertEqual(con.public_status()['model'],'vision-test')
    def test_settings_and_scan_share_broker(self):
        self.connect();cfg=fuel.settings();self.assertTrue(cfg['_runtime']);self.assertNotIn(self.body['api_key'],json.dumps(cfg));self.assertTrue(model_import.configured())
    def test_disconnect_removes_runtime(self):
        self.connect();con.disconnect();self.assertIsNone(con.runtime_settings())
        with self.assertRaises(ValueError):con.complete([dict(role='user',content='hello')])
    def test_reject_unsafe_url_and_fields(self):
        for base in ['http://example.invalid/v1','https://user:secret@example.invalid/v1','https://example.invalid/v1?key=abc']:
            with self.assertRaises(ValueError):con.connect(dict(self.body,base_url=base),lambda *a:'OK')
        with self.assertRaises(ValueError):con.connect(dict(self.body,extra=True),lambda *a:'OK')
    def test_provider_secret_echo_rejected(self):
        with self.assertRaisesRegex(ValueError,'연결 실패'):con.connect(self.body,lambda *a:self.body['api_key'])
        self.assertFalse(con.public_status()['connected'])
    def test_completion_uses_private_key_without_returning_it(self):
        self.connect()
        with patch.object(fuel,'completion',return_value='answer') as mock:
            self.assertEqual(con.complete([dict(role='user',content='hi')]),'answer')
            self.assertEqual(mock.call_args.args[1],self.body['api_key']);self.assertNotIn('_runtime',mock.call_args.args[0])
    def test_completion_secret_echo_rejected(self):
        self.connect()
        with patch.object(fuel,'completion',return_value=self.body['api_key']):
            with self.assertRaises(ValueError):con.complete([dict(role='user',content='hi')])
if __name__=='__main__':unittest.main()
