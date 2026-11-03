import unittest
import champion_rank
import champion_rank_graphs as model


def page(number=1,count=100):
    header=f'<link rel="canonical" href="{model.url("Ahri",number).partition(".com")[2]}"/><img src="champion-icons/16.21/64/103.png">Rankings · All regions'
    rows=''
    for rank in range((number-1)*100+1,(number-1)*100+count+1):
        rows+=f'<div class="lolg-rk__row"><span class="lolg-rk__num">{rank}.</span><a class="lolg-rk-who" href="/summoner/euw/Player{rank}-TAG"><img alt="Player{rank}#TAG"><i class="lolg-rk-who__region">EUW</i></a></div>'
    return header+rows


class ChampionRankGraphs(unittest.TestCase):
    def test_all_ten_pages_and_exact_identity(self):
        published=[]
        board=model.fetch(103,'Ahri',published.append,lambda url:page(int(url.rsplit('-',1)[1]) if '/page-' in url else 1))
        self.assertEqual(board['coverage'],1000);self.assertFalse(board['partial'])
        self.assertEqual([p['coverage'] for p in published],list(range(100,1001,100)))
        found=champion_rank.lookup(board,'Ahri','player1000#tag','EUW1')
        self.assertEqual(found['rank'],1000);self.assertEqual(found['source'],'LeagueOfGraphs')
        self.assertIsNone(champion_rank.lookup(board,'Ahri','player1000#wrong','EUW1'))

    def test_wrong_context_and_region_are_rejected(self):
        text=page()
        for changed in (text.replace('All regions','EUW'),text.replace('/64/103.png','/64/1.png'),text.replace('/summoner/euw/','/summoner/kr/'),text.replace('/summoners/ahri','/summoners/annie')):
            self.assertIsNone(model.parse(changed,103,'Ahri'))

    def test_partial_results_survive_failed_next_page(self):
        def read(url):
            if '/page-' in url:raise TimeoutError()
            return page()
        board=model.fetch(103,'Ahri',read=read)
        self.assertEqual(board['coverage'],100);self.assertTrue(board['partial'])
        self.assertIsNone(champion_rank.lookup(board,'Ahri','Player999#TAG','EUW'))

    def test_paginated_source_uses_base_canonical_but_real_global_ranks(self):
        text=page(2).replace('/ahri/page-2','/ahri')
        self.assertEqual(model.parse(text,103,'Ahri',2)['rows'][0]['rank'],101)
        self.assertIsNone(model.parse(text,103,'Ahri',1))

    def test_missing_identity_stays_unknown_and_does_not_block_later_ranks(self):
        text=page(10).replace('Player999#TAG','').replace('Player999-TAG','')
        chunk=model.parse(text,103,'Ahri',10)
        self.assertEqual(chunk['coverage'],99)
        self.assertEqual(chunk['scanned_to'],1000)
        self.assertNotIn(999,[r['rank'] for r in chunk['rows']])

    def test_missing_or_duplicate_rank_is_not_renumbered(self):
        self.assertIsNone(model.parse(page().replace('>50.</span>','>49.</span>'),103,'Ahri'))


if __name__=='__main__':unittest.main()
