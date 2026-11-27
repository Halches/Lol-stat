import copy
import json
from pathlib import Path
import unittest
import offmeta_data as model

FIXTURE=json.loads((Path(__file__).parent/'dev/fixtures/mobalytics-offmeta.json').read_text())['payload']
class OffmetaTests(unittest.TestCase):
    def setUp(self):
        self.cache=copy.deepcopy(FIXTURE)
        self.entity=next(v for v in self.cache.values() if v.get('__typename')=='LolChampion')
        self.build=next(v for v in self.cache.values() if v.get('type')=='OFF_META')
    def parse(self):return model.parse_state(self.cache,'Ahri','MIDDLE')
    def test_live_factual_snapshot(self):
        v=self.parse();self.assertEqual(v['source_games'],6739);self.assertAlmostEqual(v['source_winrate'],3821/6739*100)
        self.assertEqual(v['variant']['perks'][0],8992);self.assertEqual(v['variant']['core'],[2503,3158,3100])
        self.assertNotIn('wr_runes',v['variant']);self.assertNotIn('wr_core',v['variant'])
    def test_context_is_not_inferred(self):
        self.assertIsNone(model.parse_state(self.cache,'Ahri','TOP'))
        self.assertIsNone(model.parse_state(self.cache,'Lux','MIDDLE'))
        for key,value in [('region','EUW'),('queue','RANKED_FLEX'),('rank','Gold'),('patch','latest')]:
            with self.subTest(key=key):
                cache=copy.deepcopy(self.cache);e=next(v for v in cache.values() if v.get('__typename')=='LolChampion');e['activeFilters'][key]=value
                self.assertIsNone(model.parse_state(cache,'Ahri','MIDDLE'))
    def test_other_variant_never_becomes_offmeta(self):
        self.build['type']='HIGHEST_WIN_RATE';self.assertIsNone(self.parse()['variant'])
    def test_mismatched_build_is_rejected(self):
        for key,value in [('patch','16.20'),('role','TOP'),('championSlug','lux'),('queue','ARAM'),('vsChampionSlug','viktor')]:
            with self.subTest(key=key):
                old=self.build[key];self.build[key]=value;self.assertIsNone(self.parse()['variant']);self.build[key]=old
    def test_missing_runes_items_and_invalid_sample(self):
        for field,value in [('perks',{}),('items',[]),('items',42),('stats',{'matchCount':0,'wins':0}),('stats',{'matchCount':10,'wins':11}),('spells',[999,4])]:
            with self.subTest(field=field):
                old=self.build[field];self.build[field]=value;self.assertIsNone(self.parse()['variant']);self.build[field]=old
    def test_complete_items_must_come_from_same_record(self):
        self.build['items']=[x for x in self.build['items'] if x['type']!='FullBuild'];self.assertIsNone(self.parse()['variant'])
    def test_plain_json_only(self):
        html='<script>window.__PRELOADED_STATE__='+json.dumps({'lolState':{'apollo':{'dynamic':self.cache}}})+';</script>'
        self.assertEqual(model.parse(html,'Ahri','MIDDLE')['source_games'],6739)
        self.assertIsNone(model.parse(html.replace('={','=(function(){return {',1),'Ahri','MIDDLE'))
    def test_absent_is_distinct_from_unverified(self):
        self.entity['buildsOptions']['options']=[];self.assertEqual(self.parse()['status'],'absent')
        self.entity['activeFilters']={};self.assertIsNone(self.parse())
    def test_pruned_cache_revalidates(self):
        self.assertEqual(model.parse_state(model.compact(self.cache),'Ahri','MIDDLE'),self.parse())
    def test_malformed_state(self):
        for value in (None,[],{}, {'a':4},{'a':{'__typename':'LolChampion','activeFilters':[]}}):self.assertIsNone(model.parse_state(value,'Ahri','MIDDLE'))

if __name__=='__main__':unittest.main()
