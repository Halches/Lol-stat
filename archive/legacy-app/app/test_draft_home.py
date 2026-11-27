import math
import unittest
import home_model as home

class HomeTests(unittest.TestCase):
    def test_missing_metrics_do_not_become_zero_and_valid_zero_is_kept(self):
        x=home.stats([{'w':None},{'w':1,'csm':0,'vsm':float('nan')},{'w':0,'csm':-1,'vsm':None}])
        self.assertEqual(x['n'],3);self.assertEqual(x['results'],2);self.assertEqual(x['wr'],50)
        self.assertEqual(x['csm'],0);self.assertEqual(x['csm_n'],1)
        self.assertIsNone(x['vsm']);self.assertIsNone(x['kda'])
        self.assertIsNone(home.stats([])['wr'])

    def test_kda_uses_totals_with_complete_match_samples(self):
        x=home.stats([{'k':10,'a':10,'d':1},{'k':0,'a':0,'d':9},{'k':99,'a':99}])
        self.assertEqual(x['kda'],2);self.assertEqual(x['kda_n'],2)
        self.assertEqual(home.stats([{'k':2,'a':4,'d':0}])['kda'],6)

    def test_period_and_recent_matches_are_sorted_by_time_not_input_order(self):
        games=[{'t':i,'w':int(i>=10),'c':'Ahri','pos':'MIDDLE'} for i in range(30)]
        season=home.snapshot(games);recent=home.snapshot(games,'recent')
        self.assertEqual(season['stats']['n'],30)
        self.assertEqual(recent['stats']['n'],20)
        self.assertEqual(recent['stats']['wr'],100)
        self.assertEqual(recent['games'][0]['t'],29)
        self.assertEqual(recent['frequent'][0]['stats']['n'],20)
        self.assertEqual(games[0]['t'],0)

    def test_selected_profile_must_match_full_riot_id_before_live_rank_is_used(self):
        account={'riot':'Player#EUW','puuid':'own'}
        self.assertTrue(home.live_profile({'riot':'player#euw'},account))
        self.assertFalse(home.live_profile({'riot':'Player#OTHER'},account))
        self.assertFalse(home.live_profile({'riot':'Another#EUW'},account))
        self.assertFalse(home.live_profile({'riot':'Player#EUW'},None))
        self.assertTrue(home.live_profile(None,account))

    def test_no_games_no_frequent_champions_or_fake_statistics(self):
        result=home.snapshot([])
        self.assertEqual(result['frequent'],[])
        for key in ('wr','kda','csm','vsm'):self.assertIsNone(result['stats'][key])

if __name__=='__main__':unittest.main()
