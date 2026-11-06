"""A missing raw matrix must never permit an unsealed portable ranking."""
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from export_ui_attention import result_index,KINDS

class PortableIndexTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name)
        self.playback=self.folder/'playback.json';self.playback.write_bytes(b'{"saved":true}')
        self.index={'schema':'pyrocast.result-index/1','threshold':70,'kinds':list(KINDS),
                    'complete':True,'attention_rooms':['R1'],'attention_room_count':1,'unknown_rooms':[]}
        self.seal={'schema':'firelapse.portable-result-index/1','index':self.index,
                   'index_sha256':hashlib.sha256(json.dumps(self.index,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                   'playback_sha256':hashlib.sha256(self.playback.read_bytes()).hexdigest()}
        self.write()
    def write(self):
        (self.folder/'portable-result-index.json').write_text(json.dumps(self.seal),'utf8')
    def tearDown(self):self.temp.cleanup()
    def test_saved_index(self):self.assertEqual(result_index(self.folder/'result.json'),self.index)
    def test_changed_playback_rejected(self):
        self.playback.write_bytes(b'{}')
        with self.assertRaises(ValueError):result_index(self.folder/'result.json')
    def test_changed_index_rejected(self):
        self.seal['index']['attention_room_count']=99;self.write()
        with self.assertRaises(ValueError):result_index(self.folder/'result.json')
    def test_missing_evidence_rejected(self):
        (self.folder/'portable-result-index.json').unlink()
        with self.assertRaises(ValueError):result_index(self.folder/'result.json')
    def test_raw_result_still_preferred(self):
        raw={'ok':True,'room_summary':[{'original_room':'R2','cell':'C2'}], 't':[0],
             'shared_conditions':{'rooms':{'C2':{k:{'scores':{'degree':[.8]}} for k in KINDS}}}}
        (self.folder/'result.json').write_text(json.dumps(raw),'utf8')
        self.assertEqual(result_index(self.folder/'result.json')['attention_rooms'],['R2'])

if __name__=='__main__':unittest.main()
