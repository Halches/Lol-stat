import unittest
import lcu
import ui
from types import SimpleNamespace
import profile_ranks as ranks

class ProfileRanksTests(unittest.TestCase):
    def ranked(self,tier='EMERALD',division='IV',points=17):
        return {'tier':tier,'division':division,'leaguePoints':points,'wins':10,'losses':5}

    def test_each_queue_has_its_own_rank_and_one_client_read(self):
        raw={'queueMap':{'RANKED_SOLO_5x5':self.ranked(),'RANKED_FLEX_SR':self.ranked('GOLD','II',55),
                         'RANKED_TFT':self.ranked('DIAMOND','I',92)}}
        client=lcu.LCU();calls=[]
        client.call=lambda path:(calls.append(path),raw)[1]
        result=client.ranked_overview()
        self.assertEqual(calls,['/lol-ranked/v1/current-ranked-stats'])
        self.assertEqual([result[k]['tier'] for k in ('solo','flex','tft')],['EMERALD','GOLD','DIAMOND'])
        self.assertEqual(ranks.legacy_solo(result),{'tier':'EMERALD','div':'IV','lp':17,'w':10,'l':5})

    def test_missing_unknown_and_unranked_are_distinct(self):
        result=ranks.parse({'queueMap':{'RANKED_SOLO_5x5':{'tier':'NONE'},
                            'RANKED_FLEX_SR':{'tier':'NONE','isProvisional':True}}})
        self.assertEqual(result['solo']['state'],'unranked')
        self.assertEqual(result['flex']['state'],'provisional')
        self.assertEqual(result['tft']['state'],'unknown')
        self.assertIsNone(ranks.legacy_solo(result))
        for value in (None,[],{'queueMap':[]},{'queueMap':{'RANKED_TFT':{}}}):
            self.assertEqual(ranks.parse(value)['tft']['state'],'unknown')

    def test_invalid_lp_tier_division_and_mismatched_queue_are_not_shown(self):
        cases=[self.ranked(points=-1),self.ranked(points=True),self.ranked(points=float('nan')),
               self.ranked(tier='WOOD'),self.ranked(tier={}),self.ranked(division='V'),dict(self.ranked(),queueType='RANKED_TFT')]
        for value in cases:self.assertEqual(ranks.parse({'queueMap':{'RANKED_SOLO_5x5':value}})['solo']['state'],'unknown')
        result=ranks.parse({'queueMap':{'RANKED_TFT':self.ranked('MASTER','',0)}})
        self.assertEqual(result['tft']['state'],'ranked')
        self.assertEqual(result['tft']['lp'],0)
        self.assertEqual(result['tft']['div'],'')

    def test_retired_arena_rating_is_never_presented_as_current_rank_or_fame(self):
        result=ranks.parse({'queueMap':{'CHERRY':{'ratedTier':'GLADIATOR','ratedRating':9000,'tier':'CHALLENGER','leaguePoints':9000}}})
        self.assertEqual(result['arena'],{'state':'fame_unavailable'})
        self.assertNotIn('lp',result['arena'])
        self.assertNotIn('fame',result['arena'])

    def test_disconnect_clears_live_account_and_queue_ranks(self):
        calls=[]
        app=SimpleNamespace(account={'riot':'Player#TAG','ranks':{'flex':{'state':'ranked'}}},my_rank={'tier':'GOLD'},panel_sync=lambda:calls.append('refresh'))
        ui.App.on_me(app,None)
        self.assertIsNone(app.account)
        self.assertIsNone(app.my_rank)
        self.assertEqual(calls,['refresh'])

    def test_client_error_is_unknown_not_unranked(self):
        client=lcu.LCU()
        def fail(path):raise OSError('offline')
        client.call=fail
        result=client.ranked_overview()
        self.assertTrue(all(result[k]['state']=='unknown' for k in ('solo','flex','tft')))
        self.assertIsNone(result['fetched_at'])

if __name__=='__main__':unittest.main()
