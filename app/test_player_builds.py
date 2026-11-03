import copy
import json
from pathlib import Path
import unittest
import player_builds as model

FIXTURE=json.loads((Path(__file__).parent/'dev/fixtures/mobalytics-players.json').read_text(encoding='utf-8'))
class PlayerBuildTests(unittest.TestCase):
    def setUp(self):self.cache=copy.deepcopy(FIXTURE['index'])
    def listing(self):return model.listing(self.cache,'Ahri','MIDDLE')
    def test_exact_source_categories_and_slots(self):
        packet=self.listing();self.assertEqual(len(packet['groups']['OTP']),3);self.assertEqual(len(packet['groups']['Pro']),2)
        self.assertEqual(packet['groups']['Pro'][0]['name'],'Kenas');self.assertEqual(packet['groups']['OTP'][0]['name'],'MipoLz')
    def test_no_other_role_or_champion(self):
        self.assertIsNone(model.listing(self.cache,'Ahri','TOP'));self.assertIsNone(model.listing(self.cache,'Lux','MIDDLE'))
    def test_partial_listing_does_not_borrow_popular_items(self):
        for rows in self.listing()['groups'].values():
            for row in rows:self.assertIsNone(row['variant'])
    def test_all_five_live_details_from_same_player(self):
        for group in self.listing()['groups'].values():
            for row in group:
                with self.subTest(player=row['name']):
                    detail=model.detail(FIXTURE['pages'][row['id']],row);self.assertIsNotNone(detail)
                    self.assertEqual(detail['id'],row['id']);self.assertEqual(detail['name'],row['name']);self.assertIsNotNone(detail['variant'])
    def test_wrong_player_id_kind_and_patch_rejected(self):
        row=self.listing()['groups']['Pro'][0];page=FIXTURE['pages'][row['id']]
        for key,value in [('id','123'),('name','Somebody else'),('kind','OTP'),('patch','16.20'),('role','TOP')]:
            other=dict(row,**{key:value});self.assertIsNone(model.detail(page,other))
    def test_ignored_query_is_not_another_build(self):
        row=self.listing()['groups']['Pro'][0];self.assertIsNone(model.detail(self.cache,row))
    def test_invalid_results_do_not_become_zero(self):
        target=next(v for v in self.cache.values() if v.get('type')=='PRO_PLAYERS')
        target['stats']={'matchCount':10,'wins':11}
        self.assertFalse(any(row['id']==target['id'] for group in self.listing()['groups'].values() for row in group))
    def test_unclassified_record_is_not_a_pro(self):
        for value in self.cache.values():
            if value.get('type')=='PRO_PLAYERS':value['topPlayer']['type']='Other'
        self.assertEqual(self.listing()['groups'],{'OTP':[],'Pro':[]})
    def test_compact_preserves_factual_records(self):
        self.assertEqual(model.listing(model.compact(self.cache),'Ahri','MIDDLE'),self.listing())
    def test_complete_record_needs_matching_patch(self):
        row=self.listing()['groups']['Pro'][0];page=copy.deepcopy(FIXTURE['pages'][row['id']])
        build=next(v for v in page.values() if v.get('id')==row['id']);build['patch']='16.20';self.assertIsNone(model.detail(page,row))

if __name__=='__main__':unittest.main()
