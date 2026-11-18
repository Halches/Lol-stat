import copy
import unittest
from unittest.mock import Mock

from core import lola_item_sets
from lcu import LCU


class ShopImportTests(unittest.TestCase):
    def setUp(self):
        self.client = LCU()
        self.personal = dict(title='Мой набор', uid='personal', sortrank=0,
                             preferredItemSlots=[{'id': '1001', 'preferredItemSlot': 1}],
                             blocks=[{'type': 'Старт', 'items': [{'id': '1001', 'count': 1}]}])
        self.other = dict(title='LoL Helper заметки', uid='notes', sortrank=2)
        self.old = dict(title='LoL Helper: старая', uid='existing-helper', sortrank=0)
        self.collection = dict(accountId=7, timestamp=42, itemSets=[self.personal, self.old, self.other])
        self.calls = []

        def call(path, method='GET', body=None):
            self.assertEqual(path, '/lol-item-sets/v1/item-sets/7/sets')
            self.calls.append(method)
            if method == 'GET':
                return copy.deepcopy(self.collection)
            self.assertEqual(method, 'PUT')
            self.collection = copy.deepcopy(body)

        self.client.call = call
        self.builds = [('Ари: винрейт', [('Старт', [1056])]), ('Ари: популярная', [('Старт', [2031])])]

    def test_selected_build_first_with_stable_slots(self):
        self.assertTrue(self.client.set_items(7, 103, self.builds, None))
        first, second, *personal = self.collection['itemSets']
        self.assertEqual(first['title'], 'LoL Helper: Ари: винрейт')
        self.assertNotEqual(first['uid'], self.old['uid'])
        self.assertEqual(second['title'], 'LoL Helper: Ари: популярная')
        self.assertEqual(personal, [dict(self.personal, sortrank=2), dict(self.old, sortrank=3), dict(self.other, sortrank=4)])
        self.assertEqual([p['sortrank'] for p in self.collection['itemSets']], [0, 1, 2, 3, 4])
        self.assertEqual(self.calls, ['GET', 'PUT', 'GET'])
        self.assertEqual(self.collection['timestamp'], 42)
        self.calls.clear()
        self.assertTrue(self.client.set_items(7, 103, self.builds, None))
        self.assertEqual(self.calls, ['GET'])
        self.assertTrue(self.client.set_items(7, 103, self.builds[::-1], None))
        updated = self.collection['itemSets'][:2]
        self.assertEqual([p['uid'] for p in updated], [first['uid'], second['uid']])
        self.assertEqual(updated[0]['blocks'][0]['items'][0]['id'], '2031')
        self.assertTrue(self.client.set_items(7, 105, 'Физз', [('Старт', [1054])]))
        self.assertEqual([p['uid'] for p in self.collection['itemSets']], [first['uid'], 'personal', 'existing-helper', 'notes'])
        self.assertEqual(self.collection['itemSets'][0]['associatedChampions'], [105])

    def test_personal_page_with_helper_title_survives_repeat_import(self):
        self.assertTrue(self.client.set_items(7, 103, self.builds, None))
        mine = dict(self.personal, uid='copy', title='LoL Helper: мой запасной', sortrank=5)
        self.collection['itemSets'].append(mine)
        self.assertTrue(self.client.set_items(7, 103, self.builds[::-1], None))
        self.assertEqual(self.collection['itemSets'][-1], mine)

    def test_legacy_jhin_copies_disappear_after_import_without_removing_personal_sets(self):
        popular = dict(start=[1055], core=[6676, 3031], i4=[], i5=[], i6=[])
        win = dict(popular, core=[3094, 3031], n_core=81, wr_core=58.1)
        builds = lola_item_sets({'pick': popular, 'win': win}, 'Джин')[::-1]

        def legacy(uid, build, champ=202, **changes):
            name, groups = build
            return dict({'uid': uid, 'title': f'LoL Helper: {name}', 'associatedChampions': [champ],
                         'associatedMaps': [12], 'type': 'custom', 'map': 'any', 'mode': 'any',
                         'startedFrom': 'blank', 'sortrank': 0,
                         'blocks': [{'type': label, 'items': [{'id': str(item), 'count': 1} for item in items]}
                                    for label, items in groups if items]}, **changes)

        customized = legacy('customized', builds[0], preferredItemSlots=self.personal['preferredItemSlots'])
        renamed = legacy('renamed', builds[0], title='LoL Helper: запасной Джин')
        manual = legacy('manual', builds[0], blocks=self.personal['blocks'])
        other_champion = legacy('other-champion', ('Ари: популярная', builds[1][1]), champ=103)
        other_app = legacy('other-app', builds[1], title='Mobalytics: Джин')
        personal = [self.personal, customized, renamed, manual, other_champion, other_app]
        self.collection['itemSets'] = [*personal, legacy('old-win', builds[0]),
                                       legacy('old-popular', builds[1]), legacy('older-win', builds[0])]
        self.assertTrue(self.client.set_items(7, 202, builds, None, 12))
        first, second, *saved_personal = self.collection['itemSets']
        self.assertEqual([first['title'], second['title']], ['LoL Helper: Джин: лучший винрейт',
                                                            'LoL Helper: Джин: популярная'])
        self.assertEqual(first['associatedMaps'], [12])
        self.assertEqual(saved_personal, [dict(page, sortrank=i) for i, page in enumerate(personal, start=2)])
        self.calls.clear()
        self.assertTrue(self.client.set_items(7, 202, builds, None, 12))
        self.assertEqual(self.calls, ['GET'])

    def test_repeated_client_entries_merge_only_on_same_uid_and_content(self):
        same_content = dict(self.personal, uid='independent')
        different_content = dict(self.personal, title='Мой второй набор')
        personal = [self.personal, same_content, different_content, self.other]
        self.collection['itemSets'] = [*personal, *(dict(page, sortrank=10) for page in personal)]

        self.assertTrue(self.client.set_items(7, 103, self.builds, None))

        self.assertEqual(self.collection['itemSets'][2:],
                         [dict(page, sortrank=i) for i, page in enumerate(personal, start=2)])

    def test_first_import_into_empty_collection(self):
        self.collection['itemSets'] = []
        self.assertTrue(self.client.set_items(7, 103, self.builds, None))
        first, second = self.collection['itemSets']
        self.assertTrue(first['uid'] and second['uid'] and first['uid'] != second['uid'])

    def test_unreadable_collection_never_overwritten(self):
        for result in [None, {}, {'itemSets': None}, {'itemSets': [None]}, OSError('offline')]:
            with self.subTest(result=result):
                self.client.call = Mock(side_effect=[result])
                self.assertFalse(self.client.set_items(7, 103, self.builds, None))
                self.assertEqual(self.client.call.call_count, 1)

    def test_client_acknowledges_write_but_keeps_previous_order(self):
        self.client.call = Mock(side_effect=[self.collection, None, self.collection])
        self.assertFalse(self.client.set_items(7, 103, self.builds, None))
        self.assertIn('порядок', self.client.last_error)
