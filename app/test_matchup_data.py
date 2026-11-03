"""Recorded public matchup response: context checks and correct source variants."""
import json
import re
from pathlib import Path
from types import SimpleNamespace
import unittest
import core
import matchup_data

FIXTURE = Path(__file__).parent/'dev/fixtures/lolalytics-matchup.html'
DATA = SimpleNamespace(ids={'103':'Ahri','112':'Viktor','99':'Lux'})

class MatchupDataTests(unittest.TestCase):
    def test_recorded_page_has_two_distinct_matchup_builds(self):
        value = matchup_data.parse(FIXTURE.read_text(), 'Ahri', 'MIDDLE', 'Viktor', DATA)
        self.assertEqual(value['matchup']['opponent'], 'Viktor')
        self.assertEqual(value['matchup']['region'], 'all')
        self.assertTrue(value['games'] > 0)
        self.assertEqual(value['pick']['rune_stat_kind'], 'keystone')
        self.assertEqual(value['pick']['core'], [3118,3020,4645])
        self.assertEqual(value['win']['core'], [3118,3158,3041])
        self.assertNotEqual(value['pick']['skills'], value['win']['skills'])
        self.assertIsNone(value['pick']['wr_core'])  # Individual item stats are not a joint core sample.
        self.assertTrue(len(core.lola_build_items(value['pick'])) >= 3)

    def test_general_or_other_matchup_never_substitutes_for_requested_opponent(self):
        for champion, role, opponent in [('Ahri','MIDDLE','Lux'), ('Ahri','TOP','Viktor'), ('Lux','MIDDLE','Viktor')]:
            self.assertIsNone(matchup_data.parse(FIXTURE.read_text(), champion, role, opponent, DATA))

    def test_wrong_region_and_broken_graph_are_rejected(self):
        html = FIXTURE.read_text()
        graph = json.loads(re.search(r'<script[^>]*>(.*?)</script>', html, re.S)[1])
        params = next(o for o in graph['objs'] if isinstance(o,dict) and 'vsCid' in o)
        params['region'] = params['champion']  # resolves to "ahri", not all regions
        self.assertIsNone(matchup_data.parse('<script type="qwik/json">'+json.dumps(graph)+'</script>', 'Ahri','MIDDLE','Viktor',DATA))
        self.assertIsNone(matchup_data.parse('<script type="qwik/json">{"objs":[{"header":"0","summary":"0","nav":"0"}]}</script>', 'Ahri','MIDDLE','Viktor',DATA))

    def test_request_has_both_lane_filters(self):
        url = matchup_data.url('Ahri', 'MIDDLE', 'Viktor')
        self.assertIn('/ahri/vs/viktor/build/', url)
        self.assertIn('lane=middle', url)
        self.assertIn('vslane=middle', url)
        self.assertNotIn('region=euw', url)  # Matchup source serves all regions, kept distinct from general EUW.

    def test_missing_highest_win_variant_is_not_replaced_with_popular(self):
        graph = json.loads(re.search(r'<script[^>]*>(.*?)</script>', FIXTURE.read_text(), re.S)[1])
        summary = next(o for o in graph['objs'] if isinstance(o,dict) and set(o) == {'pick','win'})
        del summary['win']
        html = '<script type="qwik/json">'+json.dumps(graph)+'</script>'
        value = matchup_data.parse(html, 'Ahri','MIDDLE','Viktor', DATA)
        self.assertTrue(value['pick'])
        self.assertIsNone(value['win'])

if __name__ == '__main__': unittest.main()
