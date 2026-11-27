"""Draft regressions: correct role/sample, hidden data and settings compatibility."""
import json
import math
import tempfile
import unittest
from types import SimpleNamespace
import core
import draft_model


class PairRecommendations(unittest.TestCase):
    def test_missing_pick_preserves_opposing_role_rows(self):
        slots = draft_model.role_slots([{'c':'Lux', 'pos':'UTILITY'}, {'c':'Ahri', 'pos':'MIDDLE'}], core.ROLES)
        self.assertEqual([player.get('c') for player in slots], [None, None, 'Ahri', None, 'Lux'])

    def test_unknown_role_is_not_labelled_as_a_known_role(self):
        slots = draft_model.role_slots([{'c':'X', 'pos':''}, {'c':'Ahri', 'pos':'MIDDLE'}], core.ROLES)
        self.assertEqual(slots[0], {'c':'X', 'pos':''})
        self.assertEqual(slots[2], {'c':'Ahri', 'pos':'MIDDLE'})

    def test_enemy_winrate_is_inverted_once_and_retains_role(self):
        rows = draft_model.recommendations(None, 'Viktor', 'MIDDLE', 'enemy', 'TOP',
                 {'Ahri': (46.8, -2.1, 1240)}, {}, scope='all')
        self.assertEqual(rows[0]['role'], 'MIDDLE')
        self.assertAlmostEqual(rows[0]['winrate'], 53.2)
        self.assertEqual(rows[0]['games'], 1240)

    def test_allied_winrate_not_inverted_and_uses_selected_role(self):
        rows = draft_model.recommendations(None, 'Jinx', 'BOTTOM', 'ally', 'MIDDLE', {},
                {('TOP', 'Ahri'): (61, 4, 800), ('MIDDLE', 'Ahri'): (54, 2, 1200)}, scope='all')
        self.assertEqual([(x['winrate'], x['role']) for x in rows], [(54, 'MIDDLE')])

    def test_pool_bans_and_already_selected_champions(self):
        rows = draft_model.recommendations(None, 'Viktor', 'MIDDLE', 'enemy', 'MIDDLE',
                 {'Ahri': (45, -3, 1000), 'Syndra': (47, -2, 800), 'Viktor': (50, 0, 900)}, {},
                 {'MIDDLE': ['Ahri', 'Syndra', 'Viktor']}, unavailable=['Ahri'])
        self.assertEqual([x['champion'] for x in rows], ['Syndra'])

    def test_unknown_role_and_small_or_corrupt_sample_are_not_recommendations(self):
        self.assertEqual(draft_model.recommendations(None, 'X', '', 'enemy', 'MIDDLE', {}, {}, scope='all'), [])
        rows = draft_model.recommendations(None, 'X', 'MIDDLE', 'enemy', 'MIDDLE',
                 {'A': (45, -3, 10), 'B': (math.nan, 1, 200), 'C': (110, 2, 900)}, {}, scope='all')
        self.assertEqual(rows, [])

    def test_joint_winrate_not_fabricated_from_independent_fields(self):
        full = {'pick': {'wr_runes': 56, 'n_runes': 2400, 'wr_core': 63, 'n_core': 800}}
        option = draft_model.build_options(full)[0]
        self.assertIsNone(option['joint_winrate'])
        self.assertIsNone(option['joint_games'])
        self.assertEqual(option['item_winrate'], 63)

    def test_strict_pool_and_all_champions_are_distinct(self):
        data = core.Data({'names': {'A': 'A', 'B': 'B'}, 'ids': {'1':'A','2':'B'}, 'items': {},
             'lola': {'A|MIDDLE': {'wr': 50, 'n': 200}, 'B|MIDDLE': {'wr': 54, 'n': 500}},
             'players': {'x': {'g': []}}, 'pools': {'x': {'MIDDLE': ['A']}}})
        player = core.Player(data, 'x')
        self.assertEqual([p['c'] for p in core.draft_suggest(player, 'MIDDLE', scope='pool')['picks']], ['A'])
        self.assertEqual({p['c'] for p in core.draft_suggest(player, 'MIDDLE', scope='all')['picks']}, {'A','B'})

    def test_legacy_auto_export_is_preserved_when_loading_settings(self):
        import ui
        with tempfile.TemporaryDirectory() as home:
            with open(home+'/settings.json', 'w') as f:
                json.dump({'auto_parts': {'runes': True, 'items': False, 'spells': False}}, f)
            settings = ui.Settings(home)
            self.assertTrue(settings['auto_import'])
            settings['auto_import'] = False
            settings.save()
            reloaded = ui.Settings(home)
            self.assertFalse(reloaded['auto_import'])
            reloaded.save()
            self.assertFalse(ui.Settings(home)['auto_import'])


if __name__ == '__main__': unittest.main()
