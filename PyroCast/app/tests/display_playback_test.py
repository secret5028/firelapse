import copy,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation')]
from display_playback import display_copy,save_playback

class DisplayPrecision(unittest.TestCase):
    def test_rounding_is_copy_only_preserves_flags_identity_and_null(self):
        source={'case_id':'unaltered','Tu':[571.766451359,None],
                'conditions':{'FO':{'scores':{'degree':[.9999999,1.0000001]},'occurred':[False,True]}},'tiny':-1e-12}
        original=copy.deepcopy(source);display=display_copy(source)
        self.assertEqual(source,original)
        self.assertEqual(display['Tu'],[571.76645,None]);self.assertEqual(display['tiny'],0)
        self.assertEqual(display['case_id'],'unaltered')
        self.assertEqual(display['conditions']['FO']['occurred'],[False,True])
        self.assertEqual(display['conditions']['FO']['scores']['degree'],[.99999,1.0])

    def test_70_and_100_decisions_never_cross_on_rounding(self):
        values=[.6999999,.7,.7000001,.9999999,1.,1.0000001,1.23456789]
        display=display_copy({'degree':values,'proximity':values,'potential':values})
        for key in ('degree','proximity','potential'):
            for boundary in (.7,1.):
                self.assertEqual([x>=boundary for x in values],[x>=boundary for x in display[key]])
        self.assertEqual(display['degree'][-1],1.23457)

    def test_compact_save_idempotent_and_raw_file_untouched(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);raw=folder/'raw.csv';raw.write_bytes(b'1.234567890123\n')
            data={'series':[1.234567890123]*100,'gate':[True,None,False]}
            saved=save_playback(folder/'playback.json',data)
            self.assertEqual(saved,display_copy(saved))
            self.assertEqual(json.loads((folder/'playback.json').read_text()),saved)
            self.assertLess((folder/'playback.json').stat().st_size,len(json.dumps(data,indent=2)))
            self.assertEqual(raw.read_bytes(),b'1.234567890123\n')

    def test_nonfinite_cannot_be_saved_as_valid_display(self):
        with self.assertRaises(ValueError):display_copy({'Tu':[float('nan')]})

if __name__=='__main__':unittest.main()
