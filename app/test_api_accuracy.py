"""Regressions around missing source data, display and the history update cycle."""
from contextlib import chdir
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import core
import draft_model
import matchup_data
import performance_model
from app_services import ApplicationServices
from test_core import D, snap
from test_matchup_data import DATA, FIXTURE

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import fetch


class SourceAccuracy(unittest.TestCase):
    def test_empty_role_sample_never_reads_another_lane(self):
        fetcher = Mock(return_value={'counters': []})
        app = SimpleNamespace(data=D, player=None, lola_fetch=fetcher,
                              lola_state={('counter','RekSai','UTILITY'): 'ok'})
        rows = ApplicationServices.matchup_lines(app, {'c':'RekSai','pos':'UTILITY'}, 1, [], {'role':'UTILITY'})
        fetcher.assert_called_once_with('counter','RekSai','UTILITY')
        self.assertIn('Мало игр', rows[0][0])

    def test_missing_cs_keeps_zero_distinct_across_hint_overlay_and_postgame(self):
        for farm in (None, 0, 81):
            with self.subTest(farm=farm):
                raw = snap(600)
                scores = raw['allPlayers'][0]['scores']
                if farm is None:
                    scores.pop('creepScore')
                else:
                    scores['creepScore'] = farm
                game = core.Game(raw, D)
                engine = core.Engine(D, None)
                hints = engine.tick(game)
                self.assertEqual(any(h.id == 'bench' for h in hints), farm is not None)
                self.assertEqual(performance_model.live_values(game)['csm'], None if farm is None else farm / 10)
                goals = core.postgame(engine, game, None)['goals']
                self.assertEqual(any(row[0] == 'CS в минуту' for row in goals), farm is not None)

    def test_matchup_header_is_visible_but_not_an_importable_variant(self):
        graph = json.loads(re.search(r'<script[^>]*>(.*?)</script>', FIXTURE.read_text(), re.S)[1])
        packet = next(o for o in graph['objs'] if isinstance(o, dict) and 'header' in o and 'summary' in o)
        del packet['summary']
        page = '<script type="qwik/json">'+json.dumps(graph)+'</script>'
        value = matchup_data.parse(page,'Ahri','MIDDLE','Viktor',DATA)
        self.assertGreater(value['games'], 0)
        self.assertTrue(0 <= value['wr'] <= 100)
        self.assertEqual(draft_model.build_options(value), [])
        self.assertIsNone(matchup_data.parse(page,'Ahri','TOP','Viktor',DATA))
        recent = matchup_data.parse(FIXTURE.read_text(), 'Ahri','MIDDLE','Viktor',DATA)
        recent['matchup']['patch'] = '30'
        recent['games'] = 10981
        merged = matchup_data.with_recent_build(value, recent)
        self.assertEqual((merged['wr'],merged['games']), (value['wr'],value['games']))
        self.assertEqual(merged['build_games'], 10981)
        self.assertEqual(merged['pick'], recent['pick'])
        recent['matchup']['opponent'] = 'Lux'
        self.assertIs(matchup_data.with_recent_build(value, recent), value)


class HistoryDownload(unittest.TestCase):
    def test_timeline_retried_outside_latest_page_and_acknowledged_only_after_analysis(self):
        mid = 'EUW1_1'
        match = {'metadata':{'matchId':mid}, 'info':{'queueId':420,'gameDuration':600}}
        timeline = {'metadata':{'matchId':mid}, 'info':{'frames':[{}]}}
        with tempfile.TemporaryDirectory() as tmp, chdir(tmp), patch.dict(os.environ, {'INCREMENTAL':'1','GITHUB_OUTPUT':'out'}), \
                patch.object(fetch, 'puuids', return_value={}), patch.object(fetch, 'listed_ids', side_effect=[{mid},set(),set()]), \
                patch.object(fetch, 'get', side_effect=[match,None,timeline]) as get:
            Path('data').mkdir()
            Path('data/EUW1_1_tl.json').write_text('null')
            fetch.run()
            self.assertEqual(json.loads(fetch.SEEN.read_text()), [])
            self.assertEqual(json.loads(fetch.PENDING.read_text()), [mid])
            fetch.run()
            fetch.run()
            self.assertEqual(get.call_count, 3)
            self.assertEqual(Path('out').read_text().splitlines(), ['new=0','new=1','new=1'])
            fetch.ARCHIVE.write_text(json.dumps([{'id':mid}]))
            fetch.run(acknowledge=True)
            self.assertEqual(json.loads(fetch.PENDING.read_text()), [])
            self.assertEqual(json.loads(fetch.SEEN.read_text()), [mid])

    def test_legacy_seen_skips_archived_and_retries_only_missing_history(self):
        mid = 'EUW1_2'
        with tempfile.TemporaryDirectory() as tmp, chdir(tmp), patch.dict(os.environ, {'INCREMENTAL':'1'}), \
                patch.object(fetch, 'puuids', return_value={}), patch.object(fetch, 'listed_ids', return_value=set()), \
                patch.object(fetch, 'get', return_value=None) as get:
            fetch.SEEN.write_text(json.dumps(['EUW1_1', mid]))
            fetch.ARCHIVE.write_text(json.dumps([{'id':'EUW1_1'}]))
            fetch.run()
            self.assertEqual(get.call_args.args[0], fetch.MATCH_API + mid)
            self.assertEqual(json.loads(fetch.SEEN.read_text()), ['EUW1_1'])
            self.assertEqual(json.loads(fetch.PENDING.read_text()), [mid])

    def test_account_error_does_not_report_zero(self):
        with tempfile.TemporaryDirectory() as tmp, chdir(tmp), patch.dict(os.environ, {'GITHUB_OUTPUT':'out'}), \
                patch.object(fetch, 'puuids', side_effect=OSError('403')):
            with self.assertRaises(OSError):
                fetch.run()
            self.assertFalse(Path('out').exists())
