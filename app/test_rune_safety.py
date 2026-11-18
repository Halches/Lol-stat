import unittest
from unittest.mock import Mock, call, patch

import core
from lcu import LCU

PAGES = '/lol-perks/v1/pages'
CURRENT = '/lol-perks/v1/currentpage'
PERKS = [8437, 8446, 8444, 8451, 8410, 8345]
SHARDS = [5008, 5008, 5001]


class RuneImportTests(unittest.TestCase):
    def setUp(self):
        self.client = LCU()
        self.mine = dict(name='LoL Helper: прежняя', isEditable=True, id=3)
        self.personal = dict(name='Личная', isEditable=True, id=2)
        self.saved = dict(primaryStyleId=8400, subStyleId=8300, selectedPerkIds=PERKS + SHARDS,
                          name='LoL Helper: Мундо', id=3, isEditable=True)

    def run_import(self, answers):
        self.client.call = Mock(side_effect=answers)
        return self.client.set_runes('Мундо', 8400, 8300, PERKS, SHARDS)

    def test_rejected_write_leaves_all_pages_in_place(self):
        for pages, verb in (([self.personal], 'POST'), ([self.mine, self.personal], 'PUT')):
            with self.subTest(verb=verb):
                self.assertFalse(self.run_import([pages, OSError('отказ')]))
                requests = self.client.call.call_args_list
                self.assertEqual(len(requests), 2)
                self.assertEqual(requests[1].args[:2], (PAGES if verb == 'POST' else PAGES + '/3', verb))

    def test_in_place_update_then_readback(self):
        self.assertTrue(self.run_import([[self.mine, self.personal], None, None, self.saved]))
        self.assertEqual(self.client.call.call_args_list[-2:], [call(CURRENT, 'PUT', 3), call(CURRENT)])

    def test_partial_results(self):
        for active, message in ((self.personal, 'но не выбрана'), (None, 'не подтверждена'),
                                (dict(self.saved, subStyleId=8200), 'отличается'),
                                (dict(self.saved, selectedPerkIds=PERKS + [5005, 5008, 5001]), 'отличается')):
            with self.subTest(message=message):
                self.assertFalse(self.run_import([[self.personal], self.saved, OSError('отказ'), active]))
                self.assertIn(message, self.client.last_error)

    def test_no_body_after_create_reconciles_without_second_post(self):
        self.assertTrue(self.run_import([[self.personal], None, [self.saved], None, self.saved]))
        self.assertEqual(sum(len(c.args) > 1 and c.args[1] == 'POST'
                             for c in self.client.call.call_args_list), 1)

    def test_invalid_loadout_causes_no_client_requests(self):
        self.client.call = Mock()
        for primary, secondary, perks, shards in (
                (8400, 8400, PERKS, SHARDS), (8400, 8300, PERKS[:-1] + [123456], SHARDS),
                (8400, 8300, PERKS[:-1] + [8316], SHARDS), (8400, 8300, PERKS, [])):
            self.assertFalse(self.client.set_runes('Мундо', primary, secondary, perks, shards))
        self.client.call.assert_not_called()

    def test_offline(self):
        with patch.object(self.client, 'find', return_value=False):
            self.assertFalse(self.client.set_runes('Мундо', 8400, 8300, PERKS, SHARDS))
        self.assertIn('недоступен', self.client.last_error)

    def test_old_lolalytics_cache(self):
        old = dict(prim=8400, sec=8400, perks=PERKS)
        build = dict(old, pick=dict(old), win=dict(old))
        core.restore_lola_styles(build)
        self.assertEqual([build['sec'], build['pick']['sec'], build['win']['sec']], [8300] * 3)
