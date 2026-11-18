import copy
import unittest
from unittest.mock import Mock

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
        self.assertEqual(first['uid'], 'existing-helper')
        self.assertEqual(second['title'], 'LoL Helper: Ари: популярная')
        self.assertEqual(personal, [dict(self.personal, sortrank=2), dict(self.other, sortrank=3)])
        self.assertEqual([p['sortrank'] for p in self.collection['itemSets']], [0, 1, 2, 3])
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
        self.assertEqual([p['uid'] for p in self.collection['itemSets']], ['existing-helper', 'personal', 'notes'])
        self.assertEqual(self.collection['itemSets'][0]['associatedChampions'], [105])

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
