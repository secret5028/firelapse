import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation')]
from lite_ai_briefing import briefing_value,basic_briefing
from run_cfast_mc import summarize_batch


class ReviewPropagation(unittest.TestCase):
    def test_input_review_does_not_become_tactical_advice(self):
        class Service:
            def case(self,args):return dict(physical_validation=dict(status='unverified',review_required=[dict(message='입력 가정 검토 필요: Fire')]))
            def call(self,*args):raise AssertionError('Review must not invoke tactical tools')
        for fn in (briefing_value,basic_briefing):
            result=fn(Service(),dict(building='B',case='C'))
            self.assertEqual(result['status'],'unverified')
            self.assertEqual(result['rules'],[])
            self.assertIn('입력 가정 검토 필요',result['text'])

    def test_mc_counts_review_separately_from_physical_failure(self):
        rows=[dict(sample_id='S00',kind='random',complete=True,ranking_eligible=False,physical_validation={'status':'unverified'}),
              dict(sample_id='S01',kind='random',complete=True,ranking_eligible=False,physical_validation={'status':'physically_invalid'})]
        result=summarize_batch(rows)
        self.assertEqual(result['eligible_completed'],0)
        self.assertEqual(result['excluded_unverified'],1)
        self.assertEqual(result['excluded_physically_invalid'],1)


if __name__=='__main__':unittest.main()
